
from decimal import Decimal  # 👈 Ensure this is at the top of your file!
from .models import SiteLocation, StaffAttendance, MaterialDeduction

from django.conf import settings
# Ensure these are at the top
from .reports import get_weekly_summary, get_monthly_summary
from .reports import get_weekly_summary, generate_pdf_report
from decimal import Decimal, InvalidOperation
from django.template.loader import render_to_string
import uuid
from django.core.exceptions import ValidationError
from django.db import transaction
from django.contrib import messages
# Added ValidationError
from django.core.exceptions import PermissionDenied, ValidationError
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from .models import SiteLocation, MaterialStock, CompanyProfile, MaterialDeduction, Invitation, StaffAttendance, SkilledWorker, MaterialRestockLog
from django.db.models import Sum
# 👈 Import your new file
from django.core.mail import send_mail
from .reports import get_daily_summary, generate_pdf_report
from django.core.mail import EmailMessage
from decimal import Decimal
from .forms import WorkerPayForm

from django.db.models import F
from django.db.models import Q


@login_required
def index(request):

    today = timezone.now().date()

    # Sites ordered newest first
    sites = SiteLocation.objects.filter(
        contractor=request.user
    ).order_by("-created_at")

    # Low stock items
    low_stock_items = MaterialStock.objects.filter(
        site__contractor=request.user,
        current_balance__lt=F('minimum_required')
    ).select_related('site').order_by('current_balance')

    # Recent arrivals
    recent_arrivals = MaterialStock.objects.filter(
        site__contractor=request.user,
        last_updated__date=today
    ).select_related('site').order_by('-last_updated')

    # Total cement

    sites = SiteLocation.objects.filter(contractor=request.user)
    today = timezone.now().date()

    # 🚨 LOW STOCK: Anything less than 10
    low_stock_items = MaterialStock.objects.filter(
        site__contractor=request.user,
        current_balance__lt=10
    ).select_related('site')

    # 🚚 NEW ARRIVALS: Anything added today
    # Assuming 'last_updated' is a field in your MaterialStock model
    recent_arrivals = MaterialStock.objects.filter(
        site__contractor=request.user,
        last_updated__date=today
    ).select_related('site')

    total_cement = MaterialStock.objects.filter(
        site__contractor=request.user,
        item_name__icontains='cement'
    ).aggregate(total=Sum('current_balance'))['total'] or 0

    return render(request, 'site_management/index.html', {
        'sites': sites,
        'total_cement': total_cement,
        'low_stock_items': low_stock_items,

        'recent_arrivals': recent_arrivals,

        'recent_arrivals': recent_arrivals,  # 👈 Pass this

    })


