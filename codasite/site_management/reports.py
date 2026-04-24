# # site_management/reports.py

# from .models import (
#     MaterialDeduction,
#     StaffAttendance,
#     CompanyProfile,
#     SiteLocation,
#     Invitation,
#     MaterialStock,
#     SkilledWorker,
#     CategoryPay,
# )
# from django.db.models import Count
# from datetime import timedelta
# from django.utils import timezone
# from django.template.loader import get_template
# from io import BytesIO
# from django.db.models import Sum


# # 🛡️ SAFE IMPORT: This prevents the ModuleNotFoundError on Render
# try:
#     from xhtml2pdf import pisa
# except ImportError:
#     pisa = None


# def generate_pdf_report(data, template_name):
#     """Converts a specific HTML template into a PDF binary."""
#     # 🛡️ CHECK: If pisa isn't installed, return None instead of crashing
#     if pisa is None:
#         print("PDF Generation skipped: xhtml2pdf is not installed.")
#         return None

#     template = get_template(template_name)
#     html = template.render(data)
#     result = BytesIO()
#     pdf = pisa.pisaDocument(BytesIO(html.encode("UTF-8")), result)
#     return result.getvalue() if not pdf.err else None


# def get_daily_summary(site_id):
#     """Gathers data for the daily report."""
#     today = timezone.now().date()
#     site = SiteLocation.objects.get(id=site_id)
#     stocks = MaterialStock.objects.filter(site=site)
#     company = CompanyProfile.objects.filter(contractor=site.contractor).first()

#     deductions = MaterialDeduction.objects.filter(
#         stock_item__site=site, timestamp__date=today)
#     attendance = StaffAttendance.objects.filter(site=site, time_in__date=today)

#     recipients = [site.contractor.email] if site.contractor.email else []
#     staff_emails = Invitation.objects.filter(
#         site=site, is_used=True).values_list('email', flat=True)
#     recipients.extend(list(staff_emails))
#     clean_recipients = list(set([e for e in recipients if e and e.strip()])) or [
#         'innocoda.support@gmail.com']

#     return {
#         'site': site, 'today': today, 'company': company, 'stocks': stocks,
#         'deductions': deductions, 'attendance': attendance,
#         'recipients': clean_recipients, 'total_workers': attendance.count()
#     }


# # def get_aggregated_report(site_id, start_date, end_date):
# #     """The 'Master' Engine: Calculates money and attendance for any date range."""
# #     site = SiteLocation.objects.get(id=site_id)
# #     company = CompanyProfile.objects.filter(contractor=site.contractor).first()
# #     stocks = MaterialStock.objects.filter(site=site)

# #     # 1. Grab all attendance records for this date range
# #     attendance_records = StaffAttendance.objects.filter(
# #         site=site,
# #         time_in__date__range=[start_date, end_date]
# #     )

# #     # 2. GROUP logic: Count how many unique days each worker appeared
# #     # This is much faster than looping manually
# #     attendance_summary = attendance_records.values('worker', 'worker__name', 'worker__category', 'worker__daily_rate', 'worker__pay_frequency').annotate(
# #         days_present=Count('time_in__date', distinct=True)
# #     )

# #     staff_summary = []
# #     total_payroll = 0

# #     # 3. Process the results
# #     for item in attendance_summary:
# #         if not item['worker']:
# #             continue

# #         days_present = item['days_present']
# #         daily_rate = item['worker__daily_rate'] or 0

# #         # 💰 MONEY LOGIC
# #         if item['worker__pay_frequency'] == 'DAILY':
# #             earnings = days_present * daily_rate
# #         else:
# #             earnings = daily_rate  # Assuming daily_rate field stores flat rate for others

# #         total_payroll += earnings

# #         staff_summary.append({
# #             'name': item['worker__name'],
# #             'category': item['worker__category'],
# #             'days_present': days_present,
# #             'total_pay': earnings,
# #             'daily_rate': daily_rate
# #         })

# #     # 4. Return the Final Package
# #     return {
# #         'site': site,
# #         'company': company,
# #         'stocks': stocks,
# #         'start_date': start_date,
# #         'end_date': end_date,
# #         'staff_summary': staff_summary,
# #         'total_payroll': total_payroll,
# #         'total_workers': len(staff_summary),
# #         'recipients': [site.contractor.email] if site.contractor.email else ['innocoda.support@gmail.com']
# #     }

# def get_aggregated_report(site_id, start_date, end_date):
#     """The 'Master' Engine: Uses the rate saved AT THE TIME of clock-in."""
#     site = SiteLocation.objects.get(id=site_id)
#     # company = CompanyProfile.objects.filter(contractor=site.contractor).first()
#     # ✅ Use company now
#     company = site.company
#     stocks = MaterialStock.objects.filter(site=site)

#     # 1. Grab attendance records
#     attendance_records = StaffAttendance.objects.filter(
#         site=site,
#         time_in__date__range=[start_date, end_date]
#     )

