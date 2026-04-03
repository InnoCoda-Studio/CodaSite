from django.shortcuts import redirect
from datetime import timedelta  # Add this at the top
from decimal import Decimal  # 👈 Ensure this is at the top of your file!
from .models import SiteLocation, StaffAttendance, MaterialDeduction

from django.conf import settings
# Ensure these are at the top
#
from .reports import get_weekly_summary, generate_pdf_report, get_monthly_summary
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
from .models import SiteLocation, MaterialStock, Company, MaterialDeduction, Invitation, StaffAttendance, SkilledWorker, MaterialRestockLog
from django.db.models import Sum
# 👈 Import your new file
from django.core.mail import send_mail
from .reports import get_daily_summary, generate_pdf_report
from django.core.mail import EmailMessage
from decimal import Decimal
from .forms import WorkerPayForm
from .utils import get_weekly_summary, get_monthly_summary


from django.db.models import Q, F
# Distance calculating
from math import radians, cos, sin, asin, sqrt
from django.http import HttpResponse
from decimal import Decimal
# Clok in


@login_required
def index(request):
    today = timezone.now().date()

    # 🏢 1. Identify the Company
    # ✅ FIX: Changed 'site_company_profile' to 'company' to match your model
    try:
        user_company = request.user.company
    except AttributeError:
        # 🛡️ Safety: If it's a superuser or user without a company yet
        messages.error(request, "Access Denied: No Company Profile found.")
        return redirect('login')

    # 🏗️ 2. BASE QUERIES (Filtered by Company)
    # We use the 'user_company' object we just grabbed
    user_sites = SiteLocation.objects.filter(company=user_company)
    sites = user_sites.order_by("-created_at")

    # 📦 3. INVENTORY LOGIC (Scoped to the Company's Sites)
    # Filter by the company object directly
    low_stock_items = MaterialStock.objects.filter(
        site__company=user_company,
        current_balance__lt=F('minimum_required')
    ).select_related('site').order_by('current_balance')

    recent_arrivals = MaterialStock.objects.filter(
        site__company=user_company,
        last_updated__date=today
    ).select_related('site').order_by('-last_updated')

    # 💰 4. GLOBAL AGGREGATES (Total Cement across all sites in the company)
    total_cement = MaterialStock.objects.filter(
        site__company=user_company,
        item_name__icontains='cement'
    ).aggregate(total=Sum('current_balance'))['total'] or 0

    context = {
        'sites': sites,
        'total_cement': total_cement,
        'low_stock_items': low_stock_items,
        'recent_arrivals': recent_arrivals,
        'company': user_company,  # Added this so your template can show the name
    }

    # 🚀 HTMX MAGIC: Partial update for the Dashboard Feed
    if request.headers.get('HX-Request'):
        return render(request, 'site_management/htmx_components/dashboard_feed.html', context)

    return render(request, 'site_management/index.html', context)


# @login_required
# @transaction.atomic
# def site_dashboard(request, site_id):
#    # 🏢 1. Identify the Company
#     # Every user (Contractor or Staff) must be linked to a CompanyProfile

#     user_company = request.user.company

#     # 🛡️ 2. Secure the Site
#     # Only allow access if the site belongs to the user's company
#     site = get_object_or_404(SiteLocation, id=site_id, company=user_company)

#     today = timezone.now().date()

#     # 3. Permissions Check
#     invitation = Invitation.objects.filter(
#         email=request.user.email, site=site).last()
#     user_role = invitation.role_assigned if invitation else 'CONTRACTOR'

#     invitation = Invitation.objects.filter(
#         email=request.user.email, site=site).last()
#     user_role = invitation.role_assigned if invitation else 'CONTRACTOR'

#     is_boss = user_role in ['CONTRACTOR', 'PROJECT_MANAGER']

#     # 4. Scoped Pools (This is where you save money/security!)
#     workers = SkilledWorker.objects.filter(site=site)
#     stocks = MaterialStock.objects.filter(site=site)

#     # 🌍 GLOBAL POOL: Only show workers from the SAME company
#     global_workers_pool = SkilledWorker.objects.filter(
#         company=user_company  # ✅ NEW (Much cleaner!)
#     ).exclude(site=site)

#     # 2. HANDLE ACTIONS (ONE SINGLE POST BLOCK)
#     if request.method == "POST":

