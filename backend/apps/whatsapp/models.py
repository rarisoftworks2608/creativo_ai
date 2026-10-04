from django.conf import settings
from django.db import models

from apps.companies.models import Company
from common.models import TimeStampedModel


class Event(models.TextChoices):
    """Every workflow event that can send a WhatsApp message (Epic 12: Notifications)."""
    APPROVAL_REQUIRED = 'approval_required', 'Content generated - approval required'
    CONTENT_REGENERATED = 'content_regenerated', 'Content regenerated'
    CONTENT_APPROVED = 'content_approved', 'Content approved'
    CONTENT_REJECTED = 'content_rejected', 'Content rejected'
    CONTENT_PUBLISHED = 'content_published', 'Content published'
    PUBLISHING_FAILED = 'publishing_failed', 'Publishing failed'
    APPROVAL_REMINDER = 'approval_reminder', 'Approval reminder'
    MONTHLY_REPORT = 'monthly_report', 'Monthly report ready'


# Who receives each event: the whole group (client + internal numbers) or only the
# internal team - a client shouldn't be messaged about an internal publishing failure.
EVENT_AUDIENCE = {
    Event.APPROVAL_REQUIRED: 'all',
    Event.CONTENT_REGENERATED: 'all',
    Event.CONTENT_APPROVED: 'all',
    Event.CONTENT_REJECTED: 'internal',
    Event.CONTENT_PUBLISHED: 'all',
    Event.PUBLISHING_FAILED: 'internal',
    Event.APPROVAL_REMINDER: 'clients',
    Event.MONTHLY_REPORT: 'all',
}


def _all_events():
    return list(Event.values)


class WhatsAppConfig(TimeStampedModel):
    """A company's WhatsApp set-up (Epic 12: Configuration + Group).

    The agency's WhatsApp Business number and API credentials are platform-wide (.env);
    per company we keep who gets messaged - the client's numbers and the internal team's
    numbers form the company's notification group - and which events are switched on.
    """

    class GroupStatus(models.TextChoices):
        NOT_CREATED = 'not_created', 'Not created'
        ACTIVE = 'active', 'Active'
        INACTIVE = 'inactive', 'Inactive'

    company = models.OneToOneField(Company, on_delete=models.CASCADE, related_name='whatsapp_config')
    is_enabled = models.BooleanField(default=False)
    business_number = models.CharField(
        max_length=20, blank=True, help_text='The WhatsApp Business number messages come from (display only).',
    )
    client_numbers = models.JSONField(default=list, blank=True, help_text='[{"name": "...", "phone": "+91..."}]')
    internal_numbers = models.JSONField(default=list, blank=True, help_text='[{"name": "...", "phone": "+91..."}]')
    include_client_users = models.BooleanField(
        default=True,
        help_text="Also message the company's client logins who turned on WhatsApp notifications in their settings.",
    )

    group_name = models.CharField(max_length=120, blank=True)
    group_description = models.TextField(blank=True)
    group_status = models.CharField(max_length=15, choices=GroupStatus.choices, default=GroupStatus.NOT_CREATED)
    group_invite_link = models.URLField(
        blank=True, help_text='Optional link to a WhatsApp group created in the app for human conversation.',
    )
    group_created_at = models.DateTimeField(null=True, blank=True)

    enabled_events = models.JSONField(default=_all_events, blank=True)
    language_code = models.CharField(max_length=10, default='en', help_text='Template language, e.g. en, en_US, hi.')

    class Meta:
        verbose_name = 'WhatsApp configuration'

    def __str__(self):
        return f'WhatsApp config for {self.company.name}'


class WhatsAppTemplate(TimeStampedModel):
    """Maps a workflow event to a pre-approved WhatsApp message template (Epic 12:
    Templates). Business-initiated WhatsApp messages must use a template approved by
    Meta, so `name` + `language_code` must match a template in WhatsApp Manager exactly;
    `variables` lists which context values fill {{1}}, {{2}}, ... in order."""

    class Category(models.TextChoices):
        UTILITY = 'utility', 'Utility'
        MARKETING = 'marketing', 'Marketing'

    class MetaStatus(models.TextChoices):
        UNKNOWN = 'unknown', 'Not synced'
        APPROVED = 'approved', 'Approved'
        PENDING = 'pending', 'Pending review'
        REJECTED = 'rejected', 'Rejected'
        PAUSED = 'paused', 'Paused'
        MISSING = 'missing', 'Not found in WhatsApp Manager'

    event = models.CharField(max_length=30, choices=Event.choices)
    name = models.CharField(max_length=512, help_text='Template name exactly as created in WhatsApp Manager.')
    language_code = models.CharField(max_length=10, default='en')
    category = models.CharField(max_length=15, choices=Category.choices, default=Category.UTILITY)
    body = models.TextField(help_text='Body text as submitted to Meta, with {{1}}, {{2}} ... placeholders.')
    variables = models.JSONField(default=list, help_text='Ordered context keys for {{1}}, {{2}}, ...')
    is_active = models.BooleanField(default=True)
    meta_status = models.CharField(max_length=10, choices=MetaStatus.choices, default=MetaStatus.UNKNOWN)
    last_synced_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['event', 'language_code']
        unique_together = [['event', 'language_code']]

    def __str__(self):
        return f'{self.name} ({self.language_code})'

    def render(self, values):
        text = self.body
        for index, value in enumerate(values, start=1):
            text = text.replace(f'{{{{{index}}}}}', str(value))
        return text


class WhatsAppMessage(TimeStampedModel):
    """Delivery log of every WhatsApp message (Epic 12: status tracking)."""

    class Status(models.TextChoices):
        QUEUED = 'queued', 'Queued'
        SENT = 'sent', 'Sent'
        DELIVERED = 'delivered', 'Delivered'
        READ = 'read', 'Read'
        FAILED = 'failed', 'Failed'
        SKIPPED = 'skipped', 'Skipped'

    company = models.ForeignKey(Company, null=True, blank=True, on_delete=models.CASCADE, related_name='whatsapp_messages')
    event = models.CharField(max_length=30)
    to_number = models.CharField(max_length=20)
    recipient_name = models.CharField(max_length=150, blank=True)
    recipient_type = models.CharField(max_length=10, blank=True, help_text='client / internal / user / test')
    template_name = models.CharField(max_length=512, blank=True)
    language_code = models.CharField(max_length=10, blank=True)
    variables = models.JSONField(default=list, blank=True)
    body = models.TextField(blank=True, help_text='Rendered preview of what was sent.')
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.QUEUED)
    provider = models.CharField(max_length=10, blank=True)
    provider_message_id = models.CharField(max_length=255, blank=True, db_index=True)
    error = models.TextField(blank=True)
    attempts = models.PositiveSmallIntegerField(default=0)
    sent_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    read_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='+',
    )

    class Meta:
        ordering = ['-created_at']
        indexes = [models.Index(fields=['company', '-created_at'])]

    def __str__(self):
        return f'{self.event} -> {self.to_number} ({self.status})'
