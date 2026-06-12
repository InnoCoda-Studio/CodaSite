from django.shortcuts import redirect
from django.urls import reverse

class SubscriptionEnforcementMiddleware:
    """
    The Bouncer: Checks every incoming request to ensure the company has paid.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # 1. We only check users who are actually logged in
        if request.user.is_authenticated:

            # 2. THE WHITELIST: Pages the user is ALWAYS allowed to see
            allowed_paths = [
                '/account/login/',
                '/account/logout/',
                '/admin/',  # Don't lock yourself out of the admin panel!
                '/billing/upgrade/',  
                '/billing/paystack-webhook/',  
                '/billing/verify-payment/',  # 👈 CRITICAL FIX: Allow the JS to verify successful payments!
            ]

            # Check if the URL they are trying to visit is safe
            is_safe_path = any(request.path.startswith(path)
                               for path in allowed_paths)

            # 3. If they are trying to access the actual construction app and it's NOT a safe path
            if not is_safe_path:
                # Assuming the user is linked to a company profile
                if hasattr(request.user, 'company_owner'):
                    company = request.user.company_owner

                    try:
                        subscription = company.subscription
                        # 🚨 THE LOCKDOWN TRIGGER
                        if not subscription.is_access_valid:
                            # Bouncer says no. Send them to the Paywall.
                            return redirect('/billing/upgrade/')
                    except:
                        # If for some weird reason they don't have a subscription row at all
                        return redirect('/billing/upgrade/')

        # 4. If everything is good, let them through to the page they requested
        response = self.get_response(request)
        return response