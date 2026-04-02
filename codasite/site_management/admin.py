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