@login_required
@transaction.atomic
def site_dashboard(request, site_id):
    site = get_object_or_404(SiteLocation, id=site_id)
    today = timezone.now().date()

    # 1. PERMISSIONS & POOLS
    invitation = Invitation.objects.filter(
        email=request.user.email, site=site).last()
    user_role = invitation.role_assigned if invitation else 'CONTRACTOR'

    workers = SkilledWorker.objects.filter(site=site)
    stocks = MaterialStock.objects.filter(site=site)
    global_workers_pool = SkilledWorker.objects.filter(
        contractor=request.user
    ).exclude(site=site)

    # 2. HANDLE ACTIONS (ONE SINGLE POST BLOCK)
    if request.method == "POST":

        # A. REGISTER NEW WORKER
        if 'register_worker' in request.POST:
            try:
                worker = SkilledWorker.objects.create(
                    contractor=request.user,
                    site=site,
                    name=request.POST.get('name'),
                    category=request.POST.get('category'),
                    phone=request.POST.get('phone'),
                    daily_rate=request.POST.get('daily_rate') or 0,
                    emergency_contact=request.POST.get('emergency_contact'),
                    bank_name=request.POST.get('bank_name'),
                    account_number=request.POST.get('account_number'),
                    account_name=request.POST.get('account_name')
                )
                if 'profile_picture' in request.FILES:
                    worker.profile_picture = request.FILES['profile_picture']
                    worker.save()
                messages.success(
                    request, f"Registry created for {worker.name}.")
            except Exception as e:
                print(f"DATABASE ERROR: {e}")  # Check your terminal for this!
                messages.error(request, "Registry Error: Check all fields.")

        # B. RECALL / DEPLOY FROM MASTER REGISTRY
        elif 'deploy_worker' in request.POST:
            worker = get_object_or_404(SkilledWorker, id=request.POST.get(
                'worker_id'), contractor=request.user)
            worker.site = site
            if request.POST.get('update_category'):
                worker.category = request.POST.get('update_category')
            if request.POST.get('update_rate'):
                worker.daily_rate = Decimal(request.POST.get('update_rate'))
            worker.save()
            messages.success(
                request, f"{worker.name} deployed to {site.name}.")

        # C. CLOCK-IN
        elif 'quick_clock_in' in request.POST:
            worker = get_object_or_404(
                SkilledWorker, id=request.POST.get('worker_id'))
            StaffAttendance.objects.get_or_create(
                worker=worker, site=site, user=request.user,
                time_in__date=today,
                defaults={'time_in': timezone.now(), 'mode': 'SITE'}
            )
            messages.success(request, f"{worker.name} clocked in.")

        # D. CLOCK-OUT
        elif 'quick_clock_out' in request.POST:
            attendance = StaffAttendance.objects.filter(
                worker_id=request.POST.get('worker_id'), site=site, time_out__isnull=True
            ).last()
            if attendance:
                attendance.time_out = timezone.now()
                attendance.save()
                messages.success(
                    request, f"{attendance.worker.name} clocked out.")

        # E. UPDATE ALL PAY RATES
        elif 'update_all_rates' in request.POST:
            if request.user == site.contractor or user_role == 'PROJECT_MANAGER':
                for w in workers:
                    new_rate = request.POST.get(f'rate_{w.id}')
                    if new_rate:
                        w.daily_rate = Decimal(new_rate)
                        w.save()
                messages.success(request, "Labor rates updated.")

       # F. STOCK & MATERIAL LOGIC
        elif 'add_stock' in request.POST:
            try:
                # 1. Capture the form data
                qty_raw = request.POST.get('quantity')
                qty = Decimal(
                    qty_raw) if qty_raw and qty_raw.strip() else Decimal('0.00')
                item_name = request.POST.get('item_name', '').strip().upper()
                unit = request.POST.get('unit', '').strip()

                # 2. Update/Create the Master Balance card
                stock, created = MaterialStock.objects.get_or_create(
                    site=site,
                    item_name=item_name,
                    defaults={'unit': unit}
                )
                stock.current_balance += qty
                stock.save()

                # 3. 🟢 THE HISTORY RECEIPT (fills your history page)
                # Ensure your model handles null=True for both evidence fields!
                MaterialRestockLog.objects.create(
                    stock_item=stock,
                    site=site,
                    quantity_added=qty,
                    # We capture the image and video here
                    evidence_image=request.FILES.get('evidence_image'),
                    evidence_video=request.FILES.get('evidence_video')
                )
                messages.success(
                    request, f"Received {qty} {unit} of {item_name}. Proof logged.")
            except Exception as e:
                messages.error(request, f"Intake Error: {e}")

        # Inside your site_dashboard(request, site_id) function:

        # --- MATERIAL DEDUCTION LOGIC ---
        elif 'issue_material' in request.POST:
            stock_id = request.POST.get('stock_item')
            worker_id = request.POST.get('worker_id')
            try:
                qty = Decimal(request.POST.get('quantity') or 0)
                purpose = request.POST.get('purpose')

                # 1. Get the stock item and the worker
                stock = get_object_or_404(
                    MaterialStock, id=stock_id, site=site)
                worker = get_object_or_404(SkilledWorker, id=worker_id)

                # 2. Check if there is enough balance
                if stock.current_balance >= qty:
                    # 📉 Subtract the quantity
                    stock.current_balance -= qty
                    stock.save()

                    # 3. Create a record of WHO took it and WHY (The audit trail)
                    MaterialDeduction.objects.create(
                        stock_item=stock,
                        worker=worker,
                        quantity_taken=qty,
                        purpose=purpose,
                        authorized_by=request.user,
                    )
                    messages.success(
                        request, f"Authorized: {qty} {stock.unit} of {stock.item_name} issued to {worker.name}.")
                else:
                    messages.error(
                        request, f"Insufficient Stock! Only {stock.current_balance} {stock.unit} remaining.")

            except (InvalidOperation, ValueError):
                messages.error(request, "Invalid quantity entered.")

            return redirect('site_dashboard', site_id=site_id)

        return redirect('site_dashboard', site_id=site.id)

    # 3. GATHER DATA FOR GET REQUEST
    weekly_data = get_weekly_summary(site.id)
    monthly_data = get_monthly_summary(site.id)
    attendance_today = StaffAttendance.objects.filter(
        site=site, time_in__date=today)
    present_worker_ids = attendance_today.values_list('worker_id', flat=True)

    return render(request, 'site_management/site_dashboard.html', {
        'site': site,
        'workers': workers,
        'stocks': stocks,
        'attendance_today': attendance_today,
        'present_worker_ids': present_worker_ids,
        'global_workers_pool': global_workers_pool,
        'user_role': user_role,
        'total_spent': monthly_data['total_payroll'],
        'weekly_total': weekly_data['total_payroll'],
        'total_workers': weekly_data['total_workers'],
    })


