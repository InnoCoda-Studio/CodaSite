from django.core.management.base import BaseCommand
from site_management.models import SiteLocation
from site_management.reports import get_weekly_summary, send_resend_audit_email
import logging

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Automatically sends weekly reports to all site stakeholders'

    def handle(self, *args, **options):
        # You might want to filter this later: SiteLocation.objects.filter(is_active=True)
        active_sites = SiteLocation.objects.all()

        if not active_sites.exists():
            self.stdout.write(self.style.WARNING("No active sites found."))
            return

        for site in active_sites:
            try:
                self.stdout.write(f"⚙️ Building weekly report for: {site.name}...")
                
                # 1. Get the data for this specific site
                summary = get_weekly_summary(site.id)

                # 2. 🚀 Dispatch using the fixed Resend engine!
                # This automatically generates the PDF, applies the HTML template, 
                # and sends it via the official Resend API.
                success = send_resend_audit_email(data=summary, report_type="WEEKLY")

                if success:
                    self.stdout.write(self.style.SUCCESS(
                        f'✅ Successfully dispatched report for {site.name}'))
                else:
                    self.stdout.write(self.style.ERROR(
                        f'❌ Failed to send report for {site.name}. Check Render/Resend logs.'))

            except Exception as e:
                logger.error(
                    f"Crash while processing automated report for site {site.id}: {e}")
                self.stdout.write(self.style.ERROR(f"Critical error on {site.name}: {e}"))
                
        self.stdout.write(self.style.SUCCESS("🎉 All automated weekly reports processed!"))