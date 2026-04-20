import cloudinary.uploader  # Make sure this is imported!
from django.db.models import Q
from .reports import get_weekly_summary, generate_pdf_report, send_resend_audit_email
from django.shortcuts import get_object_or_404, render
from django.utils.safestring import mark_safe
from django.shortcuts import redirect
from datetime import timedelta  # Add this at the top
from decimal import Decimal  # 👈 Ensure this is at the top of your file!
from .models import SiteLocation, StaffAttendance, MaterialDeduction

from django.conf import settings
# Ensure these are at the top
#

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
import resend
# site_management/views.py (Top of the file)

from .reports import (
    get_daily_summary,
    get_weekly_summary,
    get_monthly_summary,
    generate_pdf_report,
    send_resend_audit_email  # 🚀 THIS IS THE ONE WE NEED!
)
from django.core.mail import EmailMessage
from decimal import Decimal
from .forms import WorkerPayForm
from .utils import get_weekly_summary, get_monthly_summary


from django.db.models import Q, F
# Distance calculating
from math import radians, cos, sin, asin, sqrt
from django.http import HttpResponse
from decimal import Decimal
# company profile
import json
from django.http import HttpResponse


@login_required
def index(request):
    # 🧼 CLEANUP: Remove the active site ID from the session
    # if 'active_site_id' in request.session:
    #     del request.session['active_site_id']
    #     request.session.modified = True

    #     today = timezone.now().date()

    # 🏢 1. Identify the Company

    # 🧼 Session Cleanup
    if 'active_site_id' in request.session:
        del request.session['active_site_id']
        request.session.modified = True

    # 🏢 1. Identify the Company (The Safe Way)
    # Check if they own a company
    user_company = getattr(request.user, 'company', None)

    # If they DON'T own one, they might be an invited staff member
    if not user_company:
        invitation = Invitation.objects.filter(
            email=request.user.email, is_used=True).first()
        if invitation:
            user_company = invitation.site.company

    # 🔥 Still no company? They haven't set up anything yet.
    if not user_company:
        # If it's a fresh Contractor, they need to create a company first
        return redirect('profile')  # Or wherever you handle company creation

    # 🏗️ 2. BASE QUERIES (Now works for everyone!)
    # If it's a staff member, they should only see the sites they are invited to
    if hasattr(request.user, 'company'):
        user_sites = SiteLocation.objects.filter(company=user_company)
    else:
        # Storekeepers only see their assigned site(s)
        assigned_site_ids = Invitation.objects.filter(
            email=request.user.email, is_used=True
        ).values_list('site_id', flat=True)
        user_sites = SiteLocation.objects.filter(id__in=assigned_site_ids)

    sites = user_sites.order_by("-created_at")

    # try:
    #     user_company = request.user.company
    # except AttributeError:
    #     messages.error(request, "Access Denied: No Company Profile found.")
    #     return redirect('login')

    # # 🏗️ 2. BASE QUERIES
    # user_sites = SiteLocation.objects.filter(company=user_company)
    # sites = user_sites.order_by("-created_at")

    # 📦 3. GLOBAL INVENTORY ENGINE (Sum of everything)
    # This groups every material by name and unit, then adds up the total balance
    # total_cement = MaterialStock.objects.filter(
    #     site__company=user_company,
    #     item_name__icontains='cement'
    # ).aggregate(total=Sum('current_balance'))['total'] or 0
    # global_inventory = MaterialStock.objects.filter(
    #     site__company=user_company
    # ).values('item_name', 'unit').annotate(
    #     total_balance=Sum('current_balance')
    # ).order_by('item_name')

    # 📦 3. GLOBAL INVENTORY ENGINE (Sum of everything)
    # Only calculate global stats if the user IS the company owner
    if hasattr(request.user, 'company'):
        # The Boss sees everything across all sites
        total_cement = MaterialStock.objects.filter(
            site__company=user_company,
            item_name__icontains='cement'
        ).aggregate(total=Sum('current_balance'))['total'] or 0

        global_inventory = MaterialStock.objects.filter(
            site__company=user_company
        ).values('item_name', 'unit').annotate(
            total_balance=Sum('current_balance')
        ).order_by('item_name')

        # Critical low stock (Full Business View)
        low_stock_items = MaterialStock.objects.filter(
            site__company=user_company,
            current_balance__lt=F('minimum_required')
        ).select_related('site').order_by('current_balance')
    else:
        # Storekeepers see 0/None for global stats to keep data private
        total_cement = 0
        global_inventory = None
        low_stock_items = None

    # 🚨 CRITICAL LOW STOCK (Across all sites)
    low_stock_items = MaterialStock.objects.filter(
        site__company=user_company,
        current_balance__lt=F('minimum_required')
    ).select_related('site').order_by('current_balance')

    context = {
        'sites': sites,
        'global_inventory': global_inventory,  # ⬅️ This is the "Know Everything" data
        'low_stock_items': low_stock_items,
        'company': user_company,
        'total_cement': total_cement,
    }

    # --- 🎯 THE RESPONSE LOGIC ---

    # Check if this is a partial update for the dashboard feed
    if request.headers.get('HX-Target') == 'dashboard-live-zone':
        return render(request, 'site_management/htmx_components/dashboard_feed.html', context)

    # 1. Prepare the full index response
    response = render(request, 'site_management/index.html', context)

    # 🚀 2. THE MAGIC CLEANUP: Wipe the Live Ops button instantly
    if request.htmx:
        # We send an EMPTY div with the OOB trigger to "kill" the button in the Nav
        cleanup_html = '<div id="live-ops-anchor" hx-swap-oob="true"></div>'
        response.write(mark_safe(cleanup_html))

    return response