@login_required
def daily_report(request, site_id):
    site = get_object_or_404(SiteLocation, id=site_id)
    if site.contractor != request.user and not request.user.is_superuser:
        raise PermissionDenied()

    today = timezone.now().date()

    # FIXED: Changed MaterialUsage to MaterialDeduction
    materials = MaterialDeduction.objects.filter(
        stock_item__site=site,
        timestamp__date=today
    )

    attendance = StaffAttendance.objects.filter(site=site, time_in__date=today)
    workers = SkilledWorker.objects.filter(
        contractor=request.user).select_related('site')

    context = {
        'site': site,
        'site_id': site_id,
        'materials': materials,
        'attendance': attendance,
        'workers': workers,
        'today': today,
    }
    return render(request, 'site_management/daily_report.html', context)

# --- WORKER & SITE MANAGEMENT ---


@login_required
def add_site(request):
    if request.method == "POST":
        SiteLocation.objects.create(
            name=request.POST.get('name'),
            address=request.POST.get('address'),
            contractor=request.user
        )
    return redirect('index')


# @login_required
# @transaction.atomic
# def add_worker(request, site_id):
#     site = get_object_or_404(SiteLocation, id=site_id)
#     if request.method == "POST":
#         id_num = request.POST.get('id_number', '').strip()
#         phone_num = request.POST.get('phone', '').strip()

#         if SkilledWorker.objects.filter(Q(id_number=id_num) | Q(phone=phone_num)).exists():
#             messages.error(
#                 request, "Access Denied: Personnel already exists in Global Registry.")
#             return redirect('site_dashboard', site_id=site_id)

#         try:
#             # 🟢 UPDATED: Capturing full details here too
#             SkilledWorker.objects.create(
#                 contractor=request.user,
#                 site=site,
#                 name=request.POST.get('name'),
#                 category=request.POST.get('category'),
#                 id_number=id_num,
#                 phone=phone_num,
#                 emergency_contact=request.POST.get(
#                     'emergency_contact'),  # 👈 ADD THIS
#                 bank_name=request.POST.get(
#                     'bank_name'),                 # 👈 ADD THIS
#                 account_number=request.POST.get(
#                     'account_number'),           # 👈 ADD THIS
#                 account_name=request.POST.get(
#                     'account_name'),             # 👈 ADD THIS
#                 pay_frequency=request.POST.get('pay_frequency'),
#                 profile_picture=request.FILES.get('profile_picture')
#             )
#             messages.success(request, "New Personnel enrolled and deployed.")
#         except Exception as e:
#             messages.error(
#                 request, "Registry Error: Please check bank and ID fields.")

