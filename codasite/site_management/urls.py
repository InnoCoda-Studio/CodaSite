from django.urls import path
from . import views
from django.contrib.auth import views as auth_views

urlpatterns = [
    # --- CORE NAVIGATION ---
    path('', views.index, name='index'),
    path('profile/', views.profile_view, name='profile'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('profile/update-logo/', views.update_company_logo,
         name='update_company_logo'),
    path('profile/update-name/', views.update_company_name,
         name='update_company_name'),

    # --- SITE MANAGEMENT ---
    path('add-site/', views.add_site, name='add_site'),
    path('update-site/<int:site_id>/', views.update_site, name='update_site'),
    path('site/<int:site_id>/', views.site_dashboard, name='site_dashboard'),
    path('site/<int:site_id>/operations/',
         views.site_operations, name='site_operations'),
    path('site/<int:site_id>/warehouse/',
         views.site_warehouse, name='site_warehouse'),

    # --- REPORTS & LEDGERS ---
    path('site/<int:site_id>/report/', views.daily_report, name='daily_report'),
    path('site/<int:site_id>/weekly-report/',
         views.send_weekly_report, name='send_weekly_report'),
    path('site/<int:site_id>/close-day/',
         views.close_site_day, name='close_site_day'),
    path('site/<int:site_id>/restock-history/',
         views.restock_history, name='restock_history'),
    path('site/<int:site_id>/material-report/',
         views.material_usage_report, name='material_usage_report'),

    # --- WORKFORCE MANAGEMENT ---
    path('workers/', views.all_workers, name='all_workers'),
    path('workers/search/', views.worker_search,
         name='worker_search'),  # HTMX Search
    path('site/<int:site_id>/add-worker/', views.add_worker, name='add_worker'),
    path('worker/<slug:slug>/', views.worker_profile, name='worker_profile'),
    path('site/<int:site_id>/deploy/', views.deploy_worker, name='deploy_worker'),
    path('worker/<int:worker_id>/trash/',
         views.trash_worker, name='trash_worker'),
    path('worker/<int:worker_id>/restore/',
         views.restore_worker, name='restore_worker'),
    path('workforce/trash/', views.workforce_trash, name='workforce_trash'),
    path('site/<int:site_id>/worker/<int:worker_id>/history/',
         views.worker_history_modal, name='worker_history_modal'),

    # --- STAFF INVITATIONS ---
    path('invite/', views.invite_staff, name='invite_staff'),
    path('block-staff/<int:invite_id>/', views.block_staff, name='block_staff'),
    path('manage-staff/<int:invitation_id>/',
         views.manage_staff_access, name='manage_staff_access'),

    # --- ATTENDANCE & PAYROLL ---
    path('attendance/<int:attendance_id>/pay/',
         views.mark_as_paid, name='mark_as_paid'),

    # --- QR & BIOMETRICS ---
    path('site/<int:site_id>/generate-qr/',
         views.generate_site_qr, name='generate_site_qr'),
    path('attendance/scan/<int:site_id>/',
         views.attendance_scan_portal, name='attendance_scan_portal'),
    path('attendance/process-clock/<int:site_id>/',
         views.process_biometric_clock, name='process_clock'),
    path('site/<int:site_id>/process-biometric/',
         views.process_biometric_clock, name='process_biometric_clock'),
    path('attendance/verify/<int:site_id>/',
         views.verify_worker_identity, name='verify_worker_identity'),

    # --- HTMX DYNAMIC FRAGMENTS ---
    path('htmx/clock-in/<int:site_id>/',
         views.htmx_clock_in, name='htmx_clock_in'),
    path('htmx/clock-out/<int:site_id>/',
         views.htmx_clock_out, name='htmx_clock_out'),
    path('htmx/finance-summary/<int:site_id>/',
         views.htmx_finance_summary, name='htmx_finance_summary'),
]
