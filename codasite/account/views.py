from django.shortcuts import render
from django.conf import settings
from site_management.models import Invitation  # Import your new models
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
# This is the line you need to fix the "not defined" error:
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth import get_user_model
from .models import Company

User = get_user_model()  # This now points to your custom User with 'is_verified'


def landing_page(request):
    return render(request, 'account/landing_page.html')


def register_view(request):
    token = request.GET.get('token') or request.POST.get('token')
    invitation = None

    # 🛡️ FIX: Use filter instead of get_object_or_404 so it doesn't crash without a token
    if token:
        invitation = Invitation.objects.filter(
            token=token, is_used=False).first()
        if not invitation:
            messages.error(
                request, "This invitation link is invalid or already used.")
            return redirect('login')

    if request.method == 'POST':
        f_name = request.POST.get('full_name', '').strip()
        u_name = request.POST.get('email', '').strip()
        p_word = request.POST.get('password', '')
        c_name = request.POST.get('company_name', '').strip()

        # 1. Validation (Matches your glassmorphism form inputs)
        if not all([u_name, f_name, p_word]) or (not invitation and not c_name):
            messages.error(request, "All fields are required.")
            return redirect(request.path + (f"?token={token}" if token else ""))

        if len(p_word) < 8:
            messages.error(request, "Password must be at least 8 characters.")
            return redirect(request.path + (f"?token={token}" if token else ""))

        if User.objects.filter(username=u_name).exists():
            messages.error(request, "This email is already registered.")
            return redirect('login')

        # 2. Save Logic
        try:
            # Create the User (Email is the Username here)
            new_user = User.objects.create_user(
                username=u_name, email=u_name, password=p_word)
            new_user.first_name = f_name
            new_user.save()

            if invitation:
                # --- STAFF LOGIC ---
                invitation.is_used = True
                invitation.save()
                request.session['assigned_site_id'] = invitation.site.id

                login(request, new_user)
                messages.success(
                    request, f"Welcome to the {invitation.site.name} team!")
                return redirect('site_dashboard', site_id=invitation.site.id)

            else:
                # --- CONTRACTOR LOGIC ---
                # ✅ Linking the 'Company' to the 'User' via the 'owner' field
                Company.objects.create(
                    name=c_name,
                    owner=new_user
                )

                login(request, new_user)
                messages.success(
                    request, f"Company {c_name} established. Welcome, Contractor.")
                return redirect('index')

        except Exception as e:
            messages.error(request, f"System error: {e}")
            return redirect(request.path + (f"?token={token}" if token else ""))

    return render(request, 'account/register.html', {'invitation': invitation, 'token': token})


def login_view(request):
    if request.method == 'POST':
        identifier = request.POST.get('username', '').strip()
        p_word = request.POST.get('password', '')

        # 🏗️ The Logic: Look for the user by email first
        user_obj = User.objects.filter(email=identifier).first()

        if user_obj:
            # If found by email, authenticate using their username
            user = authenticate(
                request, username=user_obj.username, password=p_word)
        else:
            # Otherwise, assume the identifier is the username
            user = authenticate(request, username=identifier, password=p_word)

        # 🧱 The Gatekeeper: Check if authentication passed
        if user is not None:
            login(request, user)
            messages.success(
                request, f"Access Granted. Welcome, {user.first_name}.")
            return redirect('index')
        else:
            messages.error(request, "Access Denied. Invalid credentials.")
            return redirect('login')

    return render(request, 'account/login.html')


def licensing_terms(request):
    return render(request, 'licensing.html')


def terms_of_service(request):
    return render(request, 'terms.html')