#     return redirect('site_dashboard', site_id=site_id)
@login_required
@transaction.atomic
def add_worker(request, site_id):
    site = get_object_or_404(SiteLocation, id=site_id)
    if request.method == "POST":
        id_num = request.POST.get('id_number', '').strip()
        phone_num = request.POST.get('phone', '').strip()

        # Gatekeeper Check (Make sure Q is imported from django.db.models)
        if SkilledWorker.objects.filter(Q(id_number=id_num) | Q(phone=phone_num)).exists():
            messages.error(
                request, "Personnel already exists in Global Registry.")
            return redirect('site_dashboard', site_id=site_id)

        try:
            # 🟢 CAPTURE DAILY RATE FROM HTML
            # Note: We take it from the input named 'daily_rate'
            raw_rate = request.POST.get('daily_rate')
            daily_rate = Decimal(raw_rate) if raw_rate else Decimal('0.00')

            SkilledWorker.objects.create(
                contractor=request.user,
                site=site,
                name=request.POST.get('name'),
                category=request.POST.get('category'),
                id_number=id_num,
                phone=phone_num,
                emergency_contact=request.POST.get('emergency_contact'),
                bank_name=request.POST.get('bank_name'),
                account_number=request.POST.get('account_number'),
                account_name=request.POST.get('account_name'),
                pay_frequency=request.POST.get(
                    'pay_frequency', 'Daily'),  # Default to Daily
                daily_rate=daily_rate,  # 👈 THIS WAS MISSING
                profile_picture=request.FILES.get('profile_picture')
            )
            messages.success(request, "New Personnel enrolled and deployed.")
        except Exception as e:
            # THIS PRINT IS FOR YOU: Look at your black terminal to see the exact error
            print(f"CRITICAL ERROR: {e}")
            messages.error(request, f"Registry Error: {e}")

    return redirect('site_dashboard', site_id=site_id)


@login_required
def deploy_worker(request, site_id):
    """The 'Recall' Move: Transfer an existing worker to this site."""
    site = get_object_or_404(SiteLocation, id=site_id, contractor=request.user)

    if request.method == "POST":
        worker_id = request.POST.get('worker_id')
        worker = get_object_or_404(
            SkilledWorker, id=worker_id, contractor=request.user)

        # Update their site to the current site
        worker.site = site

        # If the Architect wants to update the rate for this specific project
        new_rate = request.POST.get('update_rate')
        if new_rate:
            worker.daily_rate = new_rate

        worker.save()

        messages.success(
            request, f"{worker.name} successfully deployed to {site.name}")

    return redirect('site_dashboard', site_id=site.id)


@login_required
@transaction.atomic
def all_workers(request):
    # --- 1. HANDLE SAVING NEW WORKER ---
    if request.method == "POST" and 'register_worker' in request.POST:
        try:
            # Get the data from the form
            id_num = request.POST.get('id_number', '').strip()
            phone_num = request.POST.get('phone', '').strip()

            # 🛡️ THE SECURITY CHECK: Check if ID or Phone already exists
            if SkilledWorker.objects.filter(id_number=id_num).exists():
                messages.error(
                    request, f"Access Denied: ID {id_num} already exists.")
                return redirect('all_workers')

            # Clean the money data properly
            raw_rate = request.POST.get('daily_rate')
            daily_rate = Decimal(
                raw_rate) if raw_rate and raw_rate.strip() else Decimal('0.00')

            # Create the record
            SkilledWorker.objects.create(
                contractor=request.user,
                name=request.POST.get('name'),
                category=request.POST.get('category'),
                id_number=id_num,
                phone=phone_num,
                emergency_contact=request.POST.get('emergency_contact'),
                bank_name=request.POST.get('bank_name'),
                account_number=request.POST.get('account_number'),
                account_name=request.POST.get('account_name'),
                daily_rate=daily_rate,
                pay_frequency=request.POST.get('pay_frequency', 'Daily'),
                profile_picture=request.FILES.get('profile_picture')
            )
            messages.success(
                request, "Personnel successfully added to Global Registry.")
            return redirect('all_workers')

        except Exception as e:
            # 👈 Watch your terminal for this!
            print(f"DATABASE REJECTION ERROR: {e}")
            messages.error(request, f"Registry Error: {e}")

    # --- 2. DISPLAY LOGIC ---
    workers = SkilledWorker.objects.filter(
        contractor=request.user).order_by('-id')
    return render(request, 'site_management/all_workers.html', {'workers': workers})

