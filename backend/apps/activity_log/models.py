from django.db import models

from common.models import TimeStampedModel


class ActivityLog(TimeStampedModel):
    """Unified audit trail across the platform (Epic 18).

    Written only through `services.log_activity()` - the single choke point,
    mirroring the `notifications` app's `notify()` pattern - so every action
    type is recorded the same way instead of each caller hand-rolling entries.
    """

    class Module(models.TextChoices):
        AUTH = 'auth', 'Authentication'
        COMPANY = 'company', 'Company'
        CLIENT = 'client', 'Client'
        CALENDAR = 'calendar', 'Content Calendar'
        CREATIVE = 'creative', 'Creative Generation'
        VIDEO = 'video', 'Video Generation'
        APPROVAL = 'approval', 'Content Approval'
        SOCIAL = 'social', 'Social Accounts'
        SETTINGS = 'settings', 'Settings'

    user = models.ForeignKey(
        'authentication.User',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='activity_logs',
        help_text='Null for system-triggered actions (e.g. scheduled auto-generation).',
    )
    company = models.ForeignKey(
        'companies.Company',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='activity_logs',
        help_text='Null for actions not tied to a specific company (e.g. admin login).',
    )
    module = models.CharField(max_length=20, choices=Module.choices)
    action = models.CharField(max_length=100, help_text='Short verb phrase, e.g. "Company updated".')
    description = models.CharField(max_length=500, blank=True)
    old_value = models.JSONField(null=True, blank=True)
    new_value = models.JSONField(null=True, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['module', '-created_at']),
            models.Index(fields=['company', '-created_at']),
        ]

    def __str__(self):
        who = self.user.email if self.user else 'system'
        return f'{who} - {self.action} - {self.created_at:%Y-%m-%d %H:%M}'