def dashboard_feed_component(request):
    # ONLY get the data for the small feed, nothing else!
    recent_arrivals = MaterialRestockLog.objects.filter(
        timestamp__date=timezone.now().date()
    ).order_by('-timestamp')[:5]

    return render(request, 'site_management/htmx_components/dashboard_feed.html', {
        'recent_arrivals': recent_arrivals
    })


@login_required
@transaction.atomic
def site_dashboard(request, site_id):
    # ⚓ Anchor: Session locking
    request.session['active_site_id'] = site_id
    today = timezone.now().date()  # 📅 Added this back so Step 6 doesn't crash

    # 🏢 1. Identify the Site & Company
    site = get_object_or_404(SiteLocation, id=site_id)
    # 🎯 Get the company through the site, not the user!
    company = site.company

    # 🛡️ 2. THE PERMISSION GATE
    is_owner = (company.owner == request.user)
    invitation = Invitation.objects.filter(
        email=request.user.email, site=site, is_used=True).last()

    # 🎯 THE FIX: Fetch workers that belong to this company but are not on THIS site
    # This allows you to "redeploy" workers from other sites or your general pool
    global_workers_pool = SkilledWorker.objects.filter(
        company=company
    ).exclude(site=site)

    if not is_owner and not invitation:
        messages.error(
            request, "Access Denied: You are not assigned to this site.")
        return redirect('profile')

    # 3. Determine Role
    user_role = invitation.role_assigned if invitation else 'CONTRACTOR'

    # 🛡️ If they own the company OR their typed role is PM, they are the boss
    is_boss = is_owner or user_role == 'PROJECT_MANAGER'
    # user_role = invitation.role_assigned if invitation else 'CONTRACTOR'
    # is_boss = user_role in ['CONTRACTOR', 'PROJECT_MANAGER']

    # 4. Scoped Pools
    workers = SkilledWorker.objects.filter(site=site)
    stocks = MaterialStock.objects.filter(site=site)

    # 🌍 GLOBAL POOL (Safe for everyone)
    # We use 'company' (the one owning the site) instead of 'request.user.company'
    global_workers_pool = SkilledWorker.objects.filter(
        contractor=company.owner).exclude(site=site)

    # 5. HANDLE PERSONNEL ACTIONS (POST)

    if request.method == "POST":
        # --- 1. DEPLOY FROM GLOBAL POOL ---
        if 'deploy_worker' in request.POST:
            worker_id = request.POST.get('worker_id')

            # 🛡️ THE FIX: Look for 'contractor=company.owner' instead of 'company=company'
            worker = get_object_or_404(
                SkilledWorker, id=worker_id, contractor=company.owner)

            # Optional: Override role/rate for this specific site
            new_role = request.POST.get('update_category')
            new_rate = request.POST.get('update_rate')

            worker.site = site  # 🏗️ Move them to this site
            if new_role:
                worker.category = new_role
            if new_rate:
                worker.daily_rate = Decimal(new_rate)

            worker.save()
            messages.success(request, f"{worker.name} deployed to {site.name}")

        # --- 2. REGISTER NEW WORKER DIRECTLY TO SITE ---
        elif 'register_worker' in request.POST:
            id_num = request.POST.get('id_number', '').strip()

            # 🛡️ GHOST CHECK: Prevent duplicate IDs in the company
            if SkilledWorker.objects.filter(company=company, id_number=id_num).exists():
                messages.error(
                    request, "Identity Error: Personnel already exists in registry.")
            else:
                SkilledWorker.objects.create(
                    company=company,
                    site=site,  # 📍 Direct deployment
                    name=request.POST.get('name'),
                    category=request.POST.get('category'),
                    id_number=id_num,
                    phone=request.POST.get('phone'),
                    daily_rate=Decimal(request.POST.get(
                        'pay_frequency') or '0.00'),
                    profile_picture=request.FILES.get('profile_picture')
                )
                messages.success(
                    request, f"New Personnel enrolled and deployed to {site.name}.")

        # --- 3. MASS RATE UPDATE ---
        elif 'update_all_rates' in request.POST:
            for worker in workers:
                rate_key = f"rate_{worker.id}"
                if rate_key in request.POST:
                    worker.daily_rate = Decimal(request.POST.get(rate_key))
                    worker.save()
            messages.success(request, "Labor rates synchronized.")

        return redirect('site_dashboard', site_id=site.id)

    # 6. GATHER DATA
    weekly_data = get_weekly_summary(site.id)
    monthly_data = get_monthly_summary(site.id)
    attendance_today = StaffAttendance.objects.filter(
        site=site, time_in__date=today)
    present_worker_ids = list(attendance_today.filter(
        time_out__isnull=True).values_list('worker_id', flat=True))

    # --- 🎯 THE RESPONSE ---
    context = {
        'site': site,
        'company': company,
        'is_boss': is_boss,
        'workers': workers,
        'active_site_id': site_id,
        'stocks': stocks,
        'attendance_today': attendance_today,
        'present_worker_ids': present_worker_ids,
        'global_workers_pool': global_workers_pool,
        'user_role': user_role,
        'total_spent': monthly_data['total_payroll'],
        'weekly_total': weekly_data['total_payroll'],
        'total_workers': weekly_data['total_workers'],
    }

    response = render(request, 'site_management/site_dashboard.html', context)

    if request.htmx:
        # (Keep your Live Ops Button logic here)
        button_html = f'''...'''
        response.write(mark_safe(button_html))

    return response


