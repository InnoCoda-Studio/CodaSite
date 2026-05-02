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
    path('block-staff/<int:invite_id>/', views.block_staff, name='block_staff'),
    path('manage-staff/<int:invitation_id>/',
         views.manage_staff_access, name='manage_staff_access'),

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

    path('attendance/<int:attendance_id>/pay/',
         views.mark_as_paid, name='mark_as_paid'),


    #
    path('site/<int:site_id>/deploy/', views.deploy_worker, name='deploy_worker'),
    # Restock histry
    path('site/<int:site_id>/restock-history/',
         views.restock_history, name='restock_history'),
    #
    path('site/<int:site_id>/material-report/',
         views.material_usage_report, name='material_usage_report'),

    # 🚀 ADD THIS FOR HTMX SEARCH
    path('workers/search/', views.worker_search, name='worker_search'),



    # 🛰️ HTMX Dynamic Update Paths
    path('htmx/clock-in/<int:site_id>/',
         views.htmx_clock_in, name='htmx_clock_in'),
    path('htmx/clock-out/<int:site_id>/',
         views.htmx_clock_out, name='htmx_clock_out'),
    # path('htmx/clock-out/<int:site_id>/',
    #      views.htmx_clock_out, name='htmx_clock_out'),
    path('htmx/finance-summary/<int:site_id>/',
         views.htmx_finance_summary, name='htmx_finance_summary'),

    path('site/<int:site_id>/warehouse/',
         views.site_warehouse, name='site_warehouse'),

    # Update Site
    path('update-site/<int:site_id>/', views.update_site, name='update_site'),

    # 🎯 1. The PM's Tool: Generates the QR Modal via HTMX
    path('site/<int:site_id>/generate-qr/',
         views.generate_site_qr, name='generate_site_qr'),
    # 📱 2. The Worker's Landing Page: Where the phone goes after scanning
    # We haven't built 'attendance_scan_portal' yet, but let's reserve the road now
    path('attendance/scan/<int:site_id>/',
         views.attendance_scan_portal, name='attendance_scan_portal'),

    path('site/<int:site_id>/worker/<int:worker_id>/history/',
         views.worker_history_modal, name='worker_history_modal'),


]
