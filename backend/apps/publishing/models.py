from django.conf import settings
from django.db import models

from apps.companies.models import Company
from apps.content_calendar.models import ContentCalendarItem
from apps.social_accounts.models import SocialAccount
from common.models import TimeStampedModel


class PublishJob(TimeStampedModel):
    """One piece of approved content going out to one connected social account
    (Epic 11: Publishing & Scheduling). Multi-platform publishing = one job per account.

    Lifecycle: SCHEDULED --(due, picked by dispatch_due_publish_jobs)--> QUEUED -->
    PROCESSING --> PUBLISHED | (retryable error, attempts left) SCHEDULED again with
    backoff | FAILED. CANCELLED is terminal until an admin retries/reschedules it.

    `media` is a snapshot of exactly what gets posted (resolved from the approved
    variation / rendered video when the job is created) so a later regeneration can
    never change what an already-scheduled post contains.
    """

    class Status(models.TextChoices):
        SCHEDULED = 'scheduled', 'Scheduled'
        QUEUED = 'queued', 'Queued'
        PROCESSING = 'processing', 'Processing'
        PUBLISHED = 'published', 'Published'
        FAILED = 'failed', 'Failed'
        CANCELLED = 'cancelled', 'Cancelled'

    class PostType(models.TextChoices):
        IMAGE = 'image', 'Image post'
        CAROUSEL = 'carousel', 'Carousel'
        VIDEO = 'video', 'Video'
        REEL = 'reel', 'Reel'
        STORY = 'story', 'Story'
        TEXT = 'text', 'Text only'

    ACTIVE_STATUSES = (Status.SCHEDULED, Status.QUEUED, Status.PROCESSING)

    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='publish_jobs')
    content_calendar_item = models.ForeignKey(
        ContentCalendarItem, null=True, blank=True, on_delete=models.SET_NULL, related_name='publish_jobs',
    )
    social_account = models.ForeignKey(
        SocialAccount, null=True, blank=True, on_delete=models.SET_NULL, related_name='publish_jobs',
    )
    platform = models.CharField(max_length=15, choices=SocialAccount.Platform.choices)
    post_type = models.CharField(max_length=10, choices=PostType.choices, default=PostType.IMAGE)

    caption = models.TextField(blank=True)
    media = models.JSONField(
        default=list, blank=True,
        help_text='Snapshot of media to post: [{"kind": "image"|"video", "source": ..., "id": ..., "name": ...}].',
    )

    scheduled_at = models.DateTimeField(db_index=True)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.SCHEDULED)
    attempts = models.PositiveSmallIntegerField(default=0)
    max_attempts = models.PositiveSmallIntegerField(default=3)
    last_error = models.TextField(blank=True)
    error_log = models.JSONField(default=list, blank=True, help_text='[{"at": iso, "attempt": n, "message": ...}]')
    celery_task_id = models.CharField(max_length=255, blank=True)

    external_post_id = models.CharField(max_length=255, blank=True)
    external_url = models.URLField(max_length=500, blank=True)
    published_at = models.DateTimeField(null=True, blank=True)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='+',
    )

    class Meta:
        ordering = ['-scheduled_at', '-id']
        indexes = [
            models.Index(fields=['status', 'scheduled_at']),
            models.Index(fields=['company', 'status']),
            models.Index(fields=['company', '-published_at']),
        ]

    def __str__(self):
        return f'{self.get_platform_display()} {self.get_post_type_display()} for {self.company.name} ({self.status})'

    @property
    def is_active(self):
        return self.status in self.ACTIVE_STATUSES
