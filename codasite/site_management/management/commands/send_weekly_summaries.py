# site_management/management/commands/send_weekly_summaries.py

from django.core.management.base import BaseCommand
from site_management.models import SiteLocation
from site_management.reports import get_weekly_summary, generate_pdf_report
from django.core.mail import EmailMessage
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Automatically sends weekly reports to all site stakeholders'

    def handle(self, *args, **options):
        active_sites = SiteLocation.objects.all()

        for site in active_sites:
            try:
                # 1. Get the data for this specific site
                summary = get_weekly_summary(site.id)

                # 2. Generate the Weekly PDF
                pdf_content = generate_pdf_report(
                    summary, 'reports/weekly_pdf_template.html')

                # 3. Build and Send Email
                email = EmailMessage(
                    subject=f"AUTOMATED WEEKLY AUDIT: {site.name}",
                    body=f"Hello,\n\nThis is an automated weekly summary for the {site.name} project.",
                    from_email='innocoda.support@gmail.com',
                    to=summary['recipients'],
                )

                if pdf_content:
                    email.attach(
                        f"Weekly_Audit_{site.name}.pdf", pdf_content, 'application/pdf')
                    email.send()
                    self.stdout.write(self.style.SUCCESS(
                        f'Successfully sent report for {site.name}'))

            except Exception as e:
                logger.error(
                    f"Failed to send automated report for site {site.id}: {e}")
