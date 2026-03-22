from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import models
from django.contrib.auth import get_user_model
import uuid
from django.utils.text import slugify

User = get_user_model()

# 1. Site Infrastructure


class SiteLocation(models.Model):
    name = models.CharField(max_length=255)  # e.g., "Lekki Phase 1"
    contractor = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='sites')
    is_office = models.BooleanField(default=False)
    address = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    minimum_required = models.IntegerField(default=10, null=True, blank=True)

    def __str__(self):
        return self.name

# 2. Access Control


class Invitation(models.Model):
    ROLE_CHOICES = [
        ('PROJECT_MANAGER', 'Project Manager'),
        ('STOREKEEPER', 'Storekeeper'),
    ]
    email = models.EmailField()
    site = models.ForeignKey(SiteLocation, on_delete=models.CASCADE)
    token = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    invited_by = models.ForeignKey(User, on_delete=models.CASCADE)
    role_assigned = models.CharField(max_length=20, choices=ROLE_CHOICES)
    is_used = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Invite for {self.email} to {self.site.name}"

# 3. Staff & Skilled Workers


class SkilledWorker(models.Model):

    # IDENTITY
    name = models.CharField(max_length=255)
    slug = models.SlugField(unique=True, blank=True, null=True, max_length=100)
    id_number = models.CharField(
        max_length=50, unique=True, null=True, blank=True)
    category = models.CharField(
        max_length=100, help_text="e.g. Mason, Plumber, Supervisor")
    phone = models.CharField(max_length=20, blank=True)
    emergency_contact = models.CharField(max_length=255, null=True, blank=True)

    # 💰 PAYROLL & STATUS
    daily_rate = models.DecimalField(
        max_digits=10, decimal_places=2, default=0.00)
    pay_rate = models.DecimalField(
        max_digits=10, decimal_places=2, default=0.00)

    pay_frequency = models.CharField(
        max_length=50,
        default='Daily',
        help_text="e.g. Daily, Weekly, Per Slab, or Monthly"
    )
    is_sub_contractor = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    date_joined = models.DateField(auto_now_add=True)

    # RELATIONSHIPS
    lead_worker = models.ForeignKey(
        'self', on_delete=models.SET_NULL, null=True, blank=True, related_name='crew')
    site = models.ForeignKey('SiteLocation', on_delete=models.CASCADE,
                             related_name='workers', null=True, blank=True)
    contractor = models.ForeignKey(
        User, on_delete=models.CASCADE, null=True, blank=True)
    profile_picture = models.ImageField(
        upload_to='worker_photos/', null=True, blank=True)
    bank_name = models.CharField(
        max_length=100, null=True, blank=True, help_text="e.g. GTBank, Zenith, OPay")
    account_number = models.CharField(max_length=10, null=True, blank=True)
    account_name = models.CharField(max_length=255, null=True, blank=True)

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.name)
            # We add a short random code (4 characters) to the end
            random_id = str(uuid.uuid4())[:4]

            if self.phone:
                # Name + Phone Suffix + Random Code
                self.slug = f"{base_slug}-{self.phone[-4:]}-{random_id}"
            else:
                # Name + Random Code
                self.slug = f"{base_slug}-{random_id}"

        super().save(*args, **kwargs)

    def __str__(self):
        # Remove get_category_display() because category is a CharField, not a ChoiceField
        return f"{self.name} ({self.category})"


# 4. Daily Site Operations


class DailyWorkLog(models.Model):
    worker = models.ForeignKey(SkilledWorker, on_delete=models.CASCADE)
    site = models.ForeignKey(SiteLocation, on_delete=models.CASCADE)
    date = models.DateField(auto_now_add=True)
    is_contract_job = models.BooleanField(default=False)
    contract_amount = models.DecimalField(
        max_digits=10, decimal_places=2, default=0.00)
    logged_by = models.ForeignKey(User, on_delete=models.CASCADE)

    def __str__(self):
        return f"{self.worker.name} - {self.date}"


