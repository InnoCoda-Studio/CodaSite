from django.urls import path
from . import views
from django.contrib.auth import views as auth_views  # 👈 Add this import

urlpatterns = [
    path('', views.index, name='index'),
    path('add-site/', views.add_site, name='add_site'),
    path('site/<int:site_id>/', views.site_dashboard, name='site_dashboard'),
    path('site/<int:site_id>/report/', views.daily_report, name='daily_report'),
    path('site/<int:site_id>/add-worker/', views.add_worker, name='add_worker'),
    path('workers/', views.all_workers, name='all_workers'),
    path('worker/<slug:slug>/', views.worker_profile, name='worker_profile'),
    # site_management/urls.py
    path('invite/', views.invite_staff, name='invite_staff'),
    path('site/<int:site_id>/restock-history/',
         views.restock_history, name='restock_history'),
    path('profile/', views.profile_view, name='profile'),
    path('logout/', auth_views.LogoutView.as_view(),
         name='logout'),  # 👈 Add this line

    path('profile/update-logo/', views.update_company_logo,
         name='update_company_logo'),
    path('profile/update-name/', views.update_company_name,
         name='update_company_name'),

    # PDF JENERATOR
    path('site/<int:site_id>/close-day/',
         views.close_site_day, name='close_site_day'),

    # weekly summry
    path('site/<int:site_id>/weekly-report/',
         views.send_weekly_report, name='send_weekly_report'),
    path('site/<int:site_id>/weekly-report/',
         views.send_weekly_report, name='send_weekly_report'),

    path('site/<int:site_id>/operations/',
         views.site_operations, name='site_operations'),
]