@login_required
def site_warehouse(request, site_id):
    # 🏢 1. Fetch the site FIRST (Don't check company=user_company here)
    site = get_object_or_404(SiteLocation, id=site_id)

    # 🛡️ 2. THE PERMISSION GATE
    # Check if the user is the Boss
    is_owner = (site.company.owner == request.user)

    # Check if the user is an invited staff member for THIS site
    invitation = Invitation.objects.filter(
        email=request.user.email,
        site=site,
        is_used=True
    ).last()

    # 🔥 BLOCK ACCESS: If they aren't the Boss AND they aren't invited here
    if not is_owner and not invitation:
        messages.error(
            request, "Access Denied: You are not assigned to this warehouse.")
        return redirect('profile')

    # 3. Determine the User's Role for the UI
    user_role = invitation.role_assigned if invitation else 'CONTRACTOR'
    is_boss = is_owner or (user_role == 'PROJECT_MANAGER')

    # --- THE LOGIC ENGINE ---

    if request.method == "POST":
        if 'add_stock' in request.POST:
            try:
                qty = Decimal(request.POST.get('quantity') or '0.00')
                item_name = request.POST.get('item_name', '').strip().upper()
                unit = request.POST.get('unit', '').strip()
                img_file = request.FILES.get('evidence_image')
                vid_file = request.FILES.get('evidence_video')

                # ⚡ FAST FIX: Do the heavy internet upload OUTSIDE the database lock!
                processed_vid = None
                if vid_file:
                    import cloudinary.uploader
                    upload_result = cloudinary.uploader.upload(
                        vid_file,
                        resource_type="video",
                        folder="codasite_audits",
                        transformation=[
                            {"overlay": "CodaSite_logo_mldgwi", "gravity": "south_east",
                                "x": 20, "y": 20, "width": 80, "opacity": 90}
                        ]
                    )
                    processed_vid = upload_result['public_id']

                # 🔒 NOW we lock the database for exactly 0.01 seconds to do the math
                with transaction.atomic():
                    stock, _ = MaterialStock.objects.select_for_update().get_or_create(
                        site=site, item_name=item_name, defaults={'unit': unit}
                    )
                    stock.current_balance += qty
                    if img_file:
                        stock.evidence_image = img_file
                    if processed_vid:
                        stock.evidence_video = processed_vid
                    stock.save()

                    MaterialRestockLog.objects.create(
                        stock_item=stock, site=site, quantity_added=qty,
                        evidence_image=img_file,
                        evidence_video=processed_vid if processed_vid else None
                    )

                messages.success(
                    request, f"Received {qty} {unit} of {item_name}.")
            except Exception as e:
                messages.error(request, f"Intake Error: {e}")

        # --- B. ISSUE MATERIAL (DEDUCTION) ---
        elif 'issue_material' in request.POST:
            stock_id = request.POST.get('stock_item')
            worker_id = request.POST.get('worker_id')
            qty_input = request.POST.get('quantity')

            try:
                qty = Decimal(qty_input or 0)
                worker = get_object_or_404(SkilledWorker, id=worker_id)
                stock = get_object_or_404(
                    MaterialStock, id=stock_id, site=site)

                MaterialDeduction.objects.create(
                    stock_item=stock,
                    worker=worker,
                    quantity_taken=qty,
                    purpose=request.POST.get('purpose', 'General Site Use'),
                    authorized_by=request.user,
                )
                messages.success(
                    request, f"✅ DISPATCHED: {qty} {stock.unit} of {stock.item_name} to {worker.name}.")
            except ValidationError as e:
                error_msg = e.message_dict.get('__all__', [str(e)])[0]
                messages.error(request, error_msg)
            except Exception as e:
                messages.error(request, "A system error occurred.")

        if request.htmx:
            stocks = MaterialStock.objects.filter(site=site)
            return render(request, 'site_management/partials/stock_list_partial.html', {
                'stocks': stocks,
                'site': site,
                'messages': messages.get_messages(request)
            })

        return redirect('site_warehouse', site_id=site.id)

    # 📋 Normal Page Load
    stocks = MaterialStock.objects.filter(site=site)
    workers = SkilledWorker.objects.filter(site=site)

    context = {
        'site': site,
        'stocks': stocks,
        'workers': workers,
        'is_boss': is_boss,
        'user_role': user_role,
    }
    return render(request, 'site_management/site_warehouse.html', context)


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


