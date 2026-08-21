from django.contrib import admin

from .models import Notification


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ['recipient', 'notification_type', 'title', 'company', 'is_read', 'created_at']
    list_filter = ['notification_type', 'is_read']
    search_fields = ['recipient__email', 'title', 'company__name']
    autocomplete_fields = ['recipient', 'company', 'content_calendar_item']
    readonly_fields = ['created_at', 'updated_at', 'read_at']
