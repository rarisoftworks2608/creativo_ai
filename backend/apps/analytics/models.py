from django.conf import settings
from django.db import models

from apps.companies.models import Company
from apps.publishing.models import PublishJob
from apps.social_accounts.models import SocialAccount
from common.models import TimeStampedModel

METRIC_FIELDS = ('reach', 'impressions', 'views', 'likes', 'comments', 'shares', 'saves', 'clicks')


class PostMetrics(TimeStampedModel):
    """Latest performance numbers for one published post (Epic 15: Instagram / Facebook /
    LinkedIn metrics). One row per PublishJob; every sync also appends a
    PostMetricSnapshot so trends over time are kept (Historical data).

    engagements = likes + comments + shares + saves + clicks
    engagement_rate = engagements / reach (falls back to impressions, then views) x 100
    """

    publish_job = models.OneToOneField(PublishJob, on_delete=models.CASCADE, related_name='metrics')
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='post_metrics')
    platform = models.CharField(max_length=15)
    published_at = models.DateTimeField(null=True, blank=True)
    content_type = models.CharField(max_length=100, blank=True, help_text='Copied from the calendar item format.')
    post_type = models.CharField(max_length=10, blank=True)
    campaign = models.CharField(max_length=255, blank=True)

    reach = models.PositiveBigIntegerField(default=0)
    impressions = models.PositiveBigIntegerField(default=0)
    views = models.PositiveBigIntegerField(default=0)
    likes = models.PositiveBigIntegerField(default=0)
    comments = models.PositiveBigIntegerField(default=0)
    shares = models.PositiveBigIntegerField(default=0)
    saves = models.PositiveBigIntegerField(default=0)
    clicks = models.PositiveBigIntegerField(default=0)
    engagements = models.PositiveBigIntegerField(default=0)
    engagement_rate = models.FloatField(default=0)

    last_synced_at = models.DateTimeField(null=True, blank=True)
    sync_error = models.TextField(blank=True)
    raw = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ['-published_at']
        indexes = [
            models.Index(fields=['company', 'published_at']),
            models.Index(fields=['company', 'platform']),
        ]

    def __str__(self):
        return f'Metrics for job {self.publish_job_id}'

    def recompute(self):
        self.engagements = self.likes + self.comments + self.shares + self.saves + self.clicks
        base = self.reach or self.impressions or self.views
        self.engagement_rate = round(self.engagements / base * 100, 2) if base else 0.0


class PostMetricSnapshot(models.Model):
    post_metrics = models.ForeignKey(PostMetrics, on_delete=models.CASCADE, related_name='snapshots')
    captured_at = models.DateTimeField(auto_now_add=True)
    reach = models.PositiveBigIntegerField(default=0)
    impressions = models.PositiveBigIntegerField(default=0)
    views = models.PositiveBigIntegerField(default=0)
    likes = models.PositiveBigIntegerField(default=0)
    comments = models.PositiveBigIntegerField(default=0)
    shares = models.PositiveBigIntegerField(default=0)
    saves = models.PositiveBigIntegerField(default=0)
    clicks = models.PositiveBigIntegerField(default=0)
    engagements = models.PositiveBigIntegerField(default=0)

    class Meta:
        ordering = ['-captured_at']


class AccountMetricSnapshot(models.Model):
    """Daily follower count (and whatever account-level numbers the platform returns)
    per connected account - the basis of follower growth (Epic 15: Followers, Growth)."""

    social_account = models.ForeignKey(SocialAccount, on_delete=models.CASCADE, related_name='metric_snapshots')
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='account_metric_snapshots')
    platform = models.CharField(max_length=15)
    date = models.DateField()
    followers = models.PositiveBigIntegerField(null=True, blank=True)
    following = models.PositiveBigIntegerField(null=True, blank=True)
    media_count = models.PositiveBigIntegerField(null=True, blank=True)
    raw = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['date']
        unique_together = [['social_account', 'date']]
        indexes = [models.Index(fields=['company', 'date'])]


class AnalyticsSyncLog(models.Model):
    """One analytics synchronization run (Epic 15: Synchronization - Fetch analytics,
    Scheduled sync, API failure handling, Retry)."""

    class Status(models.TextChoices):
        RUNNING = 'running', 'Running'
        SUCCEEDED = 'succeeded', 'Succeeded'
        PARTIAL = 'partial', 'Partially succeeded'
        FAILED = 'failed', 'Failed'

    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='analytics_sync_logs')
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.RUNNING)
    started_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    posts_synced = models.PositiveIntegerField(default=0)
    posts_failed = models.PositiveIntegerField(default=0)
    accounts_synced = models.PositiveIntegerField(default=0)
    errors = models.JSONField(default=list, blank=True)
    triggered_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='+',
    )

    class Meta:
        ordering = ['-started_at']

    def __str__(self):
        return f'Analytics sync {self.company_id} {self.started_at:%Y-%m-%d %H:%M} ({self.status})'
