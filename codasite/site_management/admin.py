from .models import CompanySubscription
from django.contrib import admin
from .models import (
    SiteLocation, Invitation, SkilledWorker,
    DailyWorkLog, StaffAttendance, MaterialStock, MaterialDeduction
)


@admin.register(SiteLocation)
class SiteLocationAdmin(admin.ModelAdmin):
    # ✅ Only use fields that exist in your models.py
    list_display = ('name', 'company', 'latitude', 'longitude', 'created_at')
    search_fields = ('name', 'company__business_name')
    list_filter = ('company', 'created_at')


@admin.register(SkilledWorker)
class SkilledWorkerAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'site', 'contractor')
    list_filter = ('category', 'site')
    search_fields = ('name',)
    # This will now work with your new slug field
    prepopulated_fields = {"slug": ("name",)}


@admin.register(MaterialStock)
class MaterialStockAdmin(admin.ModelAdmin):
    list_display = ('item_name', 'current_balance', 'unit', 'site')
    list_filter = ('site',)
    search_fields = ('item_name',)


@admin.register(MaterialDeduction)
class MaterialDeductionAdmin(admin.ModelAdmin):
    list_display = ('stock_item', 'worker', 'quantity_taken',
                    'timestamp', 'authorized_by')
    list_filter = ('stock_item__site', 'timestamp')
    search_fields = ('stock_item__item_name', 'purpose')


@admin.register(StaffAttendance)
class StaffAttendanceAdmin(admin.ModelAdmin):
    list_display = ('worker', 'user', 'site', 'mode', 'time_in', 'time_out')
    list_filter = ('mode', 'site')


# @admin.register(CompanyProfile)
# class CompanyProfileAdmin(admin.ModelAdmin):
#     list_display = ('contractor', 'business_name', 'address')


admin.site.register(Invitation)
admin.site.register(DailyWorkLog)


@admin.register(CompanySubscription)
class CompanySubscriptionAdmin(admin.ModelAdmin):
    # This dictates the columns you see in the admin table
    list_display = ('company', 'tier', 'status',
                    'next_billing_date', 'has_valid_access')

    # Adds a filter sidebar on the right
    list_filter = ('tier', 'status')

    # Adds a search bar to easily find a company
    search_fields = ('company__company_name',
                     'paystack_customer_code', 'paystack_subscription_code')

    # Protects fields that shouldn't be edited manually
    readonly_fields = ('created_at',)

    # Organizes the detail view into clean sections
    fieldsets = (
        ('Company Details', {
            'fields': ('company', 'tier', 'status')
        }),
        ('Billing Timeline', {
            'fields': ('created_at', 'trial_end_date', 'next_billing_date')
        }),
        ('Paystack API Hooks', {
            'fields': ('paystack_customer_code', 'paystack_subscription_code', 'paystack_token_auth'),
            # Hides this section by default to keep the UI clean
            'classes': ('collapse',)
        }),
    )

    # Turns your custom property into a visual Green Check / Red X in the admin
    @admin.display(boolean=True, description='Access Valid')
    def has_valid_access(self, obj):
        return obj.is_access_valid