def htmx_clock_in(request, site_id):
    if request.method == "POST":
        site = get_object_or_404(SiteLocation, id=site_id)
        worker_id = request.POST.get('worker_id')
        worker = get_object_or_404(SkilledWorker, id=worker_id)
        user_lat = request.POST.get('lat')
        user_lng = request.POST.get('lng')

        # 1. 🛡️ SECURITY GATE: Check if they already finished a shift today
        already_finished = StaffAttendance.objects.filter(
            worker=worker,
            site=site,
            time_in__date=timezone.now().date(),
            time_out__isnull=False
        ).exists()

        if already_finished:
            return HttpResponse(
                f'<div class="p-3 bg-orange-500/10 text-orange-400 text-[10px] font-black uppercase rounded-xl border border-orange-500/20 animate-shake">'
                f'🚨 SECURITY: Shift already completed. Access denied until tomorrow!</div>',
                status=200
            )

        # 2. 🛰️ GPS RADIUS CHECK
        if site.latitude and site.longitude and user_lat and user_lng:
            distance = calculate_distance(
                site.latitude, site.longitude, user_lat, user_lng)
            if distance > site.radius_meters:
                return HttpResponse(
                    f'<div class="p-2 bg-red-500/20 text-red-400 text-[10px] font-black uppercase rounded-xl">🚨 Distance Error: {int(distance)}m away</div>',
                    status=200
                )

        # 3. ✅ CLOCK IN (Update or Create)
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

        # 🔄 Recalculate for OOB updates
        attendance_today = StaffAttendance.objects.filter(
            site=site, time_in__date=timezone.now().date()
        ).select_related('worker')

        present_worker_ids = list(attendance_today.filter(
            time_out__isnull=True).values_list('worker_id', flat=True))

        invitation = Invitation.objects.filter(
            email=request.user.email, site=site).last()
        user_role = invitation.role_assigned if invitation else 'CONTRACTOR'

        # 🚀 Response with Button + OOB Counter + OOB List
        response = render(request, 'site_management/htmx_components/worker_button.html', {
            'worker': worker,
            'site': site,
            'present_worker_ids': present_worker_ids,
            'attendance_today': attendance_today,
            'user_role': user_role,
        })

        # Attach OOB Counter
        onsite_count = len(present_worker_ids)
        total_workers = SkilledWorker.objects.filter(site=site).count()
        onsite_counter_html = f'''
            <h3 id="onsite-counter" hx-swap-oob="true" class="text-4xl font-black text-white tracking-tighter">
                {onsite_count} <span class="text-white/20 text-2xl">/ {total_workers}</span>
            </h3>
        '''
        from django.utils.safestring import mark_safe
        response.content = response.content + \
            mark_safe(onsite_counter_html).encode()
        response['HX-Trigger'] = 'financeUpdate'

        return response


def htmx_clock_out(request, site_id):
    if request.method == "POST":
        site = get_object_or_404(SiteLocation, id=site_id)
        worker_id = request.POST.get('worker_id')
        worker = get_object_or_404(SkilledWorker, id=worker_id)

        # 1. 🏁 Find the active shift for today and close it
        attendance = StaffAttendance.objects.filter(
            worker_id=worker_id,
            site=site,
            time_out__isnull=True
        ).last()

        if attendance:
            attendance.time_out = timezone.now()
            attendance.save()

        # 2. 🔄 RECALCULATE Attendance Lists (Instant UI Sync)
        attendance_today = StaffAttendance.objects.filter(
            site=site,
            time_in__date=timezone.now().date()
        ).select_related('worker')

        # Generate list of who is still currently on site
        present_worker_ids = list(attendance_today.filter(
            time_out__isnull=True
        ).values_list('worker_id', flat=True))

        # 🛡️ Role-based permission check
        invitation = Invitation.objects.filter(
            email=request.user.email, site=site
        ).last()
        user_role = invitation.role_assigned if invitation else 'CONTRACTOR'

        # 3. 🚀 Render the Worker Button Partial
        response = render(request, 'site_management/htmx_components/worker_button.html', {
            'worker': worker,
            'site': site,
            'present_worker_ids': present_worker_ids,
            'attendance_today': attendance_today,
            'user_role': user_role,
        })

        # 🎯 STEP 4: Prepare the OOB Counter Update
        onsite_count = len(present_worker_ids)
        total_workers = SkilledWorker.objects.filter(site=site).count()

        onsite_counter_html = f'''
            <h3 id="onsite-counter" hx-swap-oob="true" class="text-4xl font-black text-white tracking-tighter">
                {onsite_count} <span class="text-white/20 text-2xl">/ {total_workers}</span>
            </h3>
        '''

        # 🧩 Attach the OOB HTML to the main response
        # Using .encode() to match response content-type
        response.content = response.content + \
            mark_safe(onsite_counter_html).encode()

        # ⚡ STEP 5: Add the signal to refresh finance cards
        response['HX-Trigger'] = 'financeUpdate'

        return response