# This function is specifically for adding a worker WHILE on a site dashboard
# @login_required
# def add_worker(request, site_id):
#     site = get_object_or_404(SiteLocation, id=site_id)
#     if request.method == "POST":
#         # ... logic for site-specific add ...
#         # (Usually better to redirect to all_workers if it's a global registry)
#         pass
#     return redirect('site_dashboard', site_id=site_id)
# Global registry


@login_required
def add_worker(request, site_id):
    site = get_object_or_404(SiteLocation, id=site_id)

    if request.method == "POST":
        id_num = request.POST.get('id_number')

        # 🛡️ THE SECURITY CHECK: Check if ID already exists
        if id_num and SkilledWorker.objects.filter(id_number=id_num).exists():
            messages.error(
                request, f"Access Denied: ID {id_num} is already registered to another worker.")
            return redirect('site_dashboard', site_id=site_id)

        # If it's unique, go ahead and create
        try:
            SkilledWorker.objects.create(
                name=request.POST.get('name'),
                category=request.POST.get('category'),
                phone=request.POST.get('phone'),
                id_number=id_num,
                pay_frequency=request.POST.get('pay_frequency'),
                bank_name=request.POST.get('bank_name'),
                account_number=request.POST.get('account_number'),
                account_name=request.POST.get('account_name'),
                profile_picture=request.FILES.get('profile_picture'),
                site=site,
                contractor=request.user
            )
            messages.success(
                request, "Personnel successfully enrolled in registry.")
        except Exception as e:
            messages.error(request, "Registry Error: Please check all fields.")

    return redirect('site_dashboard', site_id=site_id)


@login_required
def worker_profile(request, slug):
    # 1. Fetch the specific worker (The "Dossier")
    worker = get_object_or_404(
        SkilledWorker, slug=slug, contractor=request.user
    )

    # 2. Fetch all activity (Every time they clocked in)
    history = StaffAttendance.objects.filter(
        worker=worker
    ).order_by('-time_in')

    # 3. Filter for Settlements (Only the logs you've clicked "Paid" on)
    # We use -payment_date so the most recent money sent is at the top
    payment_history = history.filter(is_paid=True).order_by('-payment_date')

    # 4. Calculate the Balance (The math for the orange card)
    unpaid_logs = history.filter(is_paid=False)
    unpaid_count = unpaid_logs.count()

    # Calculation: Days Unpaid x Their Snapshotted Rate (or current rate)
    total_debt = unpaid_count * worker.daily_rate

    # 5. Send the "Package" to your Premium HTML
    return render(request, 'site_management/worker_profile.html', {
        'worker': worker,
        'site': worker.site,
        'history': history,
        'payment_history': payment_history,
        'total_days': history.count(),
        'unpaid_days': unpaid_count,
        'total_debt': total_debt,
    })
#  mark as paid


@login_required
def mark_as_paid(request, attendance_id):
    # 1. Secure the log: Only the contractor who owns the site can authorize pay
    log = get_object_or_404(
        StaffAttendance,
        id=attendance_id,
        site__contractor=request.user
    )

    # 2. Logic Check: Only process if it hasn't been paid yet
    if not log.is_paid:
        log.is_paid = True
        log.payment_date = timezone.now()
        # Generate the digital receipt reference
        log.payment_reference = f"PAY-{log.id}-{timezone.now().strftime('%y%m%d')}"
        log.save()

        # 3. Success Feedback
        messages.success(
            request,
            f"Payment for {log.worker.name} on {log.time_in.date()} finalized: {log.payment_reference}"
        )
    else:
        messages.info(request, "This shift has already been settled.")

    # 4. Single Redirect (The logic "bridge" back to the profile)
    return redirect('worker_profile', slug=log.worker.slug)


