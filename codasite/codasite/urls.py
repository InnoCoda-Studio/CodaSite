"""
URL configuration for codasite project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.static import serve  # Add this import
import re
from account import views as account_views


urlpatterns = [
    path('ojibo-ogala!/', admin.site.urls),


    # 👈 2. Map the absolute root domain directly to the account landing page view
    path('landing/', account_views.landing_page, name='landing_page'),

    path('account/', include('account.urls')),
    path('', include('site_management.urls')),
]
# 📸 This allows you to see the photos/videos while you are developing
if not settings.DEBUG:
    urlpatterns += [
        path('static/<path:path>', serve,
             {'document_root': settings.STATIC_ROOT}),
    ]
