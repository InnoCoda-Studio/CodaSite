from django.utils import timezone
from django.db.models import Sum, F
from .models import StaffAttendance
import datetime
# Inside utils.py - replace the old get_weekly_summary function with this:
from .reports import get_weekly_summary


# def get_weekly_summary(site_id):
#     today = timezone.now().date()
#     # Find last Monday (Start of the week)
#     start_of_week = today - datetime.timedelta(days=today.weekday())

#     # Calculate total payroll for the week at this site
#     attendance = StaffAttendance.objects.filter(
#         site_id=site_id,
#         time_in__date__gte=start_of_week,
#         time_out__isnull=False  # Only pay for completed shifts
#     )

#     # Logic: Hours worked * Worker's daily rate (assuming daily rate for now)
#     total_payroll = attendance.aggregate(
#         total=Sum('worker__daily_rate'))['total'] or 0
#     total_workers = attendance.values('worker').distinct().count()

#     return {
#         'total_payroll': total_payroll,
#         'total_workers': total_workers
#     }


def get_monthly_summary(site_id):
    today = timezone.now().date()
    start_of_month = today.replace(day=1)

    attendance = StaffAttendance.objects.filter(
        site_id=site_id,
        time_in__date__gte=start_of_month,
        time_out__isnull=False
    )

    total_payroll = attendance.aggregate(
        total=Sum('worker__daily_rate'))['total'] or 0

    return {
        'total_payroll': total_payroll
    }