@login_required
def daily_report(request, site_id):
    site = get_object_or_404(SiteLocation, id=site_id)

    # 🛡️ Permission Check... (Keep your existing check)

    now = timezone.now()
    today_date = now.date()

    # 🚀 SPEED UP MATERIALS: Join stock_item and worker in 1 query
    materials = MaterialDeduction.objects.filter(
        stock_item__site=site,
        timestamp__date=today_date
    ).select_related('stock_item', 'worker').order_by('-timestamp')

    # 🚀 SPEED UP ATTENDANCE: Join worker in 1 query
    attendance = StaffAttendance.objects.filter(
        site=site,
        time_in__date=today_date
    ).select_related('worker').order_by('-time_in')

    # 🚀 SPEED UP WORKERS
    workers = SkilledWorker.objects.filter(
        contractor=request.user
    ).select_related('site')

    context = {
        'site': site,
        'site_id': site_id,
        'materials': materials,
        'attendance': attendance,
        'workers': workers,
        'today': today_date,
        'now': now,
    }

    # 🎯 HTMX Partial Optimization
    if request.htmx:
        return render(request, 'site_management/daily_report.html', context)

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
# 🚨 REMOVED @transaction.atomic from here so Cloudinary doesn't crash the database!
def add_worker(request, site_id):
    site = get_object_or_404(SiteLocation, id=site_id)
    company = site.company

    is_owner = (company.owner == request.user)
    is_invited_pm = Invitation.objects.filter(
        email=request.user.email, site=site, is_used=True, role_assigned='PROJECT_MANAGER'
    ).exists()

    if not (is_owner or is_invited_pm):
        messages.error(
            request, "SECURITY ALERT: You are not authorized to enroll personnel on this site.")
        return redirect('profile')  # Kick them completely out of the site

    if request.method == "POST":
        id_num = request.POST.get('id_number', '').strip()
        phone_num = request.POST.get('phone', '').strip()

        # --- 🛑 1. THE SECURITY VAULT: FRONT DOOR CHECKS ---
        profile_picture = request.FILES.get('profile_picture')
        lat = request.POST.get('enrollment_lat')
        lon = request.POST.get('enrollment_long')

        if not profile_picture:
            messages.error(
                request, "CRITICAL: Live Biometric photo is missing. Request rejected.")
            return redirect('site_dashboard', site_id=site_id)

        if not lat or not lon:
            messages.error(
                request, "CRITICAL: GPS Coordinates missing. Ghost worker registration blocked.")
            return redirect('site_dashboard', site_id=site_id)

        # Gatekeeper Check (Prevent Duplicates)
        if SkilledWorker.objects.filter(Q(id_number=id_num) | Q(phone=phone_num)).exists():
            messages.error(
                request, "Identity Error: Personnel already exists in Global Registry.")
            return redirect('site_dashboard', site_id=site_id)

        try:
            # 🟢 CAPTURE DAILY RATE (Matching your HTML input name 'pay_frequency')
            raw_rate = request.POST.get('pay_frequency')
            daily_rate = Decimal(raw_rate) if raw_rate else Decimal('0.00')

            # --- ⚡ 2. TIER-1 OPTIMIZATION: UPLOAD TO CLOUDINARY OUTSIDE THE LOCK ---
            # We do the heavy lifting before touching the database
            upload_result = cloudinary.uploader.upload(
                profile_picture,
                resource_type="image",
                folder="codasite_personnel",
            )
            # Get the Cloudinary ID
            secure_image_url = upload_result['public_id']

            # --- 🔒 3. NOW LOCK THE DATABASE FOR 0.01 SECONDS TO SAVE ---
            with transaction.atomic():
                worker = SkilledWorker.objects.create(
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
                    pay_frequency="Daily",  # Hardcoded since the HTML input was used for the rate
                    daily_rate=daily_rate,
                    profile_picture=secure_image_url  # Save the secure Cloudinary image!
                )

                # NOTE: If you ever add gps_lat and gps_long to your SkilledWorker model,
                # you can save `lat` and `lon` variables right here!

            messages.success(
                request, f"New Personnel '{worker.name}' enrolled securely with Biometrics and GPS.")

        except Exception as e:
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
        # domain = "http://127.0.0.1:8000"
        domain = "https://codasite.com.ng"
        invite_link = f"{domain}/account/register/?token={token}"

        # 5. The Dispatch
        # 5. THE DISPATCH (Using Resend SDK to bypass Django's local SMTP)

        from django.conf import settings

        resend.api_key = settings.RESEND_API_KEY

        # We use HTML here to make the invite look like a "Super App"
        params = {
            "from": settings.DEFAULT_FROM_EMAIL,
            "to": [email],
            "subject": f"🏗️ Invitation: Join {site.name} on CodaSite",
            "html": f"""
                <div style="font-family: sans-serif; padding: 20px; color: #1a202c; border: 1px solid #e2e8f0; border-radius: 12px;">
                    <h2 style="color: #0d9488;">InnoCoda Studio</h2>
                    <p>Hello,</p>
                    <p>You have been invited by <strong>{request.user.username}</strong> to join the project at <strong>{site.name}</strong> 
                    as a <strong>{role.replace('_', ' ').title()}</strong>.</p>
                    <p>Click the button below to set up your account and start managing site materials:</p>
                    <div style="margin: 30px 0;">
                        <a href="{invite_link}" style="display: inline-block; padding: 14px 28px; background-color: #0d9488; color: white; text-decoration: none; border-radius: 8px; font-weight: bold; font-size: 16px;">Accept Invitation</a>
                    </div>
                    <p style="margin-top: 20px; font-size: 12px; color: #718096;">If the button doesn't work, copy this link into your browser: <br>{invite_link}</p>
                    <hr style="border: 0; border-top: 1px solid #edf2f7; margin: 20px 0;">
                    <p style="font-size: 10px; color: #a0aec0;">CodaSite - Construction Management simplified.</p>
                </div>
            """
        }

        try:
            # 🚀 This calls Resend directly, ignoring the 'WinError 10061' error
            resend.Emails.send(params)
            messages.success(
                request, f"Invitation sent successfully to {email}!")
        except Exception as e:
            # If the API key is missing or internet is down, we catch it here
            messages.error(request, f"Email failed to send. Error: {e}")

        return redirect('profile')

