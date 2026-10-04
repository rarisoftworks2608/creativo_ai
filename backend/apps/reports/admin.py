from django.contrib import admin

from .models import Report


@admin.register(Report)
class ReportAdmin(admin.ModelAdmin):
    list_display = ('title', 'company', 'report_type', 'period_start', 'period_end', 'status', 'is_automated', 'generated_at')
    list_filter = ('report_type', 'status', 'is_automated')
    search_fields = ('title', 'company__name')
