from django.apps import AppConfig
from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.core.mail import send_mail
from .models import MaterialInventory


@receiver(post_save, sender=MaterialInventory)
def notify_contractor_material(sender, instance, created, **kwargs):
    if created:
        subject = f"Alert: New Material at {instance.site.name}"
        message = f"Oga, {instance.quantity} {instance.unit} of {instance.item_name} has been logged for {instance.purpose}."
        recipient_list = [instance.site.contractor.email]

        send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, recipient_list)


class SiteManagementConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'site_management'

    def ready(self):
        # 🚨 THIS IS THE TRIGGER: It wakes up your signal when the server starts
        import site_management.signals