# Restock


# @login_required
# def restock_history(request, site_id):
#     """View the full visual proof log for all materials on a specific site."""
#     site = get_object_or_404(SiteLocation, id=site_id)

#     # 🛡️ ONE SECURITY CHECK: Is this user allowed to be here?
#     is_pm = Invitation.objects.filter(
#         email=request.user.email, site=site).exists()
#     # ✅ NEW (Through the Company)
#     if site.company.owner != request.user and not request.user.is_superuser:
#         raise PermissionDenied()

#     # 🟢 THE HISTORY LOGS (Every delivery event)
#     # We use select_related to get the name and unit from the Stock model
#     history = MaterialRestockLog.objects.filter(
#         site=site).select_related('stock_item').order_by('-timestamp')

#     # 🟢 THE CURRENT TOTALS (For the top of the page if needed)
#     stocks = MaterialStock.objects.filter(site=site).order_by('-last_updated')

#     return render(request, 'site_management/restock_history.html', {
#         'site': site,
#         'history': history,
#         'stocks': stocks
#     })
@login_required
def restock_history(request, site_id):
    """View the full visual proof log for all materials on a specific site."""
    site = get_object_or_404(SiteLocation, id=site_id)

    # 🛡️ THE PERMISSION GATE
    is_owner = (site.company.owner == request.user)
    # Check if user is an invited staff member (PM, Storekeeper, etc.)
    invitation = Invitation.objects.filter(
        email=request.user.email, site=site, is_used=True).exists()

    if not is_owner and not invitation and not request.user.is_superuser:
        raise PermissionDenied()

    # 🟢 THE HISTORY LOGS
    history = MaterialRestockLog.objects.filter(
        site=site).select_related('stock_item').order_by('-timestamp')
    stocks = MaterialStock.objects.filter(site=site).order_by('-last_updated')

    return render(request, 'site_management/restock_history.html', {
        'site': site,
        'history': history,
        'stocks': stocks
    })

# @login_required
# def material_usage_report(request, site_id):
#     user_company = request.user.company
#     site = get_object_or_404(SiteLocation, id=site_id, company=user_company)

#     # 🛡️ Permission Check (Including Project Managers)
#     invitation = Invitation.objects.filter(
#         email=request.user.email, site=site, is_used=True).last()
#     is_authorized = (site.company.owner == request.user) or (
#         invitation and invitation.role_assigned == 'PROJECT_MANAGER')

#     if not is_authorized and not request.user.is_superuser:
#         from django.core.exceptions import PermissionDenied
#         raise PermissionDenied()

#     # 🟢 THE OPTIMIZED QUERY
#     usage_logs = MaterialDeduction.objects.filter(
#         stock_item__site=site
#     ).select_related('worker', 'stock_item', 'authorized_by').order_by('-timestamp')

#     context = {
#         'site': site,
#         'usage_logs': usage_logs,
#         'company': site.company,
#     }

#     # 🎯 THE HTMX SWITCH (The Engine)
#     if request.htmx:
#         # This returns ONLY the table content, no navbar, no sidebar.
#         return render(request, 'site_management/partials/usage_report_partial.html', context)

#     # Normal full page load if they refresh or type the URL
#     return render(request, 'site_management/material_usage_report.html', context)


