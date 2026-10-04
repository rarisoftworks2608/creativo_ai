import uuid

from django.conf import settings
from django.db import models

from apps.companies.models import Company
from common.models import TimeStampedModel


class SocialAccount(TimeStampedModel):
    """A connected Instagram/Facebook/LinkedIn account for a company (Epic 10:
    Social Media Account Management).

    Connected either through the OAuth flow ("Connect with Facebook" / "Connect with
    LinkedIn" - pages, Instagram professional accounts and LinkedIn organizations are
    discovered and picked from a list) or, as a fallback, by an admin pasting a token
    from the platform's developer portal. Tokens are always stored encrypted - see
    common/crypto.py.

    `account_id` is the ID publishing/analytics calls are made against: the Facebook
    Page ID, the Instagram professional account (IG user) ID, or the LinkedIn
    organization/member ID. `metadata` carries what else each platform needs - e.g. an
    Instagram account's parent `page_id`, or a LinkedIn author `urn`.
    """

    class Platform(models.TextChoices):
        INSTAGRAM = 'instagram', 'Instagram'
        FACEBOOK = 'facebook', 'Facebook'
        LINKEDIN = 'linkedin', 'LinkedIn'

    class Status(models.TextChoices):
        CONNECTED = 'connected', 'Connected'
        EXPIRED = 'expired', 'Expired'
        DISCONNECTED = 'disconnected', 'Disconnected'

    class ConnectionMethod(models.TextChoices):
        OAUTH = 'oauth', 'OAuth'
        MANUAL = 'manual', 'Manual token'

    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='social_accounts')
    platform = models.CharField(max_length=15, choices=Platform.choices)
    account_name = models.CharField(max_length=255, help_text='Admin-facing label, e.g. "Acme Restaurant IG".')
    account_id = models.CharField(
        max_length=255, blank=True, help_text='External page / organization / business account ID.',
    )
    access_token = models.TextField(blank=True, help_text='Encrypted at rest - never exposed via the API.')
    token_expires_at = models.DateTimeField(null=True, blank=True)
    refresh_token = models.TextField(blank=True, help_text='Encrypted at rest (LinkedIn programmatic refresh).')
    refresh_token_expires_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=15, choices=Status.choices, default=Status.CONNECTED)
    connection_method = models.CharField(
        max_length=10, choices=ConnectionMethod.choices, default=ConnectionMethod.MANUAL,
    )
    scopes = models.JSONField(default=list, blank=True, help_text='Permissions granted to the token.')
    metadata = models.JSONField(
        default=dict, blank=True,
        help_text='Platform extras: page_id, username, picture_url, followers_count, urn, account_type.',
    )
    last_error = models.TextField(blank=True, help_text='Most recent connection/publishing error, if any.')
    last_checked_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)

    connected_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='+',
    )

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.get_platform_display()}: {self.account_name} ({self.company.name})'

    @property
    def is_usable(self):
        return self.status == self.Status.CONNECTED and bool(self.access_token)

    @property
    def linkedin_urn(self):
        """Author URN for LinkedIn posts - an organization unless the account is a member."""
        urn = (self.metadata or {}).get('urn')
        if urn:
            return urn
        if (self.metadata or {}).get('account_type') == 'person':
            return f'urn:li:person:{self.account_id}'
        return f'urn:li:organization:{self.account_id}'


class SocialOAuthSession(models.Model):
    """The accounts discovered by one completed OAuth login, waiting for the admin to
    pick which ones to connect (Epic 10: Facebook Page selection / LinkedIn Organization
    selection). Holds access tokens, so the payload is encrypted and the session is
    single-use and short-lived."""

    class Provider(models.TextChoices):
        META = 'meta', 'Meta (Facebook & Instagram)'
        LINKEDIN = 'linkedin', 'LinkedIn'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='social_oauth_sessions')
    provider = models.CharField(max_length=10, choices=Provider.choices)
    payload = models.TextField(help_text='Encrypted JSON list of discovered candidate accounts (with tokens).')
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='+',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    consumed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.get_provider_display()} OAuth session for {self.company_id}'
