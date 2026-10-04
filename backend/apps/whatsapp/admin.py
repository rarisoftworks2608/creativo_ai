from django.contrib import admin

from .models import WhatsAppConfig, WhatsAppMessage, WhatsAppTemplate


@admin.register(WhatsAppConfig)
class WhatsAppConfigAdmin(admin.ModelAdmin):
    list_display = ('company', 'is_enabled', 'group_status', 'language_code', 'updated_at')


@admin.register(WhatsAppTemplate)
class WhatsAppTemplateAdmin(admin.ModelAdmin):
    list_display = ('event', 'name', 'language_code', 'is_active', 'meta_status')
    list_filter = ('event', 'is_active', 'meta_status')


@admin.register(WhatsAppMessage)
class WhatsAppMessageAdmin(admin.ModelAdmin):
    list_display = ('created_at', 'company', 'event', 'to_number', 'status', 'provider')
    list_filter = ('status', 'event', 'provider')
    search_fields = ('to_number', 'recipient_name', 'provider_message_id')