@login_required
def material_usage_report(request, site_id):
    """View detailed usage and deductions."""
    site = get_object_or_404(SiteLocation, id=site_id)

    # 🛡️ Permission Gate
    is_owner = (site.company.owner == request.user)
    invitation = Invitation.objects.filter(
        email=request.user.email, site=site, is_used=True).exists()

    if not is_owner and not invitation:
        raise PermissionDenied()

    # 🟢 Syncing usage_logs for your template
    usage_logs = MaterialDeduction.objects.filter(
        stock_item__site=site
    ).select_related('worker', 'stock_item', 'authorized_by').order_by('-timestamp')

    # 🎯 FIX THE FILENAME HERE:
    # It must match the file C:\...\site_management\material_usage_report.html
    return render(request, 'site_management/material_usage_report.html', {
        'site': site,
        'usage_logs': usage_logs,
        'company': site.company
    })

# Profiles


# @login_required
# def profile_view(request):
#     user = request.user

#     # 1. Determine Role & Site Assignment
#     invitation = Invitation.objects.filter(
#         email=user.email, is_used=True).last()
#     user_role = invitation.role_assigned if invitation else 'CONTRACTOR'

#     # 2. Get branding (Using the Invitation logic we synced)
#     if invitation:
#         company_profile = Company.objects.filter(
#             owner=invitation.invited_by).first()
#     else:
#         company_profile = Company.objects.filter(owner=user).first()

#     context = {
#         'user_role': user_role,
#         'invitation': invitation,
#         'company_profile': company_profile,
#         'company': company_profile,  # 🎯 Keep both for template safety
#         'sites_count': SiteLocation.objects.filter(company=company_profile).count() if company_profile else 0,
#         'assigned_site': invitation.site if invitation else None,
#     }

#     return render(request, 'site_management/profile.html', context)
@login_required
def profile_view(request):
    user = request.user

    # 1. Look for the 'Accepted' invitation for this specific email
    # We use .filter().last() to get the most recent one if they've been invited twice
    invitation = Invitation.objects.filter(
        email=user.email,
        is_used=True
    ).select_related('site', 'invited_by').last()

    # 2. Determine the Role Title
    # If they have an invitation, use whatever the Boss typed (e.g., "Site Surveyor")
    # If no invitation, they are the "COMPANY OWNER / CONTRACTOR"
    if invitation:
        user_role = invitation.role_assigned
        company_profile = Company.objects.filter(
            owner=invitation.invited_by).first()
        assigned_site = invitation.site
    else:
        user_role = "CONTRACTOR"
        company_profile = Company.objects.filter(owner=user).first()
        assigned_site = None
    #
    my_invitations = Invitation.objects.filter(
        invited_by=user
    ).select_related('site').order_by('-created_at')
    context = {
        'user_role': user_role,  # ✍️ This is now "Foreman", "Engineer", etc.
        'invitation': invitation,
        'company': company_profile,
        'my_invitations': my_invitations,
        'assigned_site': assigned_site,
        'sites_count': SiteLocation.objects.filter(company=company_profile).count() if company_profile else 0,
    }

    return render(request, 'site_management/profile.html', context)


@login_required
def update_company_logo(request):
    if request.method == "POST":
        logo_file = request.FILES.get('logo')

        # 1. 🛡️ Quick Validation
        if not logo_file or logo_file.size == 0:
            if request.htmx:
                return HttpResponse("Invalid Image", status=400)
            return redirect('profile')

        # 2. 🏢 Find Company (Cleaner Logic)
        user = request.user
        # We check if they are the owner OR if they were invited by the owner
        company = Company.objects.filter(owner=user).first()
        if not company:
            invitation = Invitation.objects.filter(
                email=user.email, is_used=True).last()
            if invitation:
                company = Company.objects.filter(
                    owner=invitation.invited_by).first()

        # 3. 🚀 Save & Respond
        if company:
            try:
                company.logo = logo_file
                company.save()

                if request.htmx:
                    # ✅ THIS IS THE KEY: Return ONLY the partial
                    response = render(request, 'site_management/partials/logo_partial.html', {
                        'company_profile': company
                    })
                    response['HX-Trigger'] = json.dumps(
                        {"showMessage": "Logo updated!"})
                    return response

                messages.success(request, "Logo updated!")
            except Exception as e:
                print(f"Cloudinary Error: {e}")
                if request.htmx:
                    return HttpResponse("Cloudinary Timeout", status=500)
                messages.error(
                    request, "Upload failed. Check your connection.")

    # 🔄 Safety Fallback
    return redirect('profile')