class StaffAttendance(models.Model):
    WORK_MODES = [('SITE', 'On-Site'), ('OFFICE', 'In-Office'),
                  ('REMOTE', 'Remote/WfH')]

    # 👷 ADD THIS FIELD to link to your SkilledWorker model
    worker = models.ForeignKey(
        'SkilledWorker', on_delete=models.CASCADE, null=True, blank=True)

    # This tracks which app user (Storekeeper) performed the action
    user = models.ForeignKey(User, on_delete=models.CASCADE)

    site = models.ForeignKey(
        SiteLocation, on_delete=models.SET_NULL, null=True)
    mode = models.CharField(max_length=10, choices=WORK_MODES, default='SITE')

    latitude = models.DecimalField(
        max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(
        max_digits=9, decimal_places=6, null=True, blank=True)

    time_in = models.DateTimeField(auto_now_add=True)  # Captured on Clock In
    time_out = models.DateTimeField(
        null=True, blank=True)  # Captured on Clock Out
    is_paid = models.BooleanField(default=False)
    payment_date = models.DateTimeField(null=True, blank=True)
    payment_reference = models.CharField(max_length=100, null=True, blank=True)

    daily_rate_at_time = models.DecimalField(
        max_digits=10, decimal_places=2, default=0.00)

    class Meta:
        verbose_name_plural = "Staff Attendance"

    def save(self, *args, **kwargs):
        if not self.pk and self.worker:  # On first save
            self.daily_rate_at_time = self.worker.daily_rate
        super().save(*args, **kwargs)

    def __str__(self):
        name = self.worker.name if self.worker else self.user.username
        return f"{name} - {self.time_in.strftime('%d %b, %H:%M')}"

    def get_duration(self):
        """Calculates exact hours and minutes worked."""
        if self.time_in and self.time_out:
            duration = self.time_out - self.time_in
            total_seconds = int(duration.total_seconds())
            hours = total_seconds // 3600
            minutes = (total_seconds % 3600) // 60
            if hours > 0:
                return f"{hours}h {minutes}m"
            return f"{minutes}m"
        return "--"


class MaterialStock(models.Model):
    site = models.ForeignKey(
        SiteLocation, on_delete=models.CASCADE, related_name='stocks')
    item_name = models.CharField(max_length=255, db_index=True)
    current_balance = models.DecimalField(
        max_digits=12, decimal_places=2, default=0)

    minimum_required = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=10
    )

    unit = models.CharField(max_length=50)
    evidence_image = models.ImageField(
        upload_to='material_evidence/%Y/%m/%d/', null=True, blank=True)
    evidence_video = models.FileField(
        upload_to='material_evidence_vids/%Y/%m/%d/', null=True, blank=True)
    last_updated = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "Material Stocks"
        unique_together = ('site', 'item_name')

    # 🚀 PRODUCTION ADDITION: For the Audit Email Logic
    def get_total_deductions_today(self):
        """Calculates total quantity taken today for the audit report."""
        from django.utils import timezone
        from django.db.models import Sum

        today = timezone.now().date()
        total = self.deductions.filter(
            timestamp__date=today
        ).aggregate(Sum('quantity_taken'))['quantity_taken__sum']

        return total or 0

    def get_weekly_total(self):
        """Calculates total quantity taken from Monday to Saturday."""
        from django.utils import timezone
        from django.db.models import Sum
        from datetime import timedelta

        today = timezone.now().date()
        start_of_week = today - timedelta(days=today.weekday())  # Monday

        total = self.deductions.filter(
            timestamp__date__range=[start_of_week, today]
        ).aggregate(Sum('quantity_taken'))['quantity_taken__sum']

        return total or 0

    def __str__(self):
        return f"{self.item_name} ({self.current_balance} {self.unit})"


class MaterialRestockLog(models.Model):
    """Permanent ledger of every material delivery to a site."""
    stock_item = models.ForeignKey(
        MaterialStock, on_delete=models.CASCADE, related_name='delivery_logs')
    site = models.ForeignKey(SiteLocation, on_delete=models.CASCADE)

    quantity_added = models.DecimalField(max_digits=12, decimal_places=2)
    timestamp = models.DateTimeField(auto_now_add=True)

    # 📸 The 'Proof' for this specific delivery event
    evidence_image = models.ImageField(
        upload_to='restock_proofs/%Y/%m/%d/', null=True, blank=True)
    evidence_video = models.FileField(
        upload_to='restock_proofs_vids/%Y/%m/%d/', null=True, blank=True)

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        return f"{self.stock_item.item_name} +{self.quantity_added} - {self.timestamp.strftime('%d %b')}"


class MaterialDeduction(models.Model):
    stock_item = models.ForeignKey(
        MaterialStock, on_delete=models.PROTECT, related_name='deductions')
    worker = models.ForeignKey(SkilledWorker, on_delete=models.PROTECT)
    quantity_taken = models.DecimalField(max_digits=12, decimal_places=2)
    purpose = models.CharField(max_length=255)
    timestamp = models.DateTimeField(auto_now_add=True)
    authorized_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True)

    def clean(self):
        # 🛡️ PRO SAFETY CHECK: Prevent taking more than available
        if self.quantity_taken > self.stock_item.current_balance:
            raise ValidationError(
                f"Insufficient stock! Only {self.stock_item.current_balance} {self.stock_item.unit} available.")

    def save(self, *args, **kwargs):
        self.full_clean()  # Force the safety check before saving
        if not self.pk:
            # Atomic update to prevent race conditions
            self.stock_item.current_balance -= self.quantity_taken
            self.stock_item.save()
        super().save(*args, **kwargs)


class CompanyProfile(models.Model):
    contractor = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name='site_company_profile')
    business_name = models.CharField(max_length=255)
    logo = models.ImageField(upload_to='company_logos/', null=True, blank=True)
    address = models.TextField(blank=True)

    def __str__(self):
        return self.business_name


class CategoryPay(models.Model):
    site = models.ForeignKey(SiteLocation, on_delete=models.CASCADE)

    # NEW: Removed choices so it matches the flexible SkilledWorker category
    category = models.CharField(
        max_length=100,
        help_text="e.g. Mason, Laborer, Iron Bender"
    )

    default_daily_rate = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0.00
    )

    class Meta:
        # This ensures you don't have two different prices for "Mason" on the same site
        unique_together = ('site', 'category')

    def __str__(self):
        return f"{self.site.name} - {self.category}: ₦{self.default_daily_rate}"