@login_required
def invite_staff(request):
    if request.method == "POST":
        email = request.POST.get('email')
        role = request.POST.get('role')
        site_id = request.POST.get('site_id')

        # 1. Get the site or show 404 (Safely)
        site = get_object_or_404(SiteLocation, id=site_id)

        # 2. Create the invitation in the DB
        token = uuid.uuid4()
        # We rename this variable to 'invitation_obj' so it doesn't clash with the string link later
        invitation_obj = Invitation.objects.create(
            email=email,
            site=site,
            role_assigned=role,
            invited_by=request.user,
            token=token
        )

        # 3. Build the REAL Invitation Link (The Banana Island Move)
        # This uses your actual Render URL
        domain = "https://codasite.onrender.com"
        invite_link = f"{domain}/account/register/?token={token}"

        # 4. Send the Email
        subject = f"Invitation to join {site.name} on CodaSite"
        message = f"""
        Hello,
        
        You have been invited by {request.user.username} to join the project at {site.name} 
        as a {role.replace('_', ' ').title()}.
        
        Please click the link below to set up your account:
        {invite_link}
        
        This link is unique to your email address.
        
        Best regards,
        InnoCoda Team
        """

        try:
            send_mail(
                subject,
                message,
                settings.DEFAULT_FROM_EMAIL,
                [email],
                fail_silently=False,
            )
            messages.success(
                request, f"Invitation sent successfully to {email}!")
        except Exception as e:
            messages.error(request, f"Email failed to send. Error: {e}")

        return redirect('index')  # Or wherever your dashboard is

# Restock


@login_required
def restock_history(request, site_id):
    """View the full visual proof log for all materials on a specific site."""
    site = get_object_or_404(SiteLocation, id=site_id)

    # 🛡️ ONE SECURITY CHECK: Is this user allowed to be here?
    is_pm = Invitation.objects.filter(
        email=request.user.email, site=site).exists()
    if site.contractor != request.user and not request.user.is_superuser and not is_pm:
        raise PermissionDenied()

    # 🟢 THE HISTORY LOGS (Every delivery event)
    # We use select_related to get the name and unit from the Stock model
    history = MaterialRestockLog.objects.filter(
        site=site).select_related('stock_item').order_by('-timestamp')

    # 🟢 THE CURRENT TOTALS (For the top of the page if needed)
    stocks = MaterialStock.objects.filter(site=site).order_by('-last_updated')

    return render(request, 'site_management/restock_history.html', {
        'site': site,
        'history': history,
        'stocks': stocks
    })


# @login_required
# def material_usage_report(request, site_id):
#     site = get_object_or_404(SiteLocation, id=site_id)

#     # 🟢 THE FIX: Add 'authorized_by' to select_related
#     usage_logs = MaterialDeduction.objects.filter(
#         stock_item__site=site
#     ).select_related('worker', 'stock_item', 'authorized_by').order_by('-timestamp')

#     return render(request, 'site_management/material_usage_report.html', {
#         'site': site,
#         'usage_logs': usage_logs,
#     })
@login_required
def material_usage_report(request, site_id):
    site = get_object_or_404(SiteLocation, id=site_id)

    # 🛡️ Security Check
    if site.contractor != request.user and not request.user.is_superuser:
        # (Add your PM invitation check here if needed)
        pass

    # 🟢 THE OPTIMIZED QUERY
    # select_related pulls the Worker, Stock Item, and Authorizer in 1 database hit
    usage_logs = MaterialDeduction.objects.filter(
        stock_item__site=site
    ).select_related('worker', 'stock_item', 'authorized_by').order_by('-timestamp')

    return render(request, 'site_management/material_usage_report.html', {
        'site': site,
        'usage_logs': usage_logs,
    })
