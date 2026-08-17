from django.contrib import admin

from .models import ContentCalendarItem


@admin.register(ContentCalendarItem)
class ContentCalendarItemAdmin(admin.ModelAdmin):
    list_display = ['topic', 'company', 'category', 'content_type', 'scheduled_date', 'status', 'source']
    list_filter = ['status', 'category', 'content_type', 'source']
    search_fields = ['topic', 'company__name']
    autocomplete_fields = ['company']
    readonly_fields = ['created_at', 'updated_at']
