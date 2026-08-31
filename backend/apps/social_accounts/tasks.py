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
