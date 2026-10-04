from django.contrib import admin

from .models import BillingRecord, Plan, Subscription, UsageSnapshot


@admin.register(Plan)
class PlanAdmin(admin.ModelAdmin):
    list_display = ('name', 'price', 'currency', 'billing_cycle', 'creative_limit', 'video_limit', 'publishing_limit', 'is_active')
    prepopulated_fields = {'slug': ('name',)}


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = ('company', 'plan', 'status', 'start_date', 'end_date', 'renewal_date')
    list_filter = ('status', 'plan')
    search_fields = ('company__name',)


@admin.register(BillingRecord)
class BillingRecordAdmin(admin.ModelAdmin):
    list_display = ('invoice_number', 'company', 'invoice_date', 'total_amount', 'currency', 'payment_status')
    list_filter = ('payment_status', 'payment_method')
    search_fields = ('invoice_number', 'company__name', 'payment_reference')


admin.site.register(UsageSnapshot)
