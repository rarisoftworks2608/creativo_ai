from django.contrib import admin

from .models import ActivityLog


@admin.register(ActivityLog)
class ActivityLogAdmin(admin.ModelAdmin):
    list_display = ['created_at', 'user', 'module', 'action', 'company', 'ip_address']
    list_filter = ['module']
    search_fields = ['action', 'description', 'user__email', 'company__name']
    autocomplete_fields = ['user', 'company']
    readonly_fields = ['created_at', 'updated_at']
    date_hierarchy = 'created_at'
