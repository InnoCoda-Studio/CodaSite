# Add Subscription if it's a separate model
from .models import CompanySubscription, Company
import requests
import hmac
from django.views.decorators.csrf import csrf_exempt
import hashlib
from django.shortcuts import render
from django.db import transaction, models  # <--- Add 'models' here
from django.db.models import F              # <--- Or just add this
import re
import math
from django.contrib.auth.models import User
from django.utils.text import slugify
from django.db import transaction, IntegrityError
from django.http import JsonResponse
from django.core.files.base import ContentFile
from django.shortcuts import render, get_object_or_404
from .models import SiteLocation
from django.shortcuts import get_object_or_404, redirect
import cloudinary.uploader  # Make sure this is imported!
from django.db.models import Q
from django.shortcuts import get_object_or_404, render
from django.utils.safestring import mark_safe
from django.shortcuts import redirect
from datetime import timedelta  # Add this at the top
from decimal import Decimal  # 👈 Ensure this is at the top of your file!
from .models import SiteLocation, StaffAttendance, MaterialDeduction
import random
from django.conf import settings
# Ensure these are at the top
import cloudinary.uploader
from django.db import transaction
from django.utils import timezone
from django.http import HttpResponse
#
import qrcode
from io import BytesIO
import base64

from django.core.management import call_command
from django.http import HttpResponseForbidden, JsonResponse

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
from .utils import  get_monthly_summary


from django.db.models import Q, F
# Distance calculating
from math import radians, cos, sin, asin, sqrt
from django.http import HttpResponse
from decimal import Decimal
# company profile
import json
from django.http import HttpResponse
import os

from django.contrib.auth import get_user_model
User = get_user_model()


