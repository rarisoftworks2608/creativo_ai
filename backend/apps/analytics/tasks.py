"""Analytics synchronization jobs (Epic 15: Scheduled sync; Epic 23: Analytics jobs)."""

import datetime

from celery import shared_task
from django.utils import timezone

from apps.notifications.models import Notification
from apps.notifications.services import notify_admins

from .models import AnalyticsSyncLog


@shared_task
def sync_company_analytics(company_id, triggered_by_id=None):
    from apps.authentication.models import User
    from apps.companies.models import Company

    from .services import sync_company

    company = Company.objects.filter(pk=company_id).first()
    if company is None:
        return None
    triggered_by = User.objects.filter(pk=triggered_by_id).first() if triggered_by_id else None
    log = sync_company(company, triggered_by=triggered_by)
    if log.status == AnalyticsSyncLog.Status.FAILED:
        notify_admins(
            actor=None, notification_type=Notification.NotificationType.ANALYTICS_SYNC_FAILED,
            title=f'Analytics sync failed for {company.name}',
            message=(log.errors[0]['message'] if log.errors else 'Unknown error')[:300],
            url=f'/companies/{company.id}/analytics', company=company,
        )
    return log.id


@shared_task
def sync_all_analytics():
    """Hourly: queues a sync for each active company whose last sync is older than
    Admin Settings > analytics sync interval."""
    from apps.companies.models import Company
    from apps.platform_settings.models import PlatformSettings
    from apps.publishing.models import PublishJob

    settings_obj = PlatformSettings.load()
    if not settings_obj.analytics_sync_enabled:
        return 0
    interval = datetime.timedelta(hours=max(1, min(settings_obj.analytics_sync_interval_hours or 6, 48)))
    now = timezone.now()
    queued = 0
    company_ids = PublishJob.objects.filter(status=PublishJob.Status.PUBLISHED).values_list('company_id', flat=True).distinct()
    for company in Company.objects.filter(pk__in=company_ids, status=Company.Status.ACTIVE):
        last = company.analytics_sync_logs.exclude(status=AnalyticsSyncLog.Status.RUNNING).order_by('-started_at').first()
        running = company.analytics_sync_logs.filter(
            status=AnalyticsSyncLog.Status.RUNNING, started_at__gte=now - datetime.timedelta(hours=1),
        ).exists()
        if running or (last and last.started_at > now - interval):
            continue
        sync_company_analytics.delay(company.id)
        queued += 1
    return queued


@shared_task
def snapshot_all_account_metrics():
    """Daily follower snapshot for every connected account (the follower-growth series)."""
    from apps.social_accounts.models import SocialAccount

    from .services import snapshot_account

    done = 0
    for account in SocialAccount.objects.filter(status=SocialAccount.Status.CONNECTED).exclude(access_token=''):
        try:
            snapshot_account(account)
            done += 1
        except Exception:  # noqa: BLE001 - one account failing must not stop the others
            continue
    return done