@login_required
def update_company_name(request):
    if request.method == "POST":
        new_name = request.POST.get('business_name')
        user = request.user

        # 🕵️‍♂️ Find the company
        invitation = Invitation.objects.filter(
            email=user.email, is_used=True).last()
        if invitation:
            company = Company.objects.filter(
                owner=invitation.invited_by).first()
        else:
            company = Company.objects.filter(owner=user).first()

        if company and new_name:
            company.name = new_name
            company.save()

            # ✅ 1. Handle HTMX Requests
            if request.headers.get('HX-Request'):
                from django.http import HttpResponse
                # Use 204 (No Content) so HTMX doesn't swap anything, just triggers the event
                response = HttpResponse(status=204)
                response['HX-Trigger'] = json.dumps({
                    "showMessage": f"Business name updated to {new_name}!"
                })
                return response

            # ✅ 2. Handle standard Form Requests (Fallback)
            messages.success(request, f"Business name updated successfully!")
        else:
            messages.error(request, "Could not update business name.")

    return redirect('profile')


@login_required
def manage_staff_access(request, invitation_id):
    # Fetch the invitation
    invite = get_object_or_404(Invitation, id=invitation_id)
    site = invite.site

    # 🛡️ Permission Gate: Only the Boss or PM can do this
    pm_invite = Invitation.objects.filter(
        site=site, role_assigned='PROJECT_MANAGER', is_used=True).first()
    is_pm = (request.user.email == pm_invite.email) if pm_invite else False

    if request.user != site.company.owner and not is_pm:
        messages.error(request, "Access Denied.")
        return redirect('site_dashboard', site_id=site.id)

    if request.method == "POST":
        action = request.POST.get('action')

        if action == 'block':
            invite.is_used = False  # This blocks them from accessing the site
            messages.warning(request, f"Access revoked for {invite.email}")
        elif action == 'unblock':
            invite.is_used = True  # This restores access
            messages.success(request, f"Access restored for {invite.email}")

        invite.save()

    return redirect('site_dashboard', site_id=site.id)


@login_required
def block_staff(request, invite_id):
    invite = get_object_or_404(Invitation, id=invite_id)
    site = invite.site

    # 🛡️ Security Check
    # Find the PM email for this site (if any)
    pm_invite = Invitation.objects.filter(
        site=site, role_assigned='PROJECT_MANAGER', is_used=True).first()
    site_pm_email = pm_invite.email if pm_invite else None

    if site.company.owner == request.user or request.user.email == site_pm_email:
        invite.is_used = False
        invite.save()
        messages.success(request, f"Access revoked for {invite.email}.")
    else:
        messages.error(
            request, "Access Denied: Only the Boss or PM can block staff.")

    return redirect('profile')


@login_required
def close_site_day(request, site_id):
    if request.method == "POST":
        # 1. Get the data summary
        summary = get_daily_summary(site_id)

        # 2. 🚀 DISPATCH VIA RESEND
        # We only pass 'summary'. The function in reports.py handles
        # the PDF generation, the HTML rendering, and the Subject line!
        success = send_resend_audit_email(summary, report_type="DAILY")

        if success:
            messages.success(
                request, f"Daily report for {summary['site'].name} dispatched via Resend!")
        else:
            messages.error(
                request, "Resend Dispatch Failed. Check Render Environment Variables.")

        return redirect('site_dashboard', site_id=site_id)


# @login_required
# def close_site_day(request, site_id):
#     if request.method == "POST":
#         # 1. Get the data
#         summary = get_daily_summary(site_id)

#         # 2. FIXED: Pass the specific template path for daily reports
#         pdf_content = generate_pdf_report(summary, 'reports/pdf_template.html')

#         # 3. Build the HTML body for the email
#         html_message = render_to_string(
#             'site_management/daily_report_email.html', summary)

#         # 4. Prepare the EmailMessage
#         email = EmailMessage(
#             subject=f"OFFICIAL REPORT: {summary['site'].name} - {summary['today']}",
#             body="Please view the attached PDF and HTML report for today's site activities.",
#             from_email=settings.DEFAULT_FROM_EMAIL,
#             to=summary['recipients'],
#         )

#         email.content_subtype = "html"
#         email.body = html_message

#         # 5. Attach the PDF
#         if pdf_content:
#             email.attach(
#                 f"Report_{summary['site'].name}_{summary['today']}.pdf",
#                 pdf_content,
#                 'application/pdf'
#             )

#         try:
#             email.send()
#             messages.success(
#                 request, f"Daily reports for {summary['site'].name} dispatched!")
#         except Exception as e:
#             messages.error(request, f"Report failed to send: {e}")

#         return redirect('site_dashboard', site_id=site_id)


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
    """The core engine that builds and sends the PDF via Resend."""
    try:
        # 1. Get the 7-day snapshot data
        summary = get_weekly_summary(site_id)

        # 2. Generate the binary PDF content
        pdf_content = generate_pdf_report(
            summary, 'reports/weekly_pdf_template.html')

        if not pdf_content:
            print(f"Error: PDF content for site {site_id} is empty.")
            return False

        # 3. 🚀 DISPATCH VIA RESEND
        # We pass the report_type="WEEKLY" to use the correct email body and subject
        success = send_resend_audit_email(
            data=summary,
            report_type="WEEKLY"
        )

        return success

    except Exception as e:
        print(f"Error in weekly report logic: {e}")
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
