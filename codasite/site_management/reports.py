# site_management/reports.py

from .models import (
    MaterialDeduction,
    StaffAttendance,
    CompanyProfile,
    SiteLocation,
    Invitation,
    MaterialStock,
    SkilledWorker,
    CategoryPay,
)
from django.db.models import Count
from datetime import timedelta
from django.utils import timezone
from django.template.loader import get_template
from io import BytesIO
from django.db.models import Sum


# 🛡️ SAFE IMPORT: This prevents the ModuleNotFoundError on Render
try:
    from xhtml2pdf import pisa
except ImportError:
    pisa = None


def generate_pdf_report(data, template_name):
    """Converts a specific HTML template into a PDF binary."""
    # 🛡️ CHECK: If pisa isn't installed, return None instead of crashing
    if pisa is None:
        print("PDF Generation skipped: xhtml2pdf is not installed.")
        return None

    template = get_template(template_name)
    html = template.render(data)
    result = BytesIO()
    pdf = pisa.pisaDocument(BytesIO(html.encode("UTF-8")), result)
    return result.getvalue() if not pdf.err else None


def get_daily_summary(site_id):
    """Gathers data for the daily report."""
    today = timezone.now().date()
    site = SiteLocation.objects.get(id=site_id)
    stocks = MaterialStock.objects.filter(site=site)
    company = CompanyProfile.objects.filter(contractor=site.contractor).first()

    deductions = MaterialDeduction.objects.filter(
        stock_item__site=site, timestamp__date=today)
    attendance = StaffAttendance.objects.filter(site=site, time_in__date=today)

    recipients = [site.contractor.email] if site.contractor.email else []
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
    """The 'Master' Engine: Calculates money and attendance for any date range."""
    site = SiteLocation.objects.get(id=site_id)
    company = CompanyProfile.objects.filter(contractor=site.contractor).first()
    stocks = MaterialStock.objects.filter(site=site)

    # 1. Grab all attendance records for this date range
    attendance_records = StaffAttendance.objects.filter(
        site=site,
        time_in__date__range=[start_date, end_date]
    )

    # 2. GROUP logic: Count how many unique days each worker appeared
    # This is much faster than looping manually
    attendance_summary = attendance_records.values('worker', 'worker__name', 'worker__category', 'worker__daily_rate', 'worker__pay_frequency').annotate(
        days_present=Count('time_in__date', distinct=True)
    )

    staff_summary = []
    total_payroll = 0

    # 3. Process the results
    for item in attendance_summary:
        if not item['worker']:
            continue

        days_present = item['days_present']
        daily_rate = item['worker__daily_rate'] or 0

        # 💰 MONEY LOGIC
        if item['worker__pay_frequency'] == 'DAILY':
            earnings = days_present * daily_rate
        else:
            earnings = daily_rate  # Assuming daily_rate field stores flat rate for others

        total_payroll += earnings

        staff_summary.append({
            'name': item['worker__name'],
            'category': item['worker__category'],
            'days_present': days_present,
            'total_pay': earnings,
            'daily_rate': daily_rate
        })

    # 4. Return the Final Package
    return {
        'site': site,
        'company': company,
        'stocks': stocks,
        'start_date': start_date,
        'end_date': end_date,
        'staff_summary': staff_summary,
        'total_payroll': total_payroll,
        'total_workers': len(staff_summary),
        'recipients': [site.contractor.email] if site.contractor.email else ['innocoda.support@gmail.com']
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
    attendance = StaffAttendance.objects.filter(site=site)

    total_spent_so_far = 0
    worker_pay_details = []

    # Get all workers who have clocked in at least once
    workers = SkilledWorker.objects.filter(
        staffattendance__site=site).distinct()

    for worker in workers:
        # 1. Find the rate for this worker's category at this site
        cat_pay = CategoryPay.objects.filter(
            site=site, category=worker.category).first()
        rate = cat_pay.default_daily_rate if cat_pay else worker.daily_rate

        # 2. Count days worked
        days = attendance.filter(worker=worker).values(
            'time_in__date').distinct().count()

        amount_due = days * rate
        total_spent_so_far += amount_due

        worker_pay_details.append({
            'name': worker.name,
            'days': days,
            'amount': amount_due
        })

    return {
        'total_spent': total_spent_so_far,
        'worker_details': worker_pay_details
    }
