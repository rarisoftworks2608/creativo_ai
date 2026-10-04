"""Automation for connected social accounts (Epic 10: Security - Token expiry)."""

from celery import shared_task
from django.utils import timezone

from apps.notifications.models import Notification
from apps.notifications.services import notify_admins

from .models import SocialAccount


@shared_task
def check_social_account_expiry():
    """Flips any CONNECTED account whose token_expires_at has passed to EXPIRED and
    notifies admins - so a stale token is caught before it silently breaks publishing,
    rather than an admin discovering it only when something fails downstream. Runs
    daily (see CELERY_BEAT_SCHEDULE); a token without an expiry date is never touched.
    """
    expired_accounts = SocialAccount.objects.filter(
        status=SocialAccount.Status.CONNECTED,
        token_expires_at__isnull=False,
        token_expires_at__lte=timezone.now(),
    ).select_related('company')

    for account in expired_accounts:
        account.status = SocialAccount.Status.EXPIRED
        account.save(update_fields=['status', 'updated_at'])

        notify_admins(
            actor=None,
            notification_type=Notification.NotificationType.SOCIAL_TOKEN_EXPIRED,
            title=f'{account.get_platform_display()} token expired for {account.company.name}',
            message=f'"{account.account_name}" needs a fresh access token to keep working.',
            url=f'/companies/{account.company_id}/social-accounts',
            company=account.company,
        )


def refresh_account_token(account):
    """Renews a LinkedIn account's access token with its refresh token, in place.
    Raises OAuthError on failure (and records it on the account)."""
    from common.crypto import decrypt_secret, encrypt_secret

    from .oauth import OAuthError, linkedin_refresh

    refresh_token = decrypt_secret(account.refresh_token)
    if not refresh_token:
        raise OAuthError('No refresh token is stored for this account.')
    try:
        tokens = linkedin_refresh(refresh_token)
    except OAuthError as exc:
        account.last_error = str(exc)[:500]
        account.save(update_fields=['last_error', 'updated_at'])
        raise

    account.access_token = encrypt_secret(tokens['access_token'])
    account.token_expires_at = tokens['expires_at']
    if tokens.get('refresh_token'):
        account.refresh_token = encrypt_secret(tokens['refresh_token'])
        account.refresh_token_expires_at = tokens['refresh_token_expires_at']
    account.status = SocialAccount.Status.CONNECTED
    account.last_error = ''
    account.save(update_fields=[
        'access_token', 'token_expires_at', 'refresh_token', 'refresh_token_expires_at', 'status', 'last_error', 'updated_at',
    ])
    return account


@shared_task
def refresh_expiring_tokens(days_ahead=7):
    """Renews every LinkedIn token that expires within `days_ahead` days and has a
    refresh token (Epic 10: Token refresh). Meta Page tokens obtained through OAuth
    don't expire, so there's nothing to refresh on that side - a revoked Meta token is
    caught by publishing/test-connection and the account is marked EXPIRED instead.
    """
    from .oauth import OAuthError

    horizon = timezone.now() + timezone.timedelta(days=days_ahead)
    accounts = SocialAccount.objects.filter(
        platform=SocialAccount.Platform.LINKEDIN,
        status__in=[SocialAccount.Status.CONNECTED, SocialAccount.Status.EXPIRED],
        token_expires_at__isnull=False,
        token_expires_at__lte=horizon,
    ).exclude(refresh_token='').select_related('company')

    refreshed = 0
    for account in accounts:
        try:
            refresh_account_token(account)
            refreshed += 1
        except OAuthError as exc:
            notify_admins(
                actor=None,
                notification_type=Notification.NotificationType.SOCIAL_TOKEN_EXPIRED,
                title=f'LinkedIn token for {account.company.name} could not be refreshed',
                message=f'"{account.account_name}": {exc}. Reconnect it with "Connect with LinkedIn".',
                url=f'/companies/{account.company_id}/social-accounts',
                company=account.company,
            )
    return refreshed