#         # A. REGISTER NEW WORKER
#         if 'register_worker' in request.POST:
#             try:
#                 worker = SkilledWorker.objects.create(
#                     contractor=request.user,
#                     company=user_company,
#                     site=site,
#                     name=request.POST.get('name'),
#                     category=request.POST.get('category'),
#                     phone=request.POST.get('phone'),
#                     daily_rate=request.POST.get('daily_rate') or 0,
#                     emergency_contact=request.POST.get('emergency_contact'),
#                     bank_name=request.POST.get('bank_name'),
#                     account_number=request.POST.get('account_number'),
#                     account_name=request.POST.get('account_name')
#                 )
#                 if 'profile_picture' in request.FILES:
#                     worker.profile_picture = request.FILES['profile_picture']
#                     worker.save()
#                 messages.success(
#                     request, f"Registry created for {worker.name}.")
#             except Exception as e:
#                 print(f"DATABASE ERROR: {e}")  # Check your terminal for this!
#                 messages.error(request, "Registry Error: Check all fields.")

#         # B. RECALL / DEPLOY FROM MASTER REGISTRY
#         elif 'deploy_worker' in request.POST:
#             worker = get_object_or_404(SkilledWorker, id=request.POST.get(
#                 'worker_id'), contractor=request.user)
#             worker.site = site
#             if request.POST.get('update_category'):
#                 worker.category = request.POST.get('update_category')
#             if request.POST.get('update_rate'):
#                 worker.daily_rate = Decimal(request.POST.get('update_rate'))
#             worker.save()
#             messages.success(
#                 request, f"{worker.name} deployed to {site.name}.")

#         # E. UPDATE ALL PAY RATES
#         elif 'update_all_rates' in request.POST:
#             # ✅ Change this (Line 210 area):
#             if request.user == site.company.owner or user_role == 'PROJECT_MANAGER':
#                 for w in workers:
#                     new_rate = request.POST.get(f'rate_{w.id}')
#                     if new_rate:
#                         w.daily_rate = Decimal(new_rate)
#                         w.save()
#                 messages.success(request, "Labor rates updated.")

#        # F. STOCK & MATERIAL LOGIC
#         elif 'add_stock' in request.POST:
#             try:
#                 # 1. Capture the form data
#                 qty_raw = request.POST.get('quantity')
#                 qty = Decimal(
#                     qty_raw) if qty_raw and qty_raw.strip() else Decimal('0.00')
#                 item_name = request.POST.get('item_name', '').strip().upper()
#                 unit = request.POST.get('unit', '').strip()

#                 # 2. Update/Create the Master Balance card
#                 stock, created = MaterialStock.objects.get_or_create(
#                     site=site,
#                     item_name=item_name,
#                     defaults={'unit': unit}
#                 )
#                 stock.current_balance += qty
#                 stock.save()

#                 # 3. 🟢 THE HISTORY RECEIPT (fills your history page)
#                 # Ensure your model handles null=True for both evidence fields!
#                 MaterialRestockLog.objects.create(
#                     stock_item=stock,
#                     site=site,
#                     quantity_added=qty,
#                     # We capture the image and video here
#                     evidence_image=request.FILES.get('evidence_image'),
#                     evidence_video=request.FILES.get('evidence_video')
#                 )
#                 messages.success(
#                     request, f"Received {qty} {unit} of {item_name}. Proof logged.")
#             except Exception as e:
#                 messages.error(request, f"Intake Error: {e}")

#         # Inside your site_dashboard(request, site_id) function:

#         # --- MATERIAL DEDUCTION LOGIC ---

# # ... inside your POST logic ...
#             # --- MATERIAL DEDUCTION LOGIC ---
#         # elif 'issue_material' in request.POST:
#         #     stock_id = request.POST.get('stock_item')
#         #     worker_id = request.POST.get('worker_id')
#         #     try:
#         #         qty = Decimal(request.POST.get('quantity') or 0)
#         #         purpose = request.POST.get('purpose', 'General Use')

#         #         # 1. THE LOCK: Use select_for_update to stop other clicks
#         #         with transaction.atomic():
#         #             stock = MaterialStock.objects.select_for_update().get(id=stock_id, site=site)
#         #             worker = get_object_or_404(SkilledWorker, id=worker_id)

#         #             if stock.current_balance >= qty:
#         #                 # 2. DO THE MATH MANUALLY (Easier to see)
#         #                 old_balance = stock.current_balance
#         #                 new_balance = old_balance - qty

