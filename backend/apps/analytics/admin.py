from django.contrib import admin

from .models import AccountMetricSnapshot, AnalyticsSyncLog, PostMetrics


@admin.register(PostMetrics)
class PostMetricsAdmin(admin.ModelAdmin):
    list_display = ('publish_job', 'company', 'platform', 'reach', 'engagements', 'engagement_rate', 'last_synced_at')
    list_filter = ('platform',)


@admin.register(AccountMetricSnapshot)
class AccountMetricSnapshotAdmin(admin.ModelAdmin):
    list_display = ('social_account', 'date', 'followers')


@admin.register(AnalyticsSyncLog)
class AnalyticsSyncLogAdmin(admin.ModelAdmin):
    list_display = ('company', 'status', 'started_at', 'posts_synced', 'posts_failed', 'accounts_synced')
    list_filter = ('status',)