# Profiles


# Profiles

@login_required
def profile_view(request):
    user = request.user

    # 1. Determine Role & Site Assignment
    invitation = Invitation.objects.filter(
        email=user.email, is_used=True).last()
    user_role = invitation.role_assigned if invitation else 'CONTRACTOR'

    # 2. Get Branding (Logo/Business Name)
    # If they are staff, we pull the profile of the person who invited them
    if invitation:
        company_profile = CompanyProfile.objects.filter(
            contractor=invitation.invited_by).first()
    else:
        company_profile = CompanyProfile.objects.filter(
            contractor=user).first()

    context = {
        'user_role': user_role,
        'invitation': invitation,
        'company_profile': company_profile,
        'sites_count': SiteLocation.objects.filter(contractor=user).count() if user_role == 'CONTRACTOR' else 0,
        # For staff, show the one site they are assigned to
        'assigned_site': invitation.site if invitation else None,
    }

    return render(request, 'site_management/profile.html', context)


@login_required
def update_company_logo(request):
    if request.method == "POST" and request.FILES.get('logo'):
        # Get or create the profile
        profile, created = CompanyProfile.objects.get_or_create(
            contractor=request.user)
        profile.logo = request.FILES['logo']
        profile.save()
        messages.success(request, "Logo updated successfully!")
    return redirect('profile')


@login_required
def update_company_name(request):
    if request.method == "POST":
        name = request.POST.get('business_name')
        profile, created = CompanyProfile.objects.get_or_create(
            contractor=request.user)
        profile.business_name = name
        profile.save()
        messages.success(request, "Company name updated!")
    return redirect('profile')


@login_required
def close_site_day(request, site_id):
    if request.method == "POST":
        # 1. Get the data
        summary = get_daily_summary(site_id)

        # 2. FIXED: Pass the specific template path for daily reports
        pdf_content = generate_pdf_report(summary, 'reports/pdf_template.html')

        # 3. Build the HTML body for the email
        html_message = render_to_string(
            'site_management/daily_report_email.html', summary)

        # 4. Prepare the EmailMessage
        email = EmailMessage(
            subject=f"OFFICIAL REPORT: {summary['site'].name} - {summary['today']}",
            body="Please view the attached PDF and HTML report for today's site activities.",
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=summary['recipients'],
        )

        email.content_subtype = "html"
        email.body = html_message

        # 5. Attach the PDF
        if pdf_content:
            email.attach(
                f"Report_{summary['site'].name}_{summary['today']}.pdf",
                pdf_content,
                'application/pdf'
            )

        try:
            email.send()
            messages.success(
                request, f"Daily reports for {summary['site'].name} dispatched!")
        except Exception as e:
            messages.error(request, f"Report failed to send: {e}")

        return redirect('site_dashboard', site_id=site_id)


# Weekly report
@login_required
def send_weekly_report(request, site_id):
    if request.method == "POST":
        # 1. Get the weekly aggregated data
        summary = get_weekly_summary(site_id)

        # 2. Use the WEEKLY template here
        pdf_content = generate_pdf_report(
            summary, 'reports/weekly_pdf_template.html')

        # 3. Prepare the Email
        email = EmailMessage(
            subject=f"WEEKLY EXECUTIVE AUDIT: {summary['site'].name}",
            body=f"Hello,\n\nPlease find attached the weekly executive summary for {summary['site'].name}.",
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=summary['recipients'],
        )

        if pdf_content:
            email.attach(
                f"Weekly_Audit_{summary['site'].name}_{summary['end_date']}.pdf",
                pdf_content,
                'application/pdf'
            )

        try:
            email.send()
            messages.success(request, "Weekly Executive Summary dispatched!")
        except Exception as e:
            messages.error(request, f"Email failed: {e}")

        return redirect('site_dashboard', site_id=site_id)