def check_proximity(site_lat, site_lng, user_lat, user_lng, tolerance_meters=200):
    """
    Calculates the distance between two sets of GPS coordinates 
    and checks if they are within a specific meter threshold.
    """
    # 🛑 THE FIX: Force all incoming coordinates to be floats
    site_lat = float(site_lat)
    site_lng = float(site_lng)
    user_lat = float(user_lat)
    user_lng = float(user_lng)

    # Earth's radius in meters
    R = 6371000

    # Convert degrees to radians
    phi1 = math.radians(site_lat)
    phi2 = math.radians(user_lat)
    delta_phi = math.radians(user_lat - site_lat)
    delta_lambda = math.radians(user_lng - site_lng)

    # Haversine formula logic
    a = math.sin(delta_phi / 2)**2 + \
        math.cos(phi1) * math.cos(phi2) * \
        math.sin(delta_lambda / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    distance = R * c

    # Return True if the worker is within the buffer (default 200m)
    return distance <= tolerance_meters


def index(request):
    if not request.user.is_authenticated:
        return render(request, 'account/landing_page.html')
    # 🧼 Session Cleanup: Wipe the active site ID when returning home
    if 'active_site_id' in request.session:
        del request.session['active_site_id']
        request.session.modified = True

    # 🏢 1. Identify the Company
    user_company = getattr(request.user, 'company', None)

    # Handle invited staff members
    if not user_company:
        invitation = Invitation.objects.filter(
            email=request.user.email, is_used=True).first()
        if invitation:
            user_company = invitation.site.company

    if not user_company:
        return redirect('profile')

    # 🔒 Check subscription access
    subscription = getattr(user_company, "subscription", None)

    if not subscription or not subscription.is_access_valid:
        return redirect("billing_upgrade")

    # 🏗️ 2. BASE QUERIES (With N+1 Optimization)
    if hasattr(request.user, 'company'):
        # 🚀 KEY FIX: Added .prefetch_related('stocks')
        user_sites = SiteLocation.objects.filter(
            company=user_company).prefetch_related('stocks')
    else:
        assigned_site_ids = Invitation.objects.filter(
            email=request.user.email, is_used=True
        ).values_list('site_id', flat=True)
        # 🚀 KEY FIX: Added .prefetch_related('stocks')
        user_sites = SiteLocation.objects.filter(
            id__in=assigned_site_ids).prefetch_related('stocks')

    sites = user_sites.order_by("-created_at")

    # 📦 3. GLOBAL INVENTORY & SECURITY LOGIC
    total_cement = 0
    global_inventory = None
    low_stock_items = None

    if hasattr(request.user, 'company'):
        # The Boss sees everything
        total_cement = MaterialStock.objects.filter(
            site__company=user_company,
            item_name__icontains='cement'
        ).aggregate(total=Sum('current_balance'))['total'] or 0

        global_inventory = MaterialStock.objects.filter(
            site__company=user_company
        ).values('item_name', 'unit').annotate(
            total_balance=Sum('current_balance')
        ).order_by('item_name')

        # 🚨 FIX: Moved this INSIDE the conditional so Storekeepers don't trigger global queries
        low_stock_items = MaterialStock.objects.filter(
            site__company=user_company,
            current_balance__lt=F('minimum_required')
        ).select_related('site').order_by('current_balance')

    context = {
        'sites': sites,
        'global_inventory': global_inventory,
        'low_stock_items': low_stock_items,
        'company': user_company,
        'total_cement': total_cement,
    }

    # --- 🎯 THE RESPONSE LOGIC ---
    if request.headers.get('HX-Target') == 'dashboard-live-zone':
        return render(request, 'site_management/htmx_components/dashboard_feed.html', context)

    response = render(request, 'site_management/index.html', context)

    if request.htmx:
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
    # global_workers_pool = SkilledWorker.objects.filter(
    #     company=company
    # ).exclude(site=site)

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

    workers = SkilledWorker.objects.filter(site=site, is_trashed=False)
    stocks = MaterialStock.objects.filter(site=site)

    # 🌍 GLOBAL POOL (Safe for everyone)
    # We use 'company' (the one owning the site) instead of 'request.user.company'
    # 🌍 GLOBAL POOL (Safe for everyone)
    # 🛑 FIX: Exclude trashed workers from the "Redeploy" dropdown
    global_workers_pool = SkilledWorker.objects.filter(
        contractor=company.owner,
        is_trashed=False
    ).exclude(site=site)

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
            # Data Extraction
            id_num = request.POST.get('id_number', '').strip().upper()
            phone_num = request.POST.get('phone', '').strip()
            worker_name = request.POST.get('name', '').strip()
            emergency_contact = request.POST.get(
                'emergency_contact', '').strip()

            # 🚀 NEW: Extract Worker Type and Lead Worker
            # 'company_hire', 'sub_contractor', or 'crew'
            worker_type = request.POST.get('worker_type', 'company_hire')
            lead_worker_id = request.POST.get('lead_worker_id')

            is_sub = False
            lead_worker_instance = None

            # Financial Data
            bank_name = request.POST.get('bank_name', '').strip().upper()
            account_num = request.POST.get('account_number', '').strip()
            account_name = request.POST.get('account_name', '').strip().upper()

            # 🚀 NEW: Smart Money & Crew Logic
            try:
                if worker_type in ['sub_contractor', 'crew']:
                    # The Oga and his boys don't get a daily rate from the company!
                    daily_rate = Decimal('0.00')
                    if worker_type == 'sub_contractor':
                        is_sub = True
                    elif worker_type == 'crew' and lead_worker_id:
                        # Find the Oga they belong to
                        lead_worker_instance = SkilledWorker.objects.get(
                            id=lead_worker_id)
                else:
                    # Normal Company Hire
                    raw_rate = request.POST.get('daily_rate')
                    daily_rate = Decimal(
                        raw_rate) if raw_rate else Decimal('0.00')
            except Exception:
                daily_rate = Decimal('0.00')

            # ⚡ Auto-Generate Staff ID (If left blank)
            if not id_num:
                year = timezone.now().year
                count = SkilledWorker.objects.filter(
                    company=company).count() + 1
                id_num = f"IC-{year}-{count:03d}"

            # 🛡️ Identity Collision Check
            if SkilledWorker.objects.filter(Q(id_number=id_num) | Q(phone=phone_num)).exists():
                messages.error(
                    request, f"Identity Error: Personnel with ID {id_num} or Phone {phone_num} already exists.")
                return redirect('site_dashboard', site_id=site.id)

            try:
                # ☁️ Cloudinary Upload (Profile Picture)
                secure_image_url = None
                profile_picture = request.FILES.get('profile_picture')
                if profile_picture:
                    upload_result = cloudinary.uploader.upload(
                        profile_picture, folder="codasite_personnel")
                    secure_image_url = upload_result['public_id']

                # 🔒 Atomic Database Transaction
                with transaction.atomic():
                    # A. Create the Shadow User
                    username = slugify(id_num)
                    # Generate the 4-digit pin from phone or default to 2026
                    raw_pin = phone_num[-4:] if len(phone_num) >= 4 else '2026'
                    default_password = f"Coda{raw_pin}"

                    worker_user = User.objects.create_user(
                        username=username, password=default_password)

                    # B. Create SkilledWorker Profile linked DIRECTLY to this site
                    worker = SkilledWorker.objects.create(
                        user=worker_user,
                        contractor=request.user,
                        site=site,  # 📍 Direct deployment to this site
                        company=company,
                        name=worker_name,
                        category=request.POST.get('category', '').upper(),
                        id_number=id_num,
                        phone=phone_num,
                        emergency_contact=emergency_contact,  # Saved to DB!

                        # 🚀 NEW: Save the Sub-Contractor / Crew Status
                        is_sub_contractor=is_sub,
                        lead_worker=lead_worker_instance,

                        gate_pass=raw_pin,  # ✨ RESTORED: Critical for QR Gate Pass!
                        daily_rate=daily_rate,
                        profile_picture=secure_image_url,
                        bank_name=bank_name,
                        account_number=account_num,
                        account_name=account_name
                    )

                messages.success(
                    request, f"SUCCESS: {worker.name} deployed to {site.name}. LOGIN: {username} | PASS: {default_password}")

            except Exception as e:
                messages.error(request, f"Registry Error: {str(e)}")

            # 🔥 The page naturally reloads here!
            return redirect('site_dashboard', site_id=site.id)

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


def calculate_distance(lat1, lon1, lat2, lon2):
    """Calculates if the worker is within 200m of the site gate."""
    try:
        R = 6371.0  # Earth radius in km
        lat1, lon1, lat2, lon2 = map(
            radians, [float(lat1), float(lon1), float(lat2), float(lon2)])
        dlon, dlat = lon2 - lon1, lat2 - lat1
        a = sin(dlat / 2)**2 + cos(lat1) * cos(lat2) * sin(dlon / 2)**2
        c = 2 * asin(sqrt(a))
        return c * R * 1000  # Distance in meters
    except (TypeError, ValueError):
        return 999999  # Fail safe for missing GPS


#         return response
def htmx_clock_in(request, site_id):
    if request.method == "POST":
        site = get_object_or_404(SiteLocation, id=site_id)
        worker_id = request.POST.get('worker_id')
        worker = get_object_or_404(SkilledWorker, id=worker_id)

        # 📸 1. CATCH THE NEW BIOMETRIC SNAPSHOT
        daily_photo = request.FILES.get('daily_photo')

        # 🛰️ 2. Coordinate Validation
        try:
            u_lat = float(request.POST.get('lat', 0))
            u_lng = float(request.POST.get('lng', 0))
        except (TypeError, ValueError):
            u_lat, u_lng = 0, 0

        # 🛡️ 3. Security Checks
        if not site.latitude or not site.longitude:
            return HttpResponse(
                '<div class="p-2 bg-orange-600 text-white text-[10px] font-black uppercase rounded-lg">🚨 Site GPS not set by Admin</div>',
                status=200
            )

        if u_lat == 0 or u_lng == 0:
            return HttpResponse(
                '<div class="p-2 bg-red-600 text-white text-[10px] font-black uppercase rounded-lg">🚨 GPS Signal missing</div>',
                status=200
            )

        distance = calculate_distance(
            site.latitude, site.longitude, u_lat, u_lng)
        if distance > site.radius_meters:
            return HttpResponse(
                f'<div class="p-2 bg-red-600 text-white text-[10px] font-bold uppercase rounded-lg">'
                f'OUT OF RANGE: {int(distance)}m away</div>',
                status=200
            )

        today = timezone.now().date()
        already_finished = StaffAttendance.objects.filter(
            worker=worker, site=site, time_in__date=today, time_out__isnull=False
        ).exists()

        if already_finished:
            return HttpResponse(
                '<div class="p-2 bg-orange-500 text-white text-[10px] font-black uppercase rounded-lg">🚨 Shift already completed today</div>',
                status=200
            )

        # ✅ 4. Clock In (Update or Create with the Photo)
        attendance, created = StaffAttendance.objects.update_or_create(
            worker=worker,
            site=site,
            time_in__date=today,
            defaults={
                'user': request.user,
                'time_in': timezone.now(),
                'daily_rate_at_time': worker.daily_rate,
                'clock_in_photo': daily_photo  # 📸 INJECT THE PHOTO INTO THE DATABASE
            }
        )

        # 🔄 5. Prep OOB Updates & Response
        attendance_today = StaffAttendance.objects.filter(
            site=site, time_in__date=today
        ).select_related('worker')

        present_worker_ids = list(attendance_today.filter(
            time_out__isnull=True).values_list('worker_id', flat=True))

        invitation = Invitation.objects.filter(
            email=request.user.email, site=site).last()
        user_role = invitation.role_assigned if invitation else 'CONTRACTOR'

        response = render(request, 'site_management/htmx_components/worker_button.html', {
            'worker': worker,
            'site': site,
            'present_worker_ids': present_worker_ids,
            'user_role': user_role,
        })

        # OOB Counter Update
        onsite_count = len(present_worker_ids)
        total_workers = SkilledWorker.objects.filter(site=site).count()
        onsite_counter_html = f'''
            <h3 id="onsite-counter" hx-swap-oob="true" class="text-4xl font-black text-white tracking-tighter">
                {onsite_count} <span class="text-white/20 text-2xl">/ {total_workers}</span>
            </h3>
        '''

        # Combine content and trigger finance refresh
        response.content += mark_safe(onsite_counter_html).encode()
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
def generate_site_qr(request, site_id):
    site = get_object_or_404(SiteLocation, id=site_id)

    # 🔐 Security: Encode the Site ID and a timestamp or secret
    # This URL is where the worker's phone will go
    portal_url = request.build_absolute_uri(f'/attendance/scan/{site.id}/')

    # Create the QR
    qr = qrcode.QRCode(version=1, box_size=10, border=5)
    qr.add_data(portal_url)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")

    # Save to buffer to send to template without saving a file to disk
    buffer = BytesIO()
    img.save(buffer, format="PNG")
    qr_base64 = base64.b64encode(buffer.getvalue()).decode()

    return render(request, 'site_management/htmx_components/qr_modal.html', {
        'qr_code': qr_base64,
        'site': site
    })
# Temporary placeholder so the server can start


# 1. THE SCAN PORTAL (No login required - anyone can scan the QR to see the form)
def attendance_scan_portal(request, site_id):
    site = get_object_or_404(SiteLocation, id=site_id)
    return render(request, 'site_management/worker_scan_portal.html', {'site': site})

# Ensure you have your models imported (SkilledWorker, StaffAttendance, etc.)
# 2. THE VERIFICATION ENDPOINT (For the Alpine.js frontend to check the PIN instantly)


# def verify_worker_identity(request, site_id):
#     """API endpoint to check Phone + PIN before opening the camera"""
#     if request.method == "POST":
#         phone = request.POST.get('phone', '').strip()
#         pin = request.POST.get('pin', '').strip()

#         # Look for the worker on this specific site
#         worker = SkilledWorker.objects.filter(
#             site_id=site_id,
#             phone=phone,
#             gate_pass=pin
#         ).first()

#         if worker:
#             return JsonResponse({'valid': True, 'name': worker.name})

#         return JsonResponse({'valid': False, 'error': 'Invalid Phone or PIN'})
#     return JsonResponse({'valid': False, 'error': 'Invalid request'})
def verify_worker_identity(request, site_id):
    """API endpoint to check Phone + PIN before opening the camera, AND check clock status"""
    if request.method == "POST":
        phone = request.POST.get('phone', '').strip()
        pin = request.POST.get('pin', '').strip()

        # Look for the worker on this specific site
        worker = SkilledWorker.objects.filter(
            site_id=site_id,
            phone=phone,
            gate_pass=pin
        ).first()

        if worker:
            # 🚀 THE FIX: Check if they are currently on the clock
            is_clocked_in = StaffAttendance.objects.filter(
                worker=worker,
                site_id=site_id,
                time_out__isnull=True
            ).exists()

            return JsonResponse({
                'valid': True,
                'name': worker.name,
                'is_clocked_in': is_clocked_in  # 👈 Pass the status to the frontend
            })

        return JsonResponse({'valid': False, 'error': 'Invalid Phone or PIN'})
    return JsonResponse({'valid': False, 'error': 'Invalid request'})


def process_biometric_clock(request, site_id):
    if request.method == 'POST':
        site = get_object_or_404(SiteLocation, id=site_id)

        # 1. Verify Identity
        phone = request.POST.get('phone', '').strip()
        pin = request.POST.get('pin', '').strip()
        worker = SkilledWorker.objects.filter(
            site=site, phone=phone, gate_pass=pin).first()
        if not worker:
            return JsonResponse({'success': False, 'error': 'Identity verification failed.'})

        clock_type = request.POST.get('type')
        photo_data = request.POST.get('photo')

        # 2. Get GPS
        try:
            lat = float(request.POST.get('lat', 0))
            lng = float(request.POST.get('lng', 0))
        except ValueError:
            return JsonResponse({'success': False, 'error': 'Corrupt GPS data.'})

        if not site.latitude or not site.longitude:
            return JsonResponse({'success': False, 'error': 'Site GPS not set by Admin. Cannot verify.'})

        # 3. Proximity Check (THE INVISIBLE FENCE!)
        if not check_proximity(site.latitude, site.longitude, lat, lng):
            return JsonResponse({'success': False, 'error': 'GPS Mismatch: You must be at the site gate.'})

        # 4. Process Photo & Save Record
        if clock_type == 'IN':
            # Guard 1: Check if they are CURRENTLY on an active shift
            already_in = StaffAttendance.objects.filter(
                worker=worker, site=site, time_out__isnull=True).exists()
            if already_in:
                return JsonResponse({'success': False, 'error': 'You are already clocked in.'})

            # 🚨 NEW GUARD 2: Check if they ALREADY completed a shift today
            # Django's __date lookup automatically handles timezone conversion safely
            already_completed_today = StaffAttendance.objects.filter(
                worker=worker,
                site=site,
                time_in__date=timezone.localdate(),  # 🇳🇬 Guarantees Lagos date matching
                time_out__isnull=False
            ).exists()

            if already_completed_today:
                return JsonResponse({
                    'success': False,
                    'error': 'Access Denied: You have already completed your shift for today.'
                })

            # ☁️ CLOUDINARY UPLOAD ☁️
            secure_image_id = None
            try:
                upload_result = cloudinary.uploader.upload(
                    photo_data,
                    folder="codasite_attendance_logs"
                )
                secure_image_id = upload_result['public_id']
            except Exception as e:
                print(f"CLOUDINARY UPLOAD FAILED: {str(e)}")
                return JsonResponse({'success': False, 'error': 'Failed to upload biometric feed to cloud.'})

            # Anti-Spam Double Check (From our previous fix)
            double_check_in = StaffAttendance.objects.filter(
                worker=worker, site=site, time_out__isnull=True).exists()
            if double_check_in:
                return JsonResponse({'success': False, 'error': 'Clock-in transaction already processed.'})

            # 5. Database Save
            try:
                user_to_assign = worker.user
                if not user_to_assign:
                    user_to_assign = worker.contractor

                attendance = StaffAttendance(
                    worker=worker,
                    site=site,
                    user=user_to_assign,
                    time_in=timezone.now(),
                    clock_in_photo=secure_image_id
                )
                attendance.save()

            except Exception as e:
                print(f"DATABASE CRASH: {str(e)}")
                return JsonResponse({'success': False, 'error': f'DB Error: {str(e)}'})

        else:
            # CLOCK OUT LOGIC
            attendance = StaffAttendance.objects.filter(
                worker=worker, site=site, time_out__isnull=True).last()
            if attendance:
                attendance.time_out = timezone.now()
                attendance.save()
            else:
                return JsonResponse({'success': False, 'error': 'No active clock-in found.'})

        return JsonResponse({'success': True})
    return JsonResponse({'success': False, 'error': 'Invalid request.'})


@login_required
def site_warehouse(request, site_id):
    # 🏢 1. Fetch the site FIRST
    site = get_object_or_404(SiteLocation, id=site_id)

    # 🛡️ 2. THE PERMISSION GATE
    is_owner = (site.company.owner == request.user)

    invitation = Invitation.objects.filter(
        email=request.user.email,
        site=site,
        is_used=True
    ).last()

    if not is_owner and not invitation:
        messages.error(
            request, "Access Denied: You are not assigned to this warehouse.")
        return redirect('profile')

    # 3. Determine the User's Role for the UI
    user_role = invitation.role_assigned if invitation else 'CONTRACTOR'
    is_boss = is_owner or (user_role == 'PROJECT_MANAGER')

    # --- THE LOGIC ENGINE (POST METHODS) ---

    if request.method == "POST":
        # --- A. INTAKE MATERIAL (ADD STOCK) ---
        if 'add_stock' in request.POST:
            try:
                qty = Decimal(request.POST.get('quantity') or '0.00')

                if qty <= 0:
                    messages.error(
                        request, "Quantity must be greater than zero.")
                    return redirect('site_warehouse', site_id=site.id)

                raw_name = request.POST.get('item_name', '')
                item_name = re.sub(r'\s+', ' ', raw_name.strip().upper())
                unit = request.POST.get('unit', '').strip()
                img_file = request.FILES.get('evidence_image')
                vid_file = request.FILES.get('evidence_video')
                item_category = request.POST.get('item_category')

                is_tool = (item_category == 'asset')

                # Heavy third-party upload executed safely outside the atomic transaction block
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

                with transaction.atomic():
                    stock, created = MaterialStock.objects.select_for_update().get_or_create(
                        site=site,
                        item_name=item_name,
                        defaults={
                            'unit': unit,
                            'is_returnable': is_tool
                        }
                    )

                    stock.is_returnable = is_tool
                    stock.unit = unit
                    stock.current_balance += qty

                    if img_file:
                        stock.evidence_image = img_file
                    if processed_vid:
                        stock.evidence_video = processed_vid

                    stock.save()

                    MaterialRestockLog.objects.create(
                        stock_item=stock,
                        site=site,
                        quantity_added=qty,
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
                if qty <= 0:
                    messages.error(request, "Invalid quantity.")
                    return redirect('site_warehouse', site_id=site.id)

                worker = get_object_or_404(
                    SkilledWorker, id=worker_id, is_trashed=False)
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
                    request, f"✅ DISPATCHED: {qty} {stock.unit} of {stock.item_name} to {worker.name}."
                )

            except ValidationError as e:
                messages.error(request, e.messages[0])
            except MaterialStock.DoesNotExist:
                messages.error(request, "Material not found.")
            except Exception as e:
                messages.error(request, f"A system error occurred: {e}")

        # --- C. RECEIVE RETURNED TOOL (PRO ARCHITECTURE) ---
        elif 'return_tool' in request.POST:
            deduction_id = request.POST.get('deduction_id')
            return_qty = Decimal(request.POST.get('return_qty') or 0)

            try:
                with transaction.atomic():
                    deduction = MaterialDeduction.objects.select_for_update().get(
                        id=deduction_id,
                        is_returned=False,
                        stock_item__site=site
                    )

                    owed_qty = deduction.amount_owed

                    if return_qty <= 0 or return_qty > owed_qty:
                        messages.error(
                            request, f"Error: You can only return between 1 and {owed_qty} items."
                        )
                    else:
                        deduction.quantity_returned += return_qty
                        deduction.returned_at = timezone.now()

                        if deduction.quantity_returned >= deduction.quantity_taken:
                            deduction.is_returned = True
                            status_msg = f"✅ FULLY SECURED: All {deduction.quantity_taken} items returned by {deduction.worker.name}."
                        else:
                            status_msg = f"⚠️ PARTIAL RETURN: Received {return_qty}. {deduction.worker.name} still owes {deduction.amount_owed}."

                        deduction.save(
                            update_fields=['quantity_returned', 'is_returned', 'returned_at'])

                        stock = deduction.stock_item
                        stock.current_balance = F(
                            'current_balance') + return_qty
                        stock.save(update_fields=['current_balance'])

                        messages.success(request, status_msg)

            except MaterialDeduction.DoesNotExist:
                messages.error(
                    request, "Error: Tool record not found or already fully returned.")
            except Exception as e:
                messages.error(request, f"System error receiving tool: {e}")

        # HTMX intercept for form submissions to handle smooth inline DOM refreshes
        if request.META.get('HTTP_HX_REQUEST'):
            response = HttpResponse(status=204)
            response['HX-Refresh'] = 'true'
            return response

        return redirect('site_warehouse', site_id=site.id)

    # --- 📋 NORMAL PAGE LOAD / GET OPERATIONS ---

    # 🔍 Fetch search parameter
    query = request.GET.get('q', '').strip()

    # Base stocks queryset
    stocks = MaterialStock.objects.filter(site=site).order_by('item_name')

    # 🟢 If the contractor search bar fires, filter the stock dashboard view instantly

    if query:
        stocks = stocks.filter(
            Q(item_name__icontains=query) |
            Q(unit__icontains=query)
        )

    workers = SkilledWorker.objects.filter(site=site, is_trashed=False)

    active_tools = MaterialDeduction.objects.filter(
        stock_item__site=site,
        is_returned=False,
        stock_item__is_returnable=True
    ).select_related('worker', 'stock_item').order_by('-timestamp')

    tool_history = MaterialDeduction.objects.filter(
        stock_item__site=site,
        stock_item__is_returnable=True
    ).select_related('worker', 'stock_item').order_by('-timestamp')

    blocked_worker_ids = list(active_tools.values_list('worker_id', flat=True))

    context = {
        'site': site,
        'stocks': stocks,
        'workers': workers,
        'is_boss': is_boss,
        'user_role': user_role,
        'active_tools': active_tools,
        'tool_history': tool_history,
        'blocked_worker_ids': blocked_worker_ids,
    }

    return render(request, 'site_management/site_warehouse.html', context)


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


# Import your models here


@login_required
def worker_history_modal(request, site_id, worker_id):
    # 1. Grab both the Site and the Worker
    site = get_object_or_404(SiteLocation, id=site_id)
    worker = get_object_or_404(SkilledWorker, id=worker_id)

    # 🔒 2. THE FIX: Filter the history by BOTH worker AND site!
    history = StaffAttendance.objects.filter(
        worker=worker, site=site).order_by('-time_in')

    context = {
        'site': site,      # Pass the site to the template so you can display the site name
        'worker': worker,
        'history': history,
    }

    return render(request, 'site_management/htmx_components/history_modal.html', context)
# --- WORKER & SITE MANAGEMENT ---


# @login_required
@login_required
def add_site(request):
    if request.method == "POST":
        # 1. Get the company
        user_company = request.user.company

        # 2. Get GPS data from the hidden inputs in your form
        lat = request.POST.get('latitude')
        lng = request.POST.get('longitude')

        # 3. Create the Site with ALL data
        SiteLocation.objects.create(
            name=request.POST.get('name'),
            address=request.POST.get('address'),
            company=user_company,
            latitude=lat if lat else None,  # Save the Lat
            longitude=lng if lng else None,  # Save the Lng
            radius_meters=100               # Set a default radius
        )

        messages.success(
            request, f"Project '{request.POST.get('name')}' registered with GPS location.")

    return redirect('index')


@login_required
def update_site(request, site_id):
    # 1. Get the site and make sure it belongs to the user's company
    site = get_object_or_404(SiteLocation, id=site_id,
                             company=request.user.company)

    # 2. Safety Check: Only allow updates if within the 7-day grace period
    if not site.is_editable():
        messages.error(
            request, "The 7-day grace period for editing this site has expired.")
        return redirect('index')

    if request.method == "POST":
        # 3. Update the fields
        site.name = request.POST.get('name')
        site.address = request.POST.get('address')
        site.latitude = request.POST.get('latitude')
        site.longitude = request.POST.get('longitude')
        site.save()

        messages.success(
            request, f"Project '{site.name}' updated successfully.")

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
def all_workers(request):
    # --- 1. HANDLE SAVING NEW WORKER ---
    active_workers = SkilledWorker.objects.filter(
        contractor=request.user, is_trashed=False).order_by('-id')
    trashed_workers = SkilledWorker.objects.filter(
        contractor=request.user, is_trashed=True).order_by('-id')
    user_sites = SiteLocation.objects.filter(company__owner=request.user)

    if request.method == "POST" and 'register_worker' in request.POST:
        try:
            # 🛡️ Data Extraction
            id_num = request.POST.get('id_number', '').strip().upper()
            phone_num = request.POST.get('phone', '').strip().replace(" ", "")
            worker_name = request.POST.get('name', '').strip()

            # 🚀 Hierarchy Logic
            worker_type = request.POST.get('worker_type', 'company_hire')
            lead_worker_id = request.POST.get('lead_worker_id')
            site_id = request.POST.get('site_id')  # Initial Site Assignment

            is_sub = (worker_type == 'sub_contractor')
            lead_worker_instance = None

            if worker_type == 'crew' and lead_worker_id:
                lead_worker_instance = SkilledWorker.objects.get(
                    id=lead_worker_id)

            # 💰 Money Logic (0.00 for Ogas and Crew)
            if worker_type in ['sub_contractor', 'crew']:
                daily_rate = Decimal('0.00')
            else:
                raw_rate = request.POST.get('daily_rate')
                daily_rate = Decimal(
                    raw_rate) if raw_rate and raw_rate.strip() else Decimal('0.00')

            # 🔐 GAT-PASS GENERATOR
            raw_pin = phone_num[-4:] if len(
                phone_num) >= 4 else str(random.randint(1000, 9999))

            # 🛡️ Collision Check

            # 🛡️ Collision Check (Scoped to the current contractor)
            if SkilledWorker.objects.filter(contractor=request.user, phone=phone_num).exists():
                messages.error(
                    request, f"Identity Error: You already have a worker with phone {phone_num}.")
                return redirect('all_workers')

            # ☁️ Cloudinary Logic
            secure_image_url = None
            profile_picture = request.FILES.get('profile_picture')
            if profile_picture:
                upload_result = cloudinary.uploader.upload(
                    profile_picture, folder="codasite_personnel")
                secure_image_url = upload_result['public_id']

            # 🔒 Save with Shadow User Creation
            with transaction.atomic():
                username = slugify(worker_name) + "-" + \
                    str(random.randint(10, 99))
                default_password = f"Coda{raw_pin}"
                worker_user = User.objects.create_user(
                    username=username, password=default_password)

                SkilledWorker.objects.create(
                    user=worker_user,
                    contractor=request.user,
                    company=request.user.contractor_profile,  # Assuming you have a profile link
                    site_id=site_id if site_id else None,
                    name=worker_name,
                    category=request.POST.get('category', '').upper(),
                    id_number=id_num,
                    phone=phone_num,
                    gate_pass=raw_pin,
                    daily_rate=daily_rate,
                    is_sub_contractor=is_sub,
                    lead_worker=lead_worker_instance,
                    emergency_contact=request.POST.get('emergency_contact'),
                    bank_name=request.POST.get('bank_name', '').upper(),
                    account_number=request.POST.get('account_number'),
                    account_name=request.POST.get('account_name', '').upper(),
                    profile_picture=secure_image_url
                )

            messages.success(
                request, f"SUCCESS: {worker_name} enrolled. PIN: {raw_pin}")
            return redirect('all_workers')

        except Exception as e:
            print(f"DATABASE REJECTION: {e}")
            messages.error(request, f"Registry Error: {e}")

   # --- 2. DISPLAY LOGIC (Optimized) ---

    # 1. Fetch active workers ONLY ONCE
    active_workers = SkilledWorker.objects.filter(
        contractor=request.user,
        is_trashed=False
    ).order_by('-id')

    # 2. Fetch trashed workers ONLY ONCE
    trashed_workers = SkilledWorker.objects.filter(
        contractor=request.user,
        is_trashed=True
    ).order_by('-id')

    # 3. Fetch sites ONLY ONCE
    user_sites = SiteLocation.objects.filter(company__owner=request.user)

    # 4. Pass the fetched variables to the template
    return render(request, 'site_management/all_workers.html', {
        'workers': active_workers,            # Powers the main table
        'global_workers_pool': active_workers,  # Powers the "Crew Lead" dropdown
        # (In case your template uses this name)
        'active_workers': active_workers,
        'trashed_workers': trashed_workers,    # Powers the graveyard/trash view
        'user_sites': user_sites,              # Powers the site assignment dropdown
    })


@login_required
def worker_search(request):
    search_query = request.GET.get('search', '').strip()

    # 🛡️ THE FIX: Safely filter for workers belonging to this specific user's projects/company
    # This checks if the user is the owner of the company OR the person who registered them.
    workers = SkilledWorker.objects.filter(
        Q(company__owner=request.user) | Q(contractor=request.user)
    ).distinct()

    # Apply the search text if they typed something
    if search_query:
        workers = workers.filter(
            Q(name__icontains=search_query) |
            Q(id_number__icontains=search_query) |
            Q(category__icontains=search_query)
        )

    return render(request, 'site_management/htmx_components/worker_list_results.html', {'workers': workers})

#


@login_required
def add_worker(request, site_id):
    site = get_object_or_404(SiteLocation, id=site_id)
    company = site.company

    # 1. 🛡️ Permission Security
    is_owner = (company.owner == request.user)
    is_invited_pm = Invitation.objects.filter(
        email=request.user.email, site=site, is_used=True, role_assigned='PROJECT_MANAGER'
    ).exists()

    if not (is_owner or is_invited_pm):
        messages.error(
            request, "SECURITY ALERT: Unauthorized enrollment attempt blocked.")
        return redirect('profile')

    if request.method == "POST":
        # Data Extraction
        id_num = request.POST.get('id_number', '').strip().upper()
        phone_num = request.POST.get(
            'phone', '').strip().replace(" ", "")  # Remove spaces
        worker_name = request.POST.get('name', '').strip()
        emergency_contact = request.POST.get('emergency_contact', '').strip()

        # 🚀 NEW: Extract Worker Type and Lead Worker (The Oga)
        # 'company_hire', 'sub_contractor', or 'crew'
        worker_type = request.POST.get('worker_type', 'company_hire')
        lead_worker_id = request.POST.get('lead_worker_id')

        is_sub = False
        lead_worker_instance = None

        # Financial Data
        bank_name = request.POST.get('bank_name', '').strip().upper()
        account_num = request.POST.get('account_number', '').strip()
        account_name = request.POST.get('account_name', '').strip().upper()

        if len(phone_num) >= 4:
            raw_pin = phone_num[-4:]
        else:
            # Generate a truly random 4-digit PIN (e.g., 4829)
            raw_pin = str(random.randint(1000, 9999))

        # 🚀 NEW: Smart Money & Crew Logic based on Worker Type
        try:
            if worker_type in ['sub_contractor', 'crew']:
                # The Oga and his boys don't get a daily rate from the company!
                daily_rate = Decimal('0.00')
                if worker_type == 'sub_contractor':
                    is_sub = True
                elif worker_type == 'crew' and lead_worker_id:
                    # Find the Oga they belong to
                    lead_worker_instance = SkilledWorker.objects.get(
                        id=lead_worker_id)
            else:
                # Normal Company Hire
                daily_rate = Decimal(request.POST.get('daily_rate') or '0.00')
        except Exception as e:
            daily_rate = Decimal('0.00')

        # 2. ⚡ Auto-Generate Staff ID (If left blank)
        if not id_num:
            year = timezone.now().year
            count = SkilledWorker.objects.filter(company=company).count() + 1
            id_num = f"CS-{year}-{count:03d}"

        # 3. 🛡️ Identity Collision Check
        if SkilledWorker.objects.filter(Q(id_number=id_num) | Q(phone=phone_num)).exists():
            messages.error(
                request, f"Identity Error: Personnel with ID {id_num} or Phone {phone_num} already exists.")
            return redirect('site_dashboard', site_id=site_id)

        try:
            # 4. ☁️ Cloudinary Upload (Profile Picture)
            secure_image_url = None
            profile_picture = request.FILES.get('profile_picture')
            if profile_picture:
                upload_result = cloudinary.uploader.upload(
                    profile_picture, folder="codasite_personnel")
                secure_image_url = upload_result['public_id']

            # 5. 🔒 Atomic Database Transaction
            with transaction.atomic():
                # A. Create the Shadow User
                username = slugify(id_num)
                # Generate the 4-digit pin from phone or default to 2026
                raw_pin = phone_num[-4:] if len(phone_num) >= 4 else "2026"
                default_password = f"Coda{raw_pin}"

                worker_user = User.objects.create_user(
                    username=username, password=default_password)

                # B. Create SkilledWorker Profile
                worker = SkilledWorker.objects.create(
                    user=worker_user,
                    contractor=request.user,
                    site=site,
                    company=company,
                    name=worker_name,
                    category=request.POST.get('category', '').upper(),
                    id_number=id_num,
                    phone=phone_num,
                    emergency_contact=emergency_contact,

                    # 🚀 NEW: Save the Sub-Contractor / Crew Status
                    is_sub_contractor=is_sub,
                    lead_worker=lead_worker_instance,

                    gate_pass=raw_pin,  # ✨ SAVING THE PIN HERE FOR QR CLOCKING
                    daily_rate=daily_rate,
                    profile_picture=secure_image_url,
                    bank_name=bank_name,
                    account_number=account_num,

                )

            messages.success(
                request, f"✅ {worker.name} ENROLLED! | PIN: {raw_pin} | PASS: {default_password}")

        except Exception as e:
            messages.error(request, f"Registry Error: {str(e)}")
            return redirect('site_dashboard', site_id=site_id)

        # 🚀 THE FIX: Standard Full-Page Redirect after success
        return redirect('site_dashboard', site_id=site_id)

    return redirect('site_dashboard', site_id=site_id)


@login_required
def rate_worker(request, worker_id):
    if request.method == "POST":
        worker = get_object_or_404(
            SkilledWorker, id=worker_id, contractor=request.user)
        new_rating = request.POST.get('rating')
        if new_rating:
            worker.rating = int(new_rating)
            # Auto-promote to Elite if they have 5 stars
            worker.is_elite = (int(new_rating) == 5)
            worker.save()
            messages.success(
                request, f"Updated {worker.name}'s performance rating.")
    return redirect('worker_profile', slug=worker.slug)


@login_required
def trash_worker(request, worker_id):
    worker = get_object_or_404(
        SkilledWorker, id=worker_id, contractor=request.user)
    worker.is_trashed = True
    worker.save()
    messages.warning(request, f"⚠️ {worker.name} has been moved to the Trash.")
    return redirect('all_workers')


@login_required
def restore_worker(request, worker_id):
    # Use contractor=request.user here too!
    worker = get_object_or_404(
        SkilledWorker, id=worker_id, contractor=request.user)
    worker.is_trashed = False
    worker.save()
    messages.success(request, f"✅ {worker.name} has been restored.")
    return redirect('workforce_trash')


@login_required
def workforce_trash(request):
    # Fetch everyone in the graveyard
    trashed_workers = SkilledWorker.objects.filter(
        contractor=request.user,
        is_trashed=True
    ).order_by('-id')

    return render(request, 'site_management/workforce_trash.html', {
        'workers': trashed_workers
    })


@login_required
def worker_profile(request, slug):
    # 1. Fetch the specific worker
    worker = get_object_or_404(
        SkilledWorker, slug=slug, contractor=request.user
    )

    # 🚀 THE FIX: Directly query the database for this worker's crew members
    crew_members = SkilledWorker.objects.filter(
        lead_worker=worker, is_trashed=False)

    # 2. Fetch all activity
    history = StaffAttendance.objects.filter(
        worker=worker
    ).order_by('-time_in')

    # 3. Filter for Settlements
    payment_history = history.filter(is_paid=True).order_by('-payment_date')

    # 4. Calculate the Balance
    unpaid_logs = history.filter(is_paid=False)
    unpaid_count = unpaid_logs.count()
    total_debt = unpaid_count * worker.daily_rate

    # 5. Pass crew_members explicitly into the context
    return render(request, 'site_management/worker_profile.html', {
        'worker': worker,
        'site': worker.site,
        'crew_members': crew_members,  # 👈 Added here
        'history': history,
        'payment_history': payment_history,
        'total_days': history.count(),
        'unpaid_days': unpaid_count,
        'total_debt': total_debt,
    })


# @login_required
# def worker_profile(request, slug):
#     # 1. Fetch the specific worker (The "Dossier")
#     worker = get_object_or_404(
#         SkilledWorker, slug=slug, contractor=request.user
#     )

#     # 2. Fetch all activity (Every time they clocked in)
#     history = StaffAttendance.objects.filter(
#         worker=worker
#     ).order_by('-time_in')

#     # 3. Filter for Settlements (Only the logs you've clicked "Paid" on)
#     # We use -payment_date so the most recent money sent is at the top
#     payment_history = history.filter(is_paid=True).order_by('-payment_date')

#     # 4. Calculate the Balance (The math for the orange card)
#     unpaid_logs = history.filter(is_paid=False)
#     unpaid_count = unpaid_logs.count()

#     # Calculation: Days Unpaid x Their Snapshotted Rate (or current rate)
#     total_debt = unpaid_count * worker.daily_rate

#     # 5. Send the "Package" to your Premium HTML
#     return render(request, 'site_management/worker_profile.html', {
#         'worker': worker,
#         'site': worker.site,
#         'history': history,
#         'payment_history': payment_history,
#         'total_days': history.count(),
#         'unpaid_days': unpaid_count,
#         'total_debt': total_debt,
#     })
# #  mark as paid


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

        # Get the company name for the email branding
        company_name = site.company.name

        # 🛡️ THE UPDATED PERMISSION GATE
        is_owner = (site.company.owner == request.user)

        is_pm = Invitation.objects.filter(
            email=request.user.email,
            site=site,
            role_assigned='PROJECT_MANAGER',
            is_used=True
        ).exists()

        if not (is_owner or is_pm):
            messages.error(
                request, "Access Denied: Only Company Owners and PMs can invite staff.")
            return redirect('site_dashboard', site_id=site.id)

        import uuid
        token = uuid.uuid4()
        Invitation.objects.create(
            email=email,
            site=site,
            role_assigned=role,
            invited_by=request.user,
            token=token
        )

        domain = "https://codasite.com.ng"
        invite_link = f"{domain}/account/register/?token={token}"

        from django.conf import settings
        import resend  # Ensure this is imported at the top of your file too

        resend.api_key = settings.RESEND_API_KEY

        # 🏗️ Updated HTML with dynamic Company Name and Brand Footer
        params = {
            "from": settings.DEFAULT_FROM_EMAIL,
            "to": [email],
            "subject": f"🏗️ Invitation: Join {site.name} on CodaSite",
            "html": f"""
                <div style="font-family: sans-serif; padding: 20px; color: #1a202c; border: 1px solid #e2e8f0; border-radius: 12px; max-width: 600px; margin: auto;">
                    <h2 style="color: #0d9488; margin-bottom: 5px;">{company_name}</h2>
                    <p style="font-size: 12px; color: #718096; margin-top: 0; margin-bottom: 20px;">via CodaSite</p>
                    
                    <p>Hello,</p>
                    <p>You have been invited by <strong>{request.user.username}</strong> to join the project at <strong>{site.name}</strong> 
                    as a <strong>{role.replace('_', ' ').title()}</strong>.</p>
                    
                    <p>Click the button below to set up your account and start managing site materials:</p>
                    
                    <div style="margin: 30px 0; text-align: center;">
                        <a href="{invite_link}" style="display: inline-block; padding: 14px 28px; background-color: #0d9488; color: white; text-decoration: none; border-radius: 8px; font-weight: bold; font-size: 16px;">Accept Invitation</a>
                    </div>
                    
                    <p style="margin-top: 20px; font-size: 12px; color: #718096;">If the button doesn't work, copy this link into your browser: <br>{invite_link}</p>
                    
                    <hr style="border: 0; border-top: 1px solid #edf2f7; margin: 20px 0;">
                    
                    <div style="text-align: center;">
                        <p style="font-size: 11px; color: #a0aec0; margin-bottom: 4px;">CodaSite - Construction Management simplified.</p>
                        <p style="font-size: 10px; color: #cbd5e0; font-weight: bold; text-transform: uppercase; letter-spacing: 1px;">Powered by InnoCoda Studio</p>
                    </div>
                </div>
            """
        }

        try:
            resend.Emails.send(params)
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
    # usage_logs = MaterialDeduction.objects.filter(
    #     stock_item__site=site
    # ).select_related('worker', 'stock_item', 'authorized_by').order_by('-timestamp')

    # In your material_usage_report view
    usage_logs = MaterialDeduction.objects.filter(
        stock_item__site=site,
        stock_item__is_returnable=False  # 🚀 Only get consumables
    ).select_related('worker', 'stock_item').order_by('-timestamp')

    # 🎯 FIX THE FILENAME HERE:
    # It must match the file C:\...\site_management\material_usage_report.html
    return render(request, 'site_management/material_usage_report.html', {
        'site': site,
        'usage_logs': usage_logs,
        'company': site.company
    })

# Profiles


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


#  Billings

@login_required
def billing_upgrade(request):
    try:
        company = request.user.company
        subscription = getattr(company, 'subscription', None)
    except Exception:
        company = None
        subscription = None

    context = {
        'company': company,
        'subscription': subscription,
        'paystack_public_key': settings.PAYSTACK_PUBLIC_KEY  # 👈 Add this line!
    }
    return render(request, 'site_management/billing_upgrade.html', context)


@csrf_exempt
def paystack_webhook(request):
    """
    The secure background receiver that catches successful payments.
    """
    if request.method == 'POST':
        payload = request.body
        paystack_signature = request.headers.get('x-paystack-signature')

        # 1. VERIFY THE SIGNATURE (Security Check)
        secret_key = settings.PAYSTACK_SECRET_KEY.encode('utf-8')
        computed_hash = hmac.new(
            secret_key, payload, hashlib.sha512).hexdigest()

        if computed_hash == paystack_signature:
            event_data = json.loads(payload)

            # 👇 THIS IS WHERE YOUR NEW CODE GOES 👇
            # 2. Check if the event is a successful payment
            if event_data.get('event') == 'charge.success':
                data = event_data['data']
                
                # Extract the customer code Paystack sends with every recurring charge
                customer_code = data.get('customer', {}).get('customer_code')

                if customer_code:
                    try:
                        # Find the exact subscription using the code we saved in verify_payment
                        subscription = CompanySubscription.objects.get(paystack_customer_code=customer_code)

                        # 🔥 Renew access for another 30 days!
                        subscription.status = 'ACTIVE'
                        subscription.next_billing_date = timezone.now() + timedelta(days=30)
                        
                        # (Optional) Update tier if custom_fields happens to be present
                        metadata = data.get('metadata', {})
                        for field in metadata.get('custom_fields', []):
                            if field.get('variable_name') == 'tier':
                                subscription.tier = field.get('value').upper()

                        subscription.save()

                        print(f"SUCCESS: Webhook renewed 30-day access for {subscription.company.company_name}")
                    except CompanySubscription.DoesNotExist:
                        print(f"Webhook Database Error: No subscription found for customer_code {customer_code}")
            # 👆 END OF NEW CODE 👆

        # Always return 200 OK to Paystack
        return HttpResponse(status=200)

    return HttpResponse(status=400)

# @login_required
# def verify_payment(request, reference):
#     """
#     Frontend verification. Calls Paystack API directly to confirm status.
#     """
#     paystack_url = f"https://api.paystack.co/transaction/verify/{reference}"
#     headers = {
#         "Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}",
#         "Content-Type": "application/json",
#     }

#     try:
#         response = requests.get(paystack_url, headers=headers)
#         response_data = response.json()

#         if response_data.get('status') and response_data['data']['status'] == 'success':
#             # 🚀 PAYMENT CONFIRMED BY PAYSTACK!
#             metadata = response_data['data'].get('metadata', {})
#             custom_fields = metadata.get('custom_fields', [])

#             # Safely extract the tier name
#             tier_name = 'PRO'  # Default fallback
#             for item in custom_fields:
#                 if item.get('variable_name') == 'tier':
#                     tier_name = item.get('value')
#                     break

#             company = request.user.company

#             # Safely get or create the subscription
#             subscription, created = CompanySubscription.objects.get_or_create(
#                 company=company)

#             # 🟢 UPDATE THE REAL DATABASE FIELDS
#             subscription.status = 'ACTIVE'
#             subscription.tier = tier_name.upper()
#             subscription.next_billing_date = timezone.now() + timedelta(days=30)
#             subscription.save()

#             print(
#                 f"✅ SUCCESS: Unlocked workspace for {company.company_name} on the {tier_name} tier!")
#             return JsonResponse({'status': 'verified', 'message': 'Subscription activated successfully.'})

#         else:
#             return JsonResponse({'status': 'failed', 'message': 'Transaction was not successful on Paystack.'}, status=400)

#     except Exception as e:
#         print(f"🚨 SYSTEM ERROR during verification: {str(e)}")
#         return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

@login_required
def verify_payment(request, reference):
    """
    Frontend verification. Calls Paystack API directly to confirm status.
    """
    paystack_url = f"https://api.paystack.co/transaction/verify/{reference}"
    headers = {
        "Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}",
        "Content-Type": "application/json",
    }

    try:
        response = requests.get(paystack_url, headers=headers)
        response_data = response.json()

        import json


        # 👇 THIS IS WHERE YOUR NEW CODE GOES 👇
        if response_data.get('status') and response_data['data']['status'] == 'success':
            # 🚀 PAYMENT CONFIRMED BY PAYSTACK!
            metadata = response_data['data'].get('metadata', {})
            custom_fields = metadata.get('custom_fields', [])
            
            # 👈 Extract the Paystack Customer Code
            customer_code = response_data['data']['customer']['customer_code']

            # Safely extract the tier name
            tier_name = 'PRO'  # Default fallback
            for item in custom_fields:
                if item.get('variable_name') == 'tier':
                    tier_name = item.get('value')
                    break

            company = request.user.company

            # Safely get or create the subscription
            subscription, created = CompanySubscription.objects.get_or_create(company=company)

            # 🟢 UPDATE THE REAL DATABASE FIELDS
            subscription.status = 'ACTIVE'
            subscription.tier = tier_name.upper()
            subscription.next_billing_date = timezone.now() + timedelta(days=30)
            
            # 👈 Save the customer code so the Webhook can find them next month!
            subscription.paystack_customer_code = customer_code 
            subscription.save()

            print(f"✅ SUCCESS: Unlocked workspace for {company.name} on the {tier_name} tier!")
            return JsonResponse({'status': 'verified', 'message': 'Subscription activated successfully.'})
        # 👆 END OF NEW CODE 👆

        else:
            return JsonResponse({'status': 'failed', 'message': 'Transaction was not successful on Paystack.'}, status=400)

    except Exception as e:
        print(f"🚨 SYSTEM ERROR during verification: {str(e)}")
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)




"""
    monday sender automaticaly itself
"""
def trigger_weekly_reports_cron(request):
    """
    Secret HTTP endpoint to trigger send_weekly_summaries via cron-job.org
    """
    secret_key = request.GET.get('key')
    expected_key = os.environ.get('CRON_SECRET_KEY', 'codasite-secret-cron-key-2026')

    if secret_key != expected_key:
        return HttpResponseForbidden("Unauthorized access")

    try:
        # Executes python manage.py send_weekly_summaries
        call_command('send_weekly_summaries')
        return JsonResponse({'status': 'success', 'message': 'Weekly summaries successfully dispatched!'})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)