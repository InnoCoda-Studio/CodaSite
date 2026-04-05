# site_management/context_processors.py

def active_site_processor(request):
    """
    This makes 'active_site_id' available in EVERY template 
    so the Live Ops button knows where to go.
    """
    return {
        'active_site_id': request.session.get('active_site_id')
    }