#     # 2. Use the 'daily_rate_at_time' field for 100% audit accuracy
#     staff_summary_map = {}
#     total_payroll = 0

#     for record in attendance_records:
#         if not record.worker:
#             continue

#         worker_id = record.worker.id
#         if worker_id not in staff_summary_map:
#             staff_summary_map[worker_id] = {
#                 'name': record.worker.name,
#                 'category': record.worker.category,
#                 'days_present': 0,
#                 'total_pay': 0,
#                 'daily_rate': record.daily_rate_at_time  # Snapshot
#             }

#         staff_summary_map[worker_id]['days_present'] += 1
#         staff_summary_map[worker_id]['total_pay'] += record.daily_rate_at_time
#         total_payroll += record.daily_rate_at_time

#     return {
#         'site': site,
#         'company': company,
#         'stocks': stocks,
#         'start_date': start_date,
#         'end_date': end_date,
#         'staff_summary': list(staff_summary_map.values()),
#         'total_payroll': total_payroll,
#         'total_workers': len(staff_summary_map),
#         'recipients': [site.contractor.email] if site.contractor.email else ['innocoda.support@gmail.com']
#     }


# def get_weekly_summary(site_id):
#     today = timezone.now().date()
#     start_of_week = today - timedelta(days=today.weekday())
#     return get_aggregated_report(site_id, start_of_week, today)


# def get_monthly_summary(site_id):
#     today = timezone.now().date()
#     start_of_month = today.replace(day=1)
#     return get_aggregated_report(site_id, start_of_month, today)


# # def get_live_site_spend(site_id):
# #     site = SiteLocation.objects.get(id=site_id)
# #     attendance = StaffAttendance.objects.filter(site=site)

# #     total_spent_so_far = 0
# #     worker_pay_details = []

# #     # Get all workers who have clocked in at least once
# #     workers = SkilledWorker.objects.filter(
# #         staffattendance__site=site).distinct()

# #     for worker in workers:
# #         # 1. Find the rate for this worker's category at this site
# #         cat_pay = CategoryPay.objects.filter(
# #             site=site, category=worker.category).first()
# #         rate = cat_pay.default_daily_rate if cat_pay else worker.daily_rate

# #         # 2. Count days worked
# #         days = attendance.filter(worker=worker).values(
# #             'time_in__date').distinct().count()

# #         amount_due = days * rate
# #         total_spent_so_far += amount_due

# #         worker_pay_details.append({
# #             'name': worker.name,
# #             'days': days,
# #             'amount': amount_due
# #         })

# #     return {
# #         'total_spent': total_spent_so_far,
# #         'worker_details': worker_pay_details
# #     }

# def get_live_site_spend(site_id):
#     """Calculates total spend based on actual historical records."""
#     site = SiteLocation.objects.get(id=site_id)
#     # Sum the daily_rate_at_time for every clock-in ever recorded at this site
#     total_spent = StaffAttendance.objects.filter(site=site).aggregate(
#         total=Sum('daily_rate_at_time'))['total'] or 0

#     # Detailed breakdown
#     worker_details = StaffAttendance.objects.filter(site=site).values(
#         'worker__name').annotate(
#             days=Count('id'),
#             amount=Sum('daily_rate_at_time')
#     ).order_by('-amount')

#     return {
#         'total_spent': total_spent,
#         'worker_details': worker_details
#     }
# site_management/reports.py

from django.template.loader import render_to_string

import os
import base64
import resend
from .models import (
    MaterialDeduction,
    StaffAttendance,
    SiteLocation,
    Invitation,
    MaterialStock,
    SkilledWorker,
    CategoryPay,
)
from django.db.models import Count, Sum
from datetime import timedelta
from django.utils import timezone
from django.template.loader import get_template
from io import BytesIO

from account.models import Company

# 🛡️ SAFE IMPORT
try:
    from xhtml2pdf import pisa
except ImportError:
    pisa = None


def generate_pdf_report(data, template_name):
    if pisa is None:
        return None
    template = get_template(template_name)
    html = template.render(data)
    result = BytesIO()
    pisa.pisaDocument(BytesIO(html.encode("UTF-8")), result)
    return result.getvalue()


def get_daily_summary(site_id):
    """Gathers data for the daily report."""
    today = timezone.now().date()
    site = SiteLocation.objects.get(id=site_id)
    stocks = MaterialStock.objects.filter(site=site)

    # ✅ FIX 1: Access company directly from site
    company = site.company

    deductions = MaterialDeduction.objects.filter(
        stock_item__site=site, timestamp__date=today)
    attendance = StaffAttendance.objects.filter(site=site, time_in__date=today)

    # ✅ FIX 2: Recipients must go through site.company.contractor
    contractor_email = site.company.owner.email if site.company and site.company.owner else None
    recipients = [contractor_email] if contractor_email else []

    staff_emails = Invitation.objects.filter(
        site=site, is_used=True).values_list('email', flat=True)
    recipients.extend(list(staff_emails))
    clean_recipients = list(set([e for e in recipients if e and e.strip()])) or [
        'innocoda.support@gmail.com']

    return {
        'site': site, 'today': today, 'company': company, 'stocks': stocks,
        'deductions': deductions, 'attendance': attendance,
        'recipients': clean_recipients, 'total_workers': attendance.count()
    }


