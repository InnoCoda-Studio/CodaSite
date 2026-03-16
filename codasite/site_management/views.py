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
from .models import SiteLocation, MaterialStock, CompanyProfile, MaterialDeduction, Invitation, StaffAttendance, SkilledWorker
from django.db.models import Sum
from .reports import get_daily_summary  # 👈 Import your new file
from django.core.mail import send_mail
from .reports import get_daily_summary, generate_pdf_report
from django.core.mail import EmailMessage
from decimal import Decimal
from .forms import WorkerPayForm


@login_required
def index(request):
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
        'recent_arrivals': recent_arrivals,  # 👈 Pass this
    })


@login_required
@transaction.atomic
def site_dashboard(request, site_id):
    site = get_object_or_404(SiteLocation, id=site_id)
    today = timezone.now().date()

    # 🟢 CRITICAL: Define 'workers' at the top so POST can see it
    workers = SkilledWorker.objects.filter(site=site)
    stocks = MaterialStock.objects.filter(site=site)

    # --- 1. HANDLE BUTTON CLICKS (POST) ---
    if request.method == "POST":

        # QUICK CLOCK-IN
        if 'quick_clock_in' in request.POST:
            worker = get_object_or_404(
                SkilledWorker, id=request.POST.get('worker_id'))
            StaffAttendance.objects.get_or_create(
                worker=worker, site=site, user=request.user,
                time_in__date=today,
                defaults={'time_in': timezone.now(), 'mode': 'SITE'}
            )
            messages.success(request, f"{worker.name} clocked in.")

        # QUICK CLOCK-OUT
        elif 'quick_clock_out' in request.POST:
            attendance = StaffAttendance.objects.filter(
                worker_id=request.POST.get('worker_id'),
                site=site, time_out__isnull=True
            ).last()
            if attendance:
                attendance.time_out = timezone.now()
                attendance.save()
                messages.success(
                    request, f"{attendance.worker.name} clocked out.")

        # ₦ NEW: UPDATE ALL PAY RATES
       # Inside your site_dashboard POST logic
        elif 'update_all_rates' in request.POST:
            # 🛡️ SECURITY CHECK: Only Contractor or PM
            invitation = Invitation.objects.filter(
                email=request.user.email, site=site).last()
            user_role = invitation.role_assigned if invitation else 'CONTRACTOR'

            if request.user == site.contractor or user_role == 'PROJECT_MANAGER':
                for worker in workers:
                    new_rate = request.POST.get(f'rate_{worker.id}')
                    if new_rate:
                        worker.daily_rate = Decimal(new_rate)
                        worker.save()
                messages.success(request, "Labor rates updated successfully.")
            else:
                messages.error(
                    request, "Access Denied: Only PMs can set prices.")

            return redirect('site_dashboard', site_id=site.id)
        # RECEIVE STOCK
        elif 'add_stock' in request.POST:
            name = request.POST.get('item_name', '').strip().upper()
            unit = request.POST.get('unit', '').strip()
            try:
                qty = Decimal(request.POST.get('quantity') or 0)
                stock, created = MaterialStock.objects.get_or_create(
                    site=site, item_name=name, defaults={'unit': unit}
                )
                stock.current_balance += qty
                if 'evidence_image' in request.FILES:
                    stock.evidence_image = request.FILES['evidence_image']
                if 'evidence_video' in request.FILES:
                    stock.evidence_video = request.FILES['evidence_video']
                stock.save()
                messages.success(request, f"Received {qty} {unit} of {name}.")
            except (InvalidOperation, ValueError):
                messages.error(request, "Invalid quantity.")

        # ISSUE MATERIAL
        elif 'issue_material' in request.POST:
            try:
                stock_item = get_object_or_404(
                    MaterialStock, id=request.POST.get('stock_item'))
                worker = get_object_or_404(
                    SkilledWorker, id=request.POST.get('worker_id'))
                qty = Decimal(request.POST.get('quantity') or 0)
                MaterialDeduction.objects.create(
                    stock_item=stock_item, worker=worker,
                    quantity_taken=qty, purpose=request.POST.get('purpose'),
                    authorized_by=request.user
                )
                messages.success(
                    request, f"Deduction authorized for {worker.name}")
            except ValidationError as e:
                messages.error(request, str(e))

        return redirect('site_dashboard', site_id=site.id)

    # --- GATHER DATA FOR THE PAGE ---
    site = get_object_or_404(SiteLocation, id=site_id)

    invitation = Invitation.objects.filter(
        email=request.user.email, site=site).last()
    user_role = invitation.role_assigned if invitation else 'CONTRACTOR'

    # --- 2. GATHER DATA FOR THE PAGE (GET) ---
    # 💰 Call the report logic for the Financial Cards
    weekly_data = get_weekly_summary(site.id)
    monthly_data = get_monthly_summary(site.id)

    # Track daily attendance
    attendance_today = StaffAttendance.objects.filter(
        site=site, time_in__date=today)
    present_worker_ids = attendance_today.values_list('worker_id', flat=True)

    return render(request, 'site_management/site_dashboard.html', {
        'site': site,
        'workers': workers,
        'stocks': stocks,
        'attendance_today': attendance_today,
        'present_worker_ids': present_worker_ids,
        'user_role': user_role,

        # 💵 The "Money" Variables
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


@login_required
def add_worker(request, site_id):
    site = get_object_or_404(SiteLocation, id=site_id)
    if request.method == "POST":
        SkilledWorker.objects.create(
            name=request.POST.get('name'),
            category=request.POST.get('category'),
            phone=request.POST.get('phone'),
            site=site,
            contractor=request.user
        )
    return redirect('site_dashboard', site_id=site_id)


@login_required
def all_workers(request):
    query = request.GET.get('search', '')
    workers = SkilledWorker.objects.filter(contractor=request.user)
    if query:
        workers = workers.filter(name__icontains=query)
    return render(request, 'site_management/all_workers.html', {'workers': workers, 'search_query': query})


@login_required
def worker_profile(request, slug):
    worker = get_object_or_404(
        SkilledWorker, slug=slug, contractor=request.user)
    history = StaffAttendance.objects.filter(
        worker=worker).order_by('-time_in')
    return render(request, 'site_management/worker_profile.html', {'worker': worker, 'history': history})


@login_required
def invite_staff(request):
    if request.method == "POST":
        email = request.POST.get('email')
        role = request.POST.get('role')
        site_id = request.POST.get('site_id')
        site = get_object_or_404(SiteLocation, id=site_id)

        # 1. Create the invitation in the DB
        token = uuid.uuid4()
        invite_link = Invitation.objects.create(
            email=email,
            site=site,
            role_assigned=role,
            invited_by=request.user,
            token=token
        )

        # 2. Build the Invitation Link
        # Replace 'innocoda.com' with your actual domain when live
        # Add 'account/' before 'register/'
        invite_link = f"http://127.0.0.1:8000/account/register/?token={token}"

        # 3. Send the Email
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
            messages.error(
                request, f"Email failed to send. Check your settings. Error: {e}")

        return redirect('profile')

# Restock


@login_required
def restock_history(request, site_id):
    site = get_object_or_404(SiteLocation, id=site_id)

    # Security check
    if site.contractor != request.user and not request.user.is_superuser:
        raise PermissionDenied()

    # Get all stock items for this site
    stocks = MaterialStock.objects.filter(site=site).order_by('-last_updated')

    return render(request, 'site_management/restock_history.html', {
        'site': site,
        'stocks': stocks,
    })


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