#         #                 # 3. UPDATE THE STOCK
#         #                 stock.current_balance = new_balance
#         #                 stock.save()

#         #                 # 4. CREATE THE LOG
#         #                 MaterialDeduction.objects.create(
#         #                     stock_item=stock,
#         #                     worker=worker,
#         #                     quantity_taken=qty,
#         #                     purpose=purpose,
#         #                     authorized_by=request.user,
#         #                 )

#         #                 messages.success(
#         #                     request, f"Deducted {qty}. Balance: {old_balance} -> {new_balance}")
#         #             else:
#         #                 messages.error(
#         #                     request, f"Insufficient Stock! Only {stock.current_balance} left.")

#         #     except Exception as e:
#         #         messages.error(request, f"System Error: {e}")

#             # 5. THE ULTIMATE KILL-SWITCH: Move the redirect OUTSIDE the try block
#             # return redirect('site_dashboard', site_id=site.id)

#     # 3. GATHER DATA FOR GET REQUEST
#     weekly_data = get_weekly_summary(site.id)
#     monthly_data = get_monthly_summary(site.id)
#     attendance_today = StaffAttendance.objects.filter(
#         site=site, time_in__date=today)

#     # 🎯 THE FIX: Only include workers who haven't clocked out yet!
#     present_worker_ids = list(attendance_today.filter(
#         time_out__isnull=True
#     ).values_list('worker_id', flat=True))

#     return render(request, 'site_management/site_dashboard.html', {
#         'site': site,
#         'is_boss': is_boss,
#         'workers': workers,
#         'stocks': stocks,
#         'attendance_today': attendance_today,
#         'present_worker_ids': present_worker_ids,
#         'global_workers_pool': global_workers_pool,
#         'user_role': user_role,
#         'total_spent': monthly_data['total_payroll'],
#         'weekly_total': weekly_data['total_payroll'],
#         'total_workers': weekly_data['total_workers'],
#     })

