from django.conf import settings
from django.db import models

from apps.companies.models import Company
from apps.content_calendar.models import ContentCalendarItem
from common.models import TimeStampedModel


class Notification(TimeStampedModel):
    """An in-app notification for one recipient (Epic 13: Notification Center - In-App).

    The first eight event types match the plan's notification list verbatim
    (Epic 12/13). company_created/client_added are an addition beyond the plan's
    list, requested so the admin team sees onboarding activity in the bell
    too, not just via email. The publishing/report/subscription types are raised
    by Epics 11, 16 and 17.
    """

    class NotificationType(models.TextChoices):
        CONTENT_GENERATED = 'content_generated', 'Content Generated'
        APPROVAL_REQUIRED = 'approval_required', 'Approval Required'
        CONTENT_APPROVED = 'content_approved', 'Content Approved'
        CONTENT_REJECTED = 'content_rejected', 'Content Rejected'
        CONTENT_REGENERATED = 'content_regenerated', 'Content Regenerated'
        CONTENT_PUBLISHED = 'content_published', 'Content Published'
        PUBLISHING_FAILED = 'publishing_failed', 'Publishing Failed'
        REMINDER = 'reminder', 'Reminder'
        COMPANY_CREATED = 'company_created', 'Company Created'
        CLIENT_ADDED = 'client_added', 'Client Added'
        ADMIN_ADDED = 'admin_added', 'Admin Added'
        SOCIAL_TOKEN_EXPIRED = 'social_token_expired', 'Social Token Expired'
        SUSPICIOUS_LOGIN = 'suspicious_login', 'Suspicious Login Activity'
        POST_SCHEDULED = 'post_scheduled', 'Post Scheduled'
        REPORT_READY = 'report_ready', 'Report Ready'
        SUBSCRIPTION_EXPIRING = 'subscription_expiring', 'Subscription Expiring'
        SUBSCRIPTION_EXPIRED = 'subscription_expired', 'Subscription Expired'
        USAGE_LIMIT_REACHED = 'usage_limit_reached', 'Usage Limit Reached'
        ANALYTICS_SYNC_FAILED = 'analytics_sync_failed', 'Analytics Sync Failed'

    recipient = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='notifications')
    company = models.ForeignKey(
        Company, null=True, blank=True, on_delete=models.CASCADE, related_name='notifications',
    )
    content_calendar_item = models.ForeignKey(
        ContentCalendarItem, null=True, blank=True, on_delete=models.SET_NULL, related_name='notifications',
    )

    notification_type = models.CharField(max_length=30, choices=NotificationType.choices)
    title = models.CharField(max_length=255)
    message = models.TextField(blank=True)
    url = models.CharField(max_length=500, blank=True, help_text='Frontend path to open when clicked.')

    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.get_notification_type_display()} -> {self.recipient.email}'
