from django.conf import settings
from django.db import models

from apps.companies.models import Company
from common.models import TimeStampedModel


class SocialAccount(TimeStampedModel):
    """A connected Instagram/Facebook/LinkedIn account for a company (Epic 10:
    Social Media Account Management). Tokens are pasted in manually by an admin
    from the platform's developer portal (no OAuth app registration yet) and
    stored encrypted - see common/crypto.py.
    """

    class Platform(models.TextChoices):
        INSTAGRAM = 'instagram', 'Instagram'
        FACEBOOK = 'facebook', 'Facebook'
        LINKEDIN = 'linkedin', 'LinkedIn'

    class Status(models.TextChoices):
        CONNECTED = 'connected', 'Connected'
        EXPIRED = 'expired', 'Expired'
        DISCONNECTED = 'disconnected', 'Disconnected'

    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='social_accounts')
    platform = models.CharField(max_length=15, choices=Platform.choices)
    account_name = models.CharField(max_length=255, help_text='Admin-facing label, e.g. "Acme Restaurant IG".')
    account_id = models.CharField(
        max_length=255, blank=True, help_text='External page / organization / business account ID.',
    )
    access_token = models.TextField(blank=True, help_text='Encrypted at rest - never exposed via the API.')
    token_expires_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=15, choices=Status.choices, default=Status.CONNECTED)
    notes = models.TextField(blank=True)

    connected_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='+',
    )

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.get_platform_display()}: {self.account_name} ({self.company.name})'