def get_aggregated_report(site_id, start_date, end_date):
    site = SiteLocation.objects.get(id=site_id)
    company = site.company
    stocks = MaterialStock.objects.filter(site=site)

    category_name = record.worker.get_category_display() if hasattr(
        record.worker, 'get_category_display') else record.worker.category

    attendance_records = StaffAttendance.objects.filter(
        site=site,
        time_in__date__range=[start_date, end_date]
    )

    staff_summary_map = {}
    total_payroll = 0

    for record in attendance_records:
        if not record.worker:
            continue

        worker_id = record.worker.id

        # 🕒 CALCULATE HOURS
        duration_hours = 0
        if record.time_in and record.time_out:
            diff = record.time_out - record.time_in
            duration_hours = round(diff.total_seconds() / 3600, 1)

        if worker_id not in staff_summary_map:
            staff_summary_map[worker_id] = {
                'name': record.worker.name,
                'category': category_name,
                'category': record.worker.category,
                'days_present': 0,
                'total_pay': 0,
                'total_hours': 0,  # 👈 Initialize Hours
                'daily_rate': record.daily_rate_at_time
            }

        staff_summary_map[worker_id]['days_present'] += 1
        staff_summary_map[worker_id]['total_pay'] += record.daily_rate_at_time
        # 👈 Add Hours
        staff_summary_map[worker_id]['total_hours'] += duration_hours
        total_payroll += record.daily_rate_at_time

    contractor_email = site.company.owner.email if site.company and site.company.owner else None

    return {
        'site': site,
        'company': company,
        'stocks': stocks,
        'start_date': start_date,
        'end_date': end_date,
        'staff_summary': list(staff_summary_map.values()),
        'total_payroll': total_payroll,
        'total_workers': len(staff_summary_map),
        'recipients': [contractor_email] if contractor_email else ['innocoda.support@gmail.com']
    }


def get_weekly_summary(site_id):
    today = timezone.now().date()
    start_of_week = today - timedelta(days=today.weekday())
    return get_aggregated_report(site_id, start_of_week, today)


def get_monthly_summary(site_id):
    today = timezone.now().date()
    start_of_month = today.replace(day=1)
    return get_aggregated_report(site_id, start_of_month, today)


def get_live_site_spend(site_id):
    site = SiteLocation.objects.get(id=site_id)
    total_spent = StaffAttendance.objects.filter(site=site).aggregate(
        total=Sum('daily_rate_at_time'))['total'] or 0

    worker_details = StaffAttendance.objects.filter(site=site).values(
        'worker__name').annotate(
            days=Count('id'),
            amount=Sum('daily_rate_at_time')
    ).order_by('-amount')

    return {'total_spent': total_spent, 'worker_details': worker_details}


# 🔑 Add RESEND_API_KEY to your Render Environment Variables
resend.api_key = os.environ.get("RESEND_API_KEY")


def send_resend_audit_email(data, report_type="DAILY"):
    """
    The High-End Dispatcher: 
    Now handles both DAILY and WEEKLY audit types.
    """
    try:
        from .reports import generate_pdf_report

        # 📂 1. Pick the right template for the PDF
        pdf_template = 'reports/pdf_template.html' if report_type == "DAILY" else 'reports/weekly_pdf_template.html'

        pdf_content = generate_pdf_report(data, pdf_template)
        if not pdf_content:
            return False

        # 📧 2. Pick the right template for the Email Body
        email_template = 'site_management/daily_report_email.html' if report_type == "DAILY" else 'site_management/weekly_report_email.html'
        html_body = render_to_string(email_template, data)

        # 🛡️ 3. Encoding
        attachment_content = base64.b64encode(pdf_content).decode()

        # 🚀 4. The Dispatch
        subject_label = "DAILY SITE AUDIT" if report_type == "DAILY" else "WEEKLY EXECUTIVE SUMMARY"

        params = {
            "from": "CodaSite Audit <reports@codasite.com.ng>",
            "to": data['recipients'],
            "subject": f"🏗️ {subject_label}: {data['site'].name}",
            "html": html_body,
            "attachments": [
                {
                    "filename": f"{report_type}_Report_{data['site'].name}.pdf",
                    "content": attachment_content,
                }
            ],
        }

        resend.Emails.send(params)
        return True
    except Exception as e:
        print(f"RESEND ERROR: {e}")
        return False
