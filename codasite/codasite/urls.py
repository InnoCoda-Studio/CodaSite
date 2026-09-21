import os
from django.conf import settings
from django.contrib import admin
from django.urls import include, path
from django.http import HttpResponse, Http404
from django.conf.urls.static import static
from django.views.static import serve 
import re
from account import views as account_views

def serve_static_root_file(request, filename):
    file_path = os.path.join(settings.BASE_DIR, 'static', filename)
    if os.path.exists(file_path):
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        content_type = 'application/javascript' if filename.endswith('.js') else 'application/json'
        response = HttpResponse(content, content_type=content_type)
        if filename == 'sw.js':
            response['Service-Worker-Allowed'] = '/'
        return response
    raise Http404(f"{filename} not found")

urlpatterns = [
    path('ojibo-ogala!/', admin.site.urls),

    # Map the absolute root domain directly to the account landing page view
    path('landing/', account_views.landing_page, name='landing_page'),

    path('account/', include('account.urls')),
    path('', include('site_management.urls')),
    
    # Serve PWA files directly from the static directory
    path('sw.js', lambda r: serve_static_root_file(r, 'sw.js')),
    path('manifest.json', lambda r: serve_static_root_file(r, 'manifest.json')),
]

# This allows you to see the photos/videos while you are developing
if not settings.DEBUG:
    urlpatterns += [
        path('static/<path:path>', serve,
             {'document_root': settings.STATIC_ROOT}),
    ]