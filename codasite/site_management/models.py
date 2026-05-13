from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import models
from django.contrib.auth import get_user_model
import uuid
from django.utils.text import slugify
from cloudinary.models import CloudinaryField
from account.models import Company
from django.db import transaction
from django.db.models import F
from datetime import timedelta
# from geopy.geocoders import Nominatim
from django.utils import timezone
import datetime
User = get_user_model()

# 1. Site Infrastructure


class SiteLocation(models.Model):
    # ✅ FIX: Point to 'Company' (the actual model class)
    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name='sites',
        null=True
    )

    name = models.CharField(max_length=255, db_index=True)
    is_office = models.BooleanField(default=False)
    address = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    # 📏 SETTINGS
    minimum_required = models.IntegerField(default=10, null=True, blank=True)

    # 🛰️ GPS ENGINE
    latitude = models.DecimalField(
        max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(
        max_digits=9, decimal_places=6, null=True, blank=True)

    radius_meters = models.IntegerField(
        default=100, help_text="Allowed distance from site center")

    def is_editable(self):
        # Returns True if the site was created less than 7 days ago
        return timezone.now() < self.created_at + timedelta(days=7)

    def __str__(self):
        return self.name


# class SiteLocation(models.Model):
#     # name = models.CharField(max_length=255,db_index=True)  # e.g., "Lekki Phase 1"
#     # contractor = models.ForeignKey(
#     #     User, on_delete=models.CASCADE, related_name='sites')

#     company = models.ForeignKey(
#         'CompanyProfile', on_delete=models.CASCADE, related_name='sites', null=True)
#     name = models.CharField(max_length=255,db_index=True)
#     is_office = models.BooleanField(default=False)
#     address = models.TextField(blank=True)
#     created_at = models.DateTimeField(auto_now_add=True)

#     # 📏 SETTINGS
#     minimum_required = models.IntegerField(default=10, null=True, blank=True)

#     # 🛰️ GPS ENGINE (ADD THESE)
#     # Using DecimalField for high precision in Lekki/Ajah streets
#     latitude = models.DecimalField(
#         max_digits=9, decimal_places=6, null=True, blank=True)
#     longitude = models.DecimalField(
#         max_digits=9, decimal_places=6, null=True, blank=True)

#     # How close the Storekeeper must be to the center (in Meters)
#     radius_meters = models.IntegerField(
#         default=100, help_text="Allowed distance from site center")

#     def __str__(self):
#         return self.name
# 2. Access Control


# class Invitation(models.Model):
#     ROLE_CHOICES = [
#         ('PROJECT_MANAGER', 'Project Manager'),
#         ('STOREKEEPER', 'Storekeeper'),
#     ]
#     email = models.EmailField()
#     site = models.ForeignKey(SiteLocation, on_delete=models.CASCADE)
#     token = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
#     invited_by = models.ForeignKey(User, on_delete=models.CASCADE)
#     role_assigned = models.CharField(
#         max_length=20, db_index=True, choices=ROLE_CHOICES)
#     is_used = models.BooleanField(default=False)
#     created_at = models.DateTimeField(auto_now_add=True)

#     def __str__(self):
#         return f"Invite for {self.email} to {self.site.name}"


class Invitation(models.Model):
    # 🛑 1. You can keep these as 'suggestions' for your UI,
    # but we remove them from the field itself to allow custom typing.
    ROLE_CHOICES = [
        ('PROJECT_MANAGER', 'Project Manager'),
        ('STOREKEEPER', 'Storekeeper'),
    ]

    email = models.EmailField()
    site = models.ForeignKey(SiteLocation, on_delete=models.CASCADE)
    token = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    invited_by = models.ForeignKey(User, on_delete=models.CASCADE)

    # ✍️ 2. REMOVE 'choices=ROLE_CHOICES' to unlock the field
    # Also increased max_length to 50 just in case they type a long title.
    role_assigned = models.CharField(
        max_length=50,
        db_index=True,
        help_text="The custom title for this staff member"
    )

    is_used = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Invite for {self.email} as {self.role_assigned} at {self.site.name}"
# 3. Staff & Skilled Workers


class SkilledWorker(models.Model):

    # IDENTITY
    company = models.ForeignKey(
        'account.Company', on_delete=models.CASCADE, related_name='workers', null=True, blank=True)
    user = models.OneToOneField(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='worker_profile'
    )
    name = models.CharField(max_length=255, db_index=True)
    slug = models.SlugField(unique=True, blank=True, null=True, max_length=100)
    id_number = models.CharField(
        max_length=50, unique=True, null=True, db_index=True, blank=True)
    category = models.CharField(
        max_length=100, db_index=True, help_text="e.g. Mason, Plumber, Supervisor")
    phone = models.CharField(max_length=20, db_index=True, blank=True)
    emergency_contact = models.CharField(
        max_length=255, db_index=True, null=True, blank=True)
    video_id_proof = CloudinaryField(
        'worker_videos/',
        resource_type='video',  # 👈 Critical for Cloudinary to treat it as video
        null=True,
        blank=True
    )

    # 💰 PAYROLL & STATUS
    daily_rate = models.DecimalField(
        max_digits=10, decimal_places=2, default=0.00)
    pay_rate = models.DecimalField(
        max_digits=10, decimal_places=2, default=0.00)

    pay_frequency = models.CharField(
        max_length=50,
        db_index=True,
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
    profile_picture = CloudinaryField(
        folder='worker_photos/', null=True, blank=True)
    bank_name = models.CharField(
        max_length=100, db_index=True, null=True, blank=True, help_text="e.g. GTBank, Zenith, OPay")
    account_number = models.CharField(
        max_length=10, db_index=True, null=True, blank=True)
    account_name = models.CharField(
        max_length=255, db_index=True, null=True, blank=True)

    gate_pass = models.CharField(max_length=10, blank=True, null=True)
    is_trashed = models.BooleanField(default=False)
    rating = models.IntegerField(default=5)
    is_elite = models.BooleanField(default=False)

    class Meta:
        # '-' means descending order (Newest/Latest ID first)
        ordering = ['-id']

    def save(self, *args, **kwargs):
        # ID NUMBER
        if not self.id_number:
            short_uuid = str(uuid.uuid4())[:4].upper()

            year = timezone.now().year
            self.id_number = f"CS-{year}-{short_uuid}"

        if not self.slug:

            # 1. Create the base (e.g., "victor-paul")
            base = slugify(self.name)

            # 2. Generate a unique short code
            short_id = str(uuid.uuid4())[:4]

            # 3. Handle the phone suffix safely
            if self.phone:
                # Clean the phone number (remove spaces/dashes) before taking last 4
                clean_phone = "".join(filter(str.isdigit, self.phone))
                phone_suffix = clean_phone[-4:] if len(
                    clean_phone) >= 4 else clean_phone
                # Combine and run through slugify ONE LAST TIME to be 100% safe
                self.slug = slugify(f"{base}-{phone_suffix}-{short_id}")
            else:
                self.slug = slugify(f"{base}-{short_id}")

        super().save(*args, **kwargs)

    def __str__(self):
        # Remove get_category_display() because category is a CharField, not a ChoiceF,db_index=Trueield
        return f"{self.name} ({self.category})"

    # 🚀 ADD THIS HELPER PROPERTY:
    @property
    def is_crew_member(self):
        """Returns True if this worker is part of a Sub-Contractor's crew"""
        return self.lead_worker is not None


# 5. Sub-Contractor Management (FIXED PRICE JOBS)

class SiteContract(models.Model):
    """Tracks Fixed-Price jobs given to Sub-Contractors (The Ogas)"""
    site = models.ForeignKey(
        SiteLocation, on_delete=models.CASCADE, related_name='contracts')

    # Only allow workers who are flagged as sub-contractors to be selected here
    sub_contractor = models.ForeignKey(
        SkilledWorker,
        on_delete=models.CASCADE,
        limit_choices_to={'is_sub_contractor': True},
        related_name='awarded_contracts'
    )

    job_title = models.CharField(
        max_length=255, help_text="e.g., Block Work for Phase 2, Full Plumbing")

    # 💰 The Fixed Price Money
    total_agreed_amount = models.DecimalField(
        max_digits=12, decimal_places=2, default=0.00)
    amount_paid_so_far = models.DecimalField(
        max_digits=12, decimal_places=2, default=0.00)

    start_date = models.DateField(auto_now_add=True)
    target_completion_date = models.DateField(null=True, blank=True)
    is_completed = models.BooleanField(default=False)

    class Meta:
        ordering = ['-start_date']

    def __str__(self):
        return f"{self.job_title} - {self.sub_contractor.name}"

    @property
    def balance_owed(self):
        """Calculates how much is left to pay the Oga"""
        return self.total_agreed_amount - self.amount_paid_so_far
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
    mode = models.CharField(max_length=10, db_index=True,
                            choices=WORK_MODES, default='SITE')
    # 📸 The Anti-Cheat Security Snapshot
    clock_in_photo = CloudinaryField(
        folder='attendance_photos/clock_in/', null=True, blank=True)

    latitude = models.DecimalField(
        max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(
        max_digits=9, decimal_places=6, null=True, blank=True)

    time_in = models.DateTimeField(auto_now_add=True)  # Captured on Clock In
    time_out = models.DateTimeField(
        null=True, blank=True)  # Captured on Clock Out
    is_paid = models.BooleanField(default=False)
    payment_date = models.DateTimeField(null=True, blank=True)
    payment_reference = models.CharField(
        max_length=100, db_index=True, null=True, blank=True)

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

    @property
    def duration(self):
        if self.time_in and self.time_out:
            diff = self.time_out - self.time_in
            total_seconds = int(diff.total_seconds())
            hours = total_seconds // 3600
            minutes = (total_seconds % 3600) // 60
            return f"{hours:02d}h {minutes:02d}m"
        return None

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

    unit = models.CharField(max_length=50, db_index=True)
    evidence_image = CloudinaryField(
        'image', folder='material_evidence', null=True, blank=True)

    is_returnable = models.BooleanField(
        default=False, help_text="True if Asset/Tool. False if Consumable.")

    evidence_video = CloudinaryField(
        'video', resource_type='video', folder='material_evidence_vids', null=True, blank=True)
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

    evidence_image = CloudinaryField(
        'image', folder='restock_proofs/', null=True, blank=True)
    evidence_video = CloudinaryField(
        'video', resource_type='video', folder='restock_proofs_vids/', null=True, blank=True)

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        return f"{self.stock_item.item_name} +{self.quantity_added} - {self.timestamp.strftime('%d %b')}"


class MaterialDeduction(models.Model):
    stock_item = models.ForeignKey(
        MaterialStock, on_delete=models.PROTECT, related_name='deductions')
    worker = models.ForeignKey(SkilledWorker, on_delete=models.PROTECT)
    quantity_taken = models.DecimalField(max_digits=12, decimal_places=2)
    purpose = models.CharField(max_length=255, db_index=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    authorized_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True)

    # 🚀 ADD THESE TWO NEW LINES:
# 🚀 ADD THESE TWO NEW LINES:
    is_returned = models.BooleanField(default=False)
    returned_at = models.DateTimeField(null=True, blank=True)

    def clean(self):
        from django.core.exceptions import ValidationError

        # 🛰️ 1. Get the REAL-TIME truth from the database
        # We look at the actual row to avoid any "Ghost Data" bugs
        db_entry = self.stock_item.__class__.objects.get(id=self.stock_item.id)
        actual_balance = db_entry.current_balance

        # 🛡️ 2. The Modern Security Gate
        if self.quantity_taken > actual_balance:
            raise ValidationError(
                f"🚨 LOGISTICS ALERT: INSUFFICIENT {self.stock_item.item_name.upper()} | "
                f"REQUESTED: {self.quantity_taken} {self.stock_item.unit} | "
                f"AVAILABLE: {actual_balance} {self.stock_item.unit}. "
                f"ACTION DENIED."
            )

    def save(self, *args, **kwargs):
        # 1. Run the safety check (requested qty vs available)
        self.full_clean()

        with transaction.atomic():
            # 2. Subtract directly in the Database (Atomic Update)
            # This prevents "Ghost Inventory" if two people click at once
            self.stock_item.current_balance = F(
                'current_balance') - self.quantity_taken
            self.stock_item.save()

            # 3. Save the actual log
            super().save(*args, **kwargs)


class CategoryPay(models.Model):
    site = models.ForeignKey(SiteLocation, on_delete=models.CASCADE)

    # NEW: Removed choices so it matches the flexible SkilledWorker category
    category = models.CharField(
        max_length=100,
        db_index=True,
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