# site_management/views.py (Refactored)


def send_weekly_report_logic(site_id):
    """The core engine that builds and sends the PDF."""
    try:
        summary = get_weekly_summary(site_id)
        pdf_content = generate_pdf_report(
            summary, 'reports/weekly_pdf_template.html')

        email = EmailMessage(
            subject=f"WEEKLY EXECUTIVE AUDIT: {summary['site'].name}",
            body=f"Automated weekly summary attached.",
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=summary['recipients'],
        )
        if pdf_content:
            email.attach(
                f"Weekly_Audit_{summary['site'].name}.pdf", pdf_content, 'application/pdf')
            email.send()
            return True
    except Exception as e:
        print(f"Error sending automated report: {e}")
    return False

# Your existing view now just calls the logic


@login_required
def send_weekly_report(request, site_id):
    if request.method == "POST":
        if send_weekly_report_logic(site_id):
            messages.success(request, "Weekly Executive Summary dispatched!")
        else:
            messages.error(request, "Failed to send report.")
        return redirect('site_dashboard', site_id=site_id)


@login_required
def update_worker_pay(request, worker_id):
    worker = get_object_or_404(SkilledWorker, id=worker_id)
    if request.method == "POST":
        form = WorkerPayForm(request.POST, instance=worker)
        if form.is_valid():
            form.save()
            messages.success(request, f"Pay updated for {worker.name}")
            return redirect('staff_list')  # Redirect back to your worker list
    else:
        form = WorkerPayForm(instance=worker)

    return render(request, 'site_management/update_pay.html', {'form': form, 'worker': worker})


# site_management/views.py


@login_required
def site_operations(request, site_id):
    site = get_object_or_404(SiteLocation, id=site_id)
    today = timezone.now().date()

    # 1. Get Financial Data for the Cards
    weekly_data = get_weekly_summary(site.id)
    monthly_data = get_monthly_summary(site.id)

    # 2. Get Site Data for the Roll Call and Warehouse
    workers = SkilledWorker.objects.filter(site=site)
    stocks = MaterialStock.objects.filter(site=site)

    # 3. Track who is present TODAY
    attendance_today = StaffAttendance.objects.filter(
        site=site, time_in__date=today)
    present_worker_ids = attendance_today.values_list('worker_id', flat=True)

    context = {
        'site': site,
        'workers': workers,
        'stocks': stocks,
        'attendance_today': attendance_today,
        'present_worker_ids': present_worker_ids,

        # 💰 These fill your New Financial Cards:
        'total_spent': monthly_data['total_payroll'],
        'weekly_total': weekly_data['total_payroll'],
        'total_workers': weekly_data['total_workers'],
    }
    return render(request, 'site_management/operations.html', context)


# from django.db.models import Sum # 👈 This is our "Calculator" tool
# from .models import SiteLocation, StaffAttendance, MaterialDeduction


@login_required
def financial_dashboard(request):
    sites = SiteLocation.objects.filter(contractor=request.user)
    site_data = []

    for site in sites:
        # 🟢 LABOR MATH: Grouping by category but summing the SNAPSHOTTED rate
        # We use 'worker__category' to group them, but 'daily_rate_at_time' for the money.
        labor_totals = StaffAttendance.objects.filter(site=site).values(
            'worker__category'
        ).annotate(
            # 👈 Using your smart snapshot field
            total_spent=Sum('daily_rate_at_time')
        )

        # 🟢 MATERIAL MATH: Grouping by item name
        material_totals = MaterialDeduction.objects.filter(stock_item__site=site).values(
            'stock_item__item_name'
        ).annotate(
            total_used=Sum('quantity_taken')
        )

        # Calculate the site total from our grouped labor data
        site_cash_total = sum(item['total_spent']
                              or 0 for item in labor_totals)

        site_data.append({
            'site': site,
            'labor': labor_totals,
            'materials': material_totals,
            'grand_total': site_cash_total
        })

    return render(request, 'site_management/financial_dashboard.html', {'site_data': site_data})