@login_required
@transaction.atomic
def site_dashboard(request, site_id):
    # 🏢 1. Identify the Company
    user_company = request.user.company

    # 🛡️ 2. Secure the Site
    site = get_object_or_404(SiteLocation, id=site_id, company=user_company)
    today = timezone.now().date()

    # 3. Permissions Check
    invitation = Invitation.objects.filter(
        email=request.user.email, site=site).last()
    user_role = invitation.role_assigned if invitation else 'CONTRACTOR'
    is_boss = user_role in ['CONTRACTOR', 'PROJECT_MANAGER']

    # 4. Scoped Pools
    workers = SkilledWorker.objects.filter(site=site)
    stocks = MaterialStock.objects.filter(
        site=site)  # Keep for summary display

    # 🌍 GLOBAL POOL: Only show workers from the SAME company (for deployment)
    global_workers_pool = SkilledWorker.objects.filter(
        company=user_company
    ).exclude(site=site)

    # 5. HANDLE PERSONNEL ACTIONS
    if request.method == "POST":

        # A. REGISTER NEW WORKER
        if 'register_worker' in request.POST:
            try:
                worker = SkilledWorker.objects.create(
                    contractor=request.user,
                    company=user_company,
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
                messages.error(request, "Registry Error: Check all fields.")

        # B. DEPLOY FROM MASTER REGISTRY
        elif 'deploy_worker' in request.POST:
            worker = get_object_or_404(SkilledWorker, id=request.POST.get(
                'worker_id'), company=user_company)
            worker.site = site
            if request.POST.get('update_category'):
                worker.category = request.POST.get('update_category')
            if request.POST.get('update_rate'):
                worker.daily_rate = Decimal(request.POST.get('update_rate'))
            worker.save()
            messages.success(
                request, f"{worker.name} deployed to {site.name}.")

        # C. UPDATE ALL PAY RATES
        elif 'update_all_rates' in request.POST:
            if is_boss:
                for w in workers:
                    new_rate = request.POST.get(f'rate_{w.id}')
                    if new_rate:
                        w.daily_rate = Decimal(new_rate)
                        w.save()
                messages.success(request, "Labor rates updated.")

        return redirect('site_dashboard', site_id=site.id)

    # 6. GATHER DATA FOR DISPLAY
    weekly_data = get_weekly_summary(site.id)
    monthly_data = get_monthly_summary(site.id)
    attendance_today = StaffAttendance.objects.filter(
        site=site, time_in__date=today)

    # 🎯 THE FIX: Active workers only
    present_worker_ids = list(attendance_today.filter(
        time_out__isnull=True
    ).values_list('worker_id', flat=True))

    return render(request, 'site_management/site_dashboard.html', {
        'site': site,
        'is_boss': is_boss,
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


# @login_required
# @transaction.atomic
# def site_warehouse(request, site_id):
#     user_company = request.user.company
#     site = get_object_or_404(SiteLocation, id=site_id, company=user_company)

#     if request.method == "POST":
#         # 🟢 Logic for ADDING STOCK
#         if 'add_stock' in request.POST:
#             try:
#                 qty = Decimal(request.POST.get('quantity') or '0')
#                 item_name = request.POST.get('item_name', '').strip().upper()
#                 unit = request.POST.get('unit', '').strip()

#                 stock, _ = MaterialStock.objects.get_or_create(
#                     site=site, item_name=item_name, defaults={'unit': unit}
#                 )
#                 stock.current_balance += qty
#                 stock.save()

#                 MaterialRestockLog.objects.create(
#                     stock_item=stock, site=site, quantity_added=qty,
#                     evidence_image=request.FILES.get('evidence_image'),
#                     evidence_video=request.FILES.get('evidence_video')
#                 )
#                 messages.success(
#                     request, f"Inventory updated: {qty} {unit} of {item_name}")
#             except Exception as e:
#                 messages.error(request, f"Error adding stock: {e}")

#             # 🎯 CRITICAL: Redirect here so the page refreshes properly
#             return redirect('site_warehouse', site_id=site.id)

#         # 🔴 Logic for ISSUING MATERIAL
#         elif 'issue_material' in request.POST:
#             try:
#                 stock_id = request.POST.get('stock_item')
#                 worker_id = request.POST.get('worker_id')
#                 qty = Decimal(request.POST.get('quantity') or 0)
#                 purpose = request.POST.get('purpose', 'General Use')

#                 stock = MaterialStock.objects.select_for_update().get(id=stock_id, site=site)
#                 worker = get_object_or_404(SkilledWorker, id=worker_id)

#                 if stock.current_balance >= qty:
#                     stock.current_balance -= qty
#                     stock.save()

#                     MaterialDeduction.objects.create(
#                         stock_item=stock, worker=worker,
#                         quantity_taken=qty, purpose=purpose, authorized_by=request.user,
#                     )
#                     messages.success(
#                         request, f"Authorized release: {qty} {stock.unit}")
#                 else:
#                     messages.error(request, "Insufficient stock available.")
#             except Exception as e:
#                 messages.error(request, f"Requisition Error: {e}")

#             # 🎯 CRITICAL: Redirect here too!
#             return redirect('site_warehouse', site_id=site.id)

#     # 📋 3. GATHER DATA FOR GET REQUEST
#     stocks = MaterialStock.objects.filter(site=site)
#     workers = SkilledWorker.objects.filter(site=site)

#     # Permission checks
#     invitation = Invitation.objects.filter(
#         email=request.user.email, site=site).last()
#     user_role = invitation.role_assigned if invitation else 'CONTRACTOR'

#     return render(request, 'site_management/site_warehouse.html', {
#         'site': site,
#         'stocks': stocks,
#         'workers': workers,
#         'user_role': user_role,
#     })

@login_required
# @transaction.atomic
def site_warehouse(request, site_id):
    user_company = request.user.company
    site = get_object_or_404(SiteLocation, id=site_id, company=user_company)

    # --- HANDLE ACTIONS FOR MATERIALS ---
    if request.method == "POST":
        # A. ADD STOCK
        if 'add_stock' in request.POST:
            try:
                qty = Decimal(request.POST.get('quantity') or '0.00')
                item_name = request.POST.get('item_name', '').strip().upper()
                unit = request.POST.get('unit', '').strip()

                # 📸 Capture the files once here
                img_file = request.FILES.get('evidence_image')
                vid_file = request.FILES.get('evidence_video')

                stock, _ = MaterialStock.objects.get_or_create(
                    site=site, item_name=item_name, defaults={'unit': unit}
                )

                # ➕ Update Balance
                stock.current_balance += qty

                # 🔄 SYNC: Update the Stock object with the latest proof
                if img_file:
                    stock.evidence_image = img_file
                if vid_file:
                    stock.evidence_video = vid_file

                stock.save()

                # 📝 LOG: Create the audit trail
                MaterialRestockLog.objects.create(
                    stock_item=stock,
                    site=site,
                    quantity_added=qty,
                    evidence_image=img_file,
                    evidence_video=vid_file
                )

                messages.success(
                    request, f"Received {qty} {unit} of {item_name}.")
            except Exception as e:
                messages.error(request, f"Intake Error: {e}")

       # B. ISSUE MATERIAL
        elif 'issue_material' in request.POST:
            stock_id = request.POST.get('stock_item')
            worker_id = request.POST.get('worker_id')
            qty_input = request.POST.get('quantity')

            try:
                qty = Decimal(qty_input or 0)

                # 🛡️ 1. LOCK THE TRANSACTION
                with transaction.atomic():
                    # 🔒 select_for_update() makes Request #2 wait until Request #1 is DONE
                    stock = MaterialStock.objects.select_for_update().get(id=stock_id, site=site)
                    worker = get_object_or_404(SkilledWorker, id=worker_id)

                    # 🛡️ 2. CHECK FOR DUPLICATES (Inside the Lock!)
                    # Check if this exact worker took this exact amount in the last 10 seconds
                    is_duplicate = MaterialDeduction.objects.filter(
                        stock_item=stock,
                        worker=worker,
                        quantity_taken=qty,
                        timestamp__gte=timezone.now() - timedelta(seconds=10)
                    ).exists()

                    if is_duplicate:
                        # If Request #2 tries to run, it finds Request #1's data and STOPS.
                        return redirect('site_warehouse', site_id=site.id)

                    # 🛡️ 3. DO THE MATH
                    if stock.current_balance >= qty:
                        stock.current_balance -= qty
                        stock.save()

                        MaterialDeduction.objects.create(
                            stock_item=stock,
                            worker=worker,
                            quantity_taken=qty,
                            purpose=request.POST.get('purpose', 'General'),
                            authorized_by=request.user,
                        )
                        messages.success(
                            request, f"Deducted {qty}. New Balance: {stock.current_balance}")
                    else:
                        messages.error(request, "Insufficient Stock.")

            except Exception as e:
                messages.error(request, f"Error: {e}")

            return redirect('site_warehouse', site_id=site.id)

    # 📋 Gather Data
    stocks = MaterialStock.objects.filter(site=site)
    workers = SkilledWorker.objects.filter(site=site)
    invitation = Invitation.objects.filter(
        email=request.user.email, site=site, is_used=True).last()
    user_role = invitation.role_assigned if invitation else 'CONTRACTOR'
    is_boss = (site.company.owner == request.user) or (
        user_role == 'PROJECT_MANAGER')

    return render(request, 'site_management/site_warehouse.html', {
        'site': site,
        'stocks': stocks,
        'workers': workers,
        'is_boss': is_boss,
        'user_role': user_role,
    })


@login_required
def htmx_finance_summary(request, site_id):
    site = get_object_or_404(SiteLocation, id=site_id)

    # 🛡️ THE STRONG PERMISSION CHECK
    # 1. Get role from invitation if it exists
    invitation = Invitation.objects.filter(
        email=request.user.email, site=site, is_used=True).last()
    user_role = invitation.role_assigned if invitation else 'CONTRACTOR'

    # 2. Check: Are you the Company Owner OR the Project Manager?
    # ✅ This ensures YOU (the Boss) always pass the test
    is_boss = (site.company.owner == request.user) or (
        user_role == 'PROJECT_MANAGER')

    if not is_boss:
        return HttpResponse("<p class='text-red-500 font-black uppercase text-[10px]'>Access Denied</p>")

    # 💰 THE MATH
    # Ensure these utility functions are updated to use site.id correctly
    weekly_data = get_weekly_summary(site.id)
    monthly_data = get_monthly_summary(site.id)

    context = {
        'total_spent': monthly_data['total_payroll'],
        'weekly_total': weekly_data['total_payroll'],
        'total_workers': weekly_data['total_workers'],
        'site': site,
    }

    # 🚀 Return ONLY the cards to the dashboard container
    return render(request, 'site_management/htmx_components/finance_card.html', context)

# clok in


# Distance calculating


def calculate_distance(lat1, lon1, lat2, lon2):
    # 🌍 Earth radius in kilometers
    R = 6371.0

    # Convert degrees to radians
    lat1, lon1, lat2, lon2 = map(
        radians, [float(lat1), float(lon1), float(lat2), float(lon2)])

    # Haversine formula
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = sin(dlat / 2)**2 + cos(lat1) * cos(lat2) * sin(dlon / 2)**2
    c = 2 * asin(sqrt(a))

    # Return distance in Meters
    return c * R * 1000


# site_management/views.py

def htmx_clock_in(request, site_id):
    if request.method == "POST":
        site = get_object_or_404(SiteLocation, id=site_id)
        worker_id = request.POST.get('worker_id')
        worker = get_object_or_404(SkilledWorker, id=worker_id)
        user_lat = request.POST.get('lat')
        user_lng = request.POST.get('lng')

        # 1. 🚨 Security (Distance Check)
        if site.latitude and site.longitude and user_lat and user_lng:
            distance = calculate_distance(
                site.latitude, site.longitude, user_lat, user_lng)
            if distance > site.radius_meters:
                return HttpResponse(
                    f'<div class="p-2 bg-red-500/20 text-red-400 text-[10px] font-black uppercase rounded-xl animate-shake">'
                    f'🚨 Access Denied: {int(distance)}m away!</div>',
                    status=200
                )

        # 2. ✅ Save to Database FIRST
        StaffAttendance.objects.update_or_create(
            worker=worker,
            site=site,
            time_in__date=timezone.now().date(),
            defaults={
                'user': request.user,
                'time_in': timezone.now(),
                'daily_rate_at_time': worker.daily_rate
            }
        )

        # 3. 🔄 Calculate the lists SECOND (Now it includes the new clock-in)
        attendance_today = StaffAttendance.objects.filter(
            site=site,
            time_in__date=timezone.now().date()
        )

        present_worker_ids = list(
            attendance_today.filter(time_out__isnull=True).values_list(
                'worker_id', flat=True)
        )

        # 4. 🛡️ Role Check
        invitation = Invitation.objects.filter(
            email=request.user.email, site=site).last()
        user_role = invitation.role_assigned if invitation else 'CONTRACTOR'

        # 5. 🚀 Return the Button Partial
        response = render(request, 'site_management/htmx_components/worker_button.html', {
            'worker': worker,
            'site': site,
            'present_worker_ids': present_worker_ids,
            'attendance_today': attendance_today,
            'user_role': user_role,
        })

        # 🎯 STEP 2: Add the "Finance Update" signal to the header
        response['HX-Trigger'] = 'financeUpdate'

        return response

# site_management/views.py


def htmx_clock_out(request, site_id):
    if request.method == "POST":
        site = get_object_or_404(SiteLocation, id=site_id)
        worker_id = request.POST.get('worker_id')
        worker = get_object_or_404(SkilledWorker, id=worker_id)

        # 1. Find the active shift and close it
        attendance = StaffAttendance.objects.filter(
            worker_id=worker_id,
            site=site,
            time_out__isnull=True
        ).last()

        if attendance:
            attendance.time_out = timezone.now()
            attendance.save()

        # 2. 🔄 RECALCULATE for the UI
        attendance_today = StaffAttendance.objects.filter(
            site=site,
            time_in__date=timezone.now().date()
        )

        # We need this list so the 'Clock In' buttons reappear for these workers
        present_worker_ids = list(attendance_today.filter(
            time_out__isnull=True).values_list('worker_id', flat=True))

        # 🛡️ Get role for permissions
        invitation = Invitation.objects.filter(
            email=request.user.email, site=site).last()
        user_role = invitation.role_assigned if invitation else 'CONTRACTOR'

        response = render(request, 'site_management/htmx_components/worker_button.html', {
            'worker': worker,
            'site': site,
            'present_worker_ids': present_worker_ids,
            'attendance_today': attendance_today,
        })

        # 🎯 STEP 2: Add the signal
        response['HX-Trigger'] = 'financeUpdate'

        return response


@login_required
def daily_report(request, site_id):
    site = get_object_or_404(SiteLocation, id=site_id)
    if site.company.owner != request.user and not request.user.is_superuser:
        raise PermissionDenied()

    # 🟢 Use timezone.now() so it handles both Date and Time correctly
    now = timezone.now()
    today_date = now.date()

    # Materials moved strictly today
    materials = MaterialDeduction.objects.filter(
        stock_item__site=site,
        timestamp__date=today_date
    ).order_by('-timestamp')

    # Personnel clocked in strictly today
    attendance = StaffAttendance.objects.filter(
        site=site,
        time_in__date=today_date
    ).order_by('-time_in')

    workers = SkilledWorker.objects.filter(
        contractor=request.user).select_related('site')

    context = {
        'site': site,
        'site_id': site_id,
        'materials': materials,
        'attendance': attendance,
        'workers': workers,
        'today': today_date,  # For the "Log Date" display
        'now': now,          # For the "Live Time" display
    }
    # 🟢 HTMX MAGIC CHECK
    # if request.headers.get('HX-Request'):
    #     return render(request, 'site_management/partials/_material_rows.html', context)

    return render(request, 'site_management/daily_report.html', context)

# --- WORKER & SITE MANAGEMENT ---


# @login_required
@login_required
def add_site(request):
    if request.method == "POST":
        # ✅ FIX: Use '.company' instead of '.site_company_profile'
        # This matches the 'related_name' we set in your account/models.py
        user_company = request.user.company

        # 🏗️ 2. Now you can use it down here
        SiteLocation.objects.create(
            name=request.POST.get('name'),
            address=request.POST.get('address'),
            company=user_company  # ✅ Now this works perfectly!
        )
        messages.success(request, "New site location added successfully.")

    return redirect('index')


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

# views.py
# allworkers sers


def worker_search(request):
    search_text = request.GET.get('search', '').strip()

    # Filter by name OR category (role) for ALL users or just current company
    workers = SkilledWorker.objects.filter(
        Q(name__icontains=search_text) |
        Q(category__icontains=search_text)
    )

    # Return ONLY the results part, not the whole page!
    return render(request, 'site_management/htmx_components/worker_list_results.html', {'workers': workers})


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
    # 1. ✅ THE SECURITY FIX: Use the Company Owner link
    log = get_object_or_404(
        StaffAttendance,
        id=attendance_id,
        site__company__owner=request.user  # 👈 Changed from site__contractor
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
            f"Payment for {log.worker.name} finalized: {log.payment_reference}"
        )
    else:
        messages.info(request, "This shift has already been settled.")

    # 4. Redirect back to the worker's profile
    return redirect('worker_profile', slug=log.worker.slug)


@login_required
def invite_staff(request):
    if request.method == "POST":
        email = request.POST.get('email')
        role = request.POST.get('role')
        site_id = request.POST.get('site_id')
        site = get_object_or_404(SiteLocation, id=site_id)

        # 🛡️ THE UPDATED PERMISSION GATE
        # 1. Check the Company Owner (The Boss)
        # ✅ We use site.company.owner now
        is_owner = (site.company.owner == request.user)

        # 2. Check if the user is a Project Manager for THIS site
        is_pm = Invitation.objects.filter(
            email=request.user.email,
            site=site,
            role_assigned='PROJECT_MANAGER',
            is_used=True
        ).exists()

        # 🔥 Block anyone who isn't the Boss or a PM
        if not (is_owner or is_pm):
            messages.error(
                request, "Access Denied: Only Company Owners and PMs can invite staff.")
            return redirect('site_dashboard', site_id=site.id)

        # 3. Create the Invite record
        import uuid
        token = uuid.uuid4()
        Invitation.objects.create(
            email=email,
            site=site,
            role_assigned=role,
            invited_by=request.user,
            token=token
        )

        # 4. Build the Link
        # domain = "https://codasite.onrender.com"
        domain = "http://127.0.0.1:8000"
        invite_link = f"{domain}/account/register/?token={token}"

        # 5. The Dispatch
        subject = f"Invitation to join {site.name} on CodaSite"
        message = f"""
        Hello,
        
        You have been invited by {request.user.username} to join the project at {site.name} 
        as a {role.replace('_', ' ').title()}.
        
        Please click the link below to set up your account:
        {invite_link}
        
        Best regards,
        InnoCoda Team
        """

        try:
            from django.core.mail import send_mail
            from django.conf import settings
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

        return redirect('profile')

# Restock


@login_required
def restock_history(request, site_id):
    """View the full visual proof log for all materials on a specific site."""
    site = get_object_or_404(SiteLocation, id=site_id)

    # 🛡️ ONE SECURITY CHECK: Is this user allowed to be here?
    is_pm = Invitation.objects.filter(
        email=request.user.email, site=site).exists()
    # ✅ NEW (Through the Company)
    if site.company.owner != request.user and not request.user.is_superuser:
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

    # ✅ FIX: Permission Check
    # We look through the company to find the owner (You/Innocoda)
    if site.company.owner != request.user and not request.user.is_superuser:
        # (Optional: Add your Project Manager invitation check here)
        from django.core.exceptions import PermissionDenied
        raise PermissionDenied()

    # 🟢 THE OPTIMIZED QUERY
    # This remains the same—it's already very efficient!
    usage_logs = MaterialDeduction.objects.filter(
        stock_item__site=site
    ).select_related('worker', 'stock_item', 'authorized_by').order_by('-timestamp')

    return render(request, 'site_management/material_usage_report.html', {
        'site': site,
        'usage_logs': usage_logs,
        'company': site.company,  # ✅ Added for branding in the report
    })
# Profiles


# Profiles

# @login_required
# def profile_view(request):
#     user = request.user

#     # 1. Determine Role & Site Assignment
#     invitation = Invitation.objects.filter(
#         email=user.email, is_used=True).last()
#     user_role = invitation.role_assigned if invitation else 'CONTRACTOR'

#     # 2. Get Branding (Logo/Business Name)
#     # If they are staff, we pull the profile of the person who invited them
#     if invitation:
#         company_profile =Company.objects.filter(
#             contractor=invitation.invited_by).first()
#     else:
#         company_profile = Company.objects.filter(
#             contractor=user).first()

#     context = {
#         'user_role': user_role,
#         'invitation': invitation,
#         'company_profile': company_profile,
#         'sites_count': SiteLocation.objects.filter(contractor=user).count() if user_role == 'CONTRACTOR' else 0,
#         # For staff, show the one site they are assigned to
#         'assigned_site': invitation.site if invitation else None,
#     }

#     return render(request, 'site_management/profile.html', context)


# @login_required
# def update_company_logo(request):
#     if request.method == "POST" and request.FILES.get('logo'):
#         # Get or create the profile
#         profile, created = CompanyProfile.objects.get_or_create(
#             contractor=request.user)
#         profile.logo = request.FILES['logo']
#         profile.save()
#         messages.success(request, "Logo updated successfully!")
#     return redirect('profile')


@login_required
def profile_view(request):
    user = request.user
    invitation = Invitation.objects.filter(
        email=user.email, is_used=True).last()
    user_role = invitation.role_assigned if invitation else 'CONTRACTOR'

    # ✅ Change CompanyProfile -> Company | contractor -> owner
    if invitation:
        company_profile = Company.objects.filter(
            owner=invitation.invited_by).first()
    else:
        company_profile = Company.objects.filter(owner=user).first()

    context = {
        'user_role': user_role,
        'invitation': invitation,
        'company_profile': company_profile,
        'sites_count': SiteLocation.objects.filter(company=company_profile).count() if company_profile else 0,
        'assigned_site': invitation.site if invitation else None,
    }
    return render(request, 'site_management/profile.html', context)


@login_required
def update_company_logo(request):
    if request.method == "POST" and request.FILES.get('logo'):
        # ✅ FIX: Get or create using the new 'Company' model
        profile, created = Company.objects.get_or_create(
            owner=request.user)
        profile.logo = request.FILES['logo']
        profile.save()
        messages.success(request, "Logo updated successfully!")
    return redirect('profile')


@login_required
def update_company_name(request):
    if request.method == "POST":
        name = request.POST.get('business_name')

        # ✅ FIX: Use 'Company' and 'owner' instead of 'CompanyProfile' and 'contractor'
        # Also use 'name' instead of 'business_name' to match your account/models.py
        profile, created = Company.objects.get_or_create(
            owner=request.user
        )
        profile.name = name
        profile.save()

        messages.success(request, "Company name updated!")
    return redirect('profile')

# @login_required
# def update_company_name(request):
#     if request.method == "POST":
#         name = request.POST.get('business_name')
#         profile, created = CompanyProfile.objects.get_or_create(
#             contractor=request.user)
#         profile.business_name = name
#         profile.save()
#         messages.success(request, "Company name updated!")
#     return redirect('profile')


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
