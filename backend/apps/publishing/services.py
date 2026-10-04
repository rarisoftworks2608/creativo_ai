"""Publishing workflow (Epic 11) - creating/scheduling jobs, auto-scheduling approved
content (Epic 22: Automation Engine - Publishing leg), and recording outcomes."""

import datetime
import logging
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.activity_log.models import ActivityLog
from apps.activity_log.services import log_activity
from apps.content_calendar.models import ContentCalendarItem, ContentReviewEvent
from apps.content_calendar.services import record_review_event
from apps.notifications.models import Notification
from apps.notifications.services import notify, notify_admins
from apps.social_accounts.models import SocialAccount

from . import media as media_utils
from .models import PublishJob

logger = logging.getLogger(__name__)

PUBLISHABLE_ITEM_STATUSES = (ContentCalendarItem.Status.APPROVED, ContentCalendarItem.Status.PUBLISHED)


def _platform_settings():
    from apps.platform_settings.models import PlatformSettings

    return PlatformSettings.load()


def platform_timezone():
    name = _platform_settings().timezone_name
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError):
        return timezone.get_default_timezone()


def item_publish_datetime(item):
    """The calendar item's date + time (or the default publish time) in the platform
    timezone, as an aware datetime - never in the past."""
    settings_obj = _platform_settings()
    local_time = item.scheduled_time or settings_obj.default_publish_time
    scheduled = datetime.datetime.combine(item.scheduled_date, local_time, tzinfo=platform_timezone())
    now = timezone.now()
    return scheduled if scheduled > now else now


def _client_recipients(company):
    from apps.companies.models import ClientProfile

    return [
        profile.user for profile in company.clients.select_related('user')
        if profile.user.is_active and profile.can_access(ClientProfile.Page.PUBLISHING)
    ]


def _whatsapp(company, event, context):
    try:
        from apps.whatsapp.services import dispatch_event

        dispatch_event(company, event, context)
    except Exception:  # noqa: BLE001 - WhatsApp must never break publishing
        logger.exception('WhatsApp dispatch failed for %s', event)


@transaction.atomic
def create_publish_jobs(item, accounts, *, scheduled_at=None, actor=None, caption=None, post_type=None):
    """Creates one PublishJob per social account for an approved calendar item.

    Validates: item is approved, every account belongs to the item's company and is
    connected, the item has media to post, and (when enforced) the subscription's
    publishing quota. Returns the created jobs.
    """
    from apps.subscriptions.enforcement import check_quota

    if item.status not in PUBLISHABLE_ITEM_STATUSES:
        raise ValidationError({'detail': 'Only approved content can be published or scheduled.'})
    if not accounts:
        raise ValidationError({'detail': 'Select at least one connected social account.'})
    for account in accounts:
        if account.company_id != item.company_id:
            raise ValidationError({'detail': f'"{account.account_name}" does not belong to this company.'})
        if not account.is_usable:
            raise ValidationError({'detail': f'"{account.account_name}" is not connected - reconnect it first.'})

    try:
        resolved_type, media, resolved_caption = media_utils.resolve_content(item)
    except media_utils.MediaUnavailable as exc:
        raise ValidationError({'detail': str(exc)}) from exc

    check_quota(item.company, 'publishing', amount=len(accounts))

    when = scheduled_at or timezone.now()
    max_attempts = max(1, min(int(_platform_settings().publish_max_attempts or 3), 10))
    jobs = []
    for account in accounts:
        job_type = post_type or resolved_type
        # Platform-specific fallbacks: stories only exist on Instagram here.
        if job_type == PublishJob.PostType.STORY and account.platform != SocialAccount.Platform.INSTAGRAM:
            job_type = PublishJob.PostType.IMAGE
        jobs.append(PublishJob.objects.create(
            company=item.company,
            content_calendar_item=item,
            social_account=account,
            platform=account.platform,
            post_type=job_type,
            caption=caption if caption is not None else resolved_caption,
            media=media,
            scheduled_at=when,
            status=PublishJob.Status.SCHEDULED,
            max_attempts=max_attempts,
            created_by=actor,
        ))

    record_review_event(
        item, ContentReviewEvent.Action.SCHEDULED, actor=actor,
        metadata={'jobs': [job.id for job in jobs], 'scheduled_at': when.isoformat(),
                  'platforms': sorted({job.platform for job in jobs})},
    )
    log_activity(
        module=ActivityLog.Module.PUBLISHING, action='Content scheduled',
        description=f'{item.topic} → {", ".join(a.get_platform_display() for a in accounts)} at {when:%Y-%m-%d %H:%M}',
        company=item.company, user=actor,
    )
    return jobs


def auto_schedule_on_approval(item, actor=None):
    """Epic 22: approved content goes straight into the publishing queue - one job per
    connected account on each of the item's platforms, at the item's planned date/time.
    A no-op unless Admin Settings > "auto-schedule on approval" is on."""
    settings_obj = _platform_settings()
    if not settings_obj.auto_schedule_on_approval:
        return []
    accounts = list(SocialAccount.objects.filter(
        company=item.company, platform__in=item.platforms or [], status=SocialAccount.Status.CONNECTED,
    ).exclude(access_token=''))
    if not accounts:
        notify_admins(
            actor=None,
            notification_type=Notification.NotificationType.PUBLISHING_FAILED,
            title=f'"{item.topic}" was approved but could not be auto-scheduled',
            message=f'{item.company.name} has no connected account for: {", ".join(item.platforms or [])}.',
            url=f'/companies/{item.company_id}/social-accounts',
            company=item.company,
        )
        return []
    try:
        return create_publish_jobs(item, accounts, scheduled_at=item_publish_datetime(item), actor=actor)
    except ValidationError as exc:
        detail = exc.detail.get('detail') if isinstance(exc.detail, dict) else exc.detail
        notify_admins(
            actor=None,
            notification_type=Notification.NotificationType.PUBLISHING_FAILED,
            title=f'"{item.topic}" could not be auto-scheduled',
            message=str(detail),
            url=f'/companies/{item.company_id}/publishing',
            company=item.company,
        )
        return []


def enqueue_job(job):
    """Moves a job to QUEUED and hands it to a worker - unless it's already in flight."""
    from .tasks import publish_job

    claimed = PublishJob.objects.filter(
        pk=job.pk, status__in=[PublishJob.Status.SCHEDULED, PublishJob.Status.FAILED, PublishJob.Status.CANCELLED],
    ).update(status=PublishJob.Status.QUEUED, updated_at=timezone.now())
    if not claimed:
        return job
    result = publish_job.delay(job.pk)
    PublishJob.objects.filter(pk=job.pk).update(celery_task_id=result.id or '')
    job.refresh_from_db()
    return job


def mark_published(job, result):
    job.status = PublishJob.Status.PUBLISHED
    job.external_post_id = result.external_id
    job.external_url = (result.url or '')[:500]
    job.published_at = timezone.now()
    job.last_error = ''
    job.save(update_fields=['status', 'external_post_id', 'external_url', 'published_at', 'last_error', 'updated_at'])

    item = job.content_calendar_item
    platform = job.get_platform_display()
    if item is not None:
        remaining = item.publish_jobs.filter(status__in=PublishJob.ACTIVE_STATUSES).exclude(pk=job.pk).exists()
        if not remaining and item.status != ContentCalendarItem.Status.PUBLISHED:
            item.status = ContentCalendarItem.Status.PUBLISHED
            item.save(update_fields=['status', 'updated_at'])
        record_review_event(
            item, ContentReviewEvent.Action.PUBLISHED,
            metadata={'job_id': job.id, 'platform': job.platform, 'url': job.external_url},
        )

    topic = item.topic if item else f'Post #{job.id}'
    url = f'/companies/{job.company_id}/publishing'
    title = f'"{topic}" was published to {platform}'
    notify_admins(actor=None, notification_type=Notification.NotificationType.CONTENT_PUBLISHED, title=title,
                  message=job.external_url, url=url, company=job.company)
    for user in _client_recipients(job.company):
        notify(user, Notification.NotificationType.CONTENT_PUBLISHED, title, message=job.external_url, url=url,
               company=job.company, content_calendar_item=item)
    log_activity(module=ActivityLog.Module.PUBLISHING, action='Content published',
                 description=f'{topic} → {platform}', company=job.company)
    _whatsapp(job.company, 'content_published', {'topic': topic, 'platform': platform, 'url': job.external_url or url})

    # Record the publish against the subscription's usage history.
    try:
        from apps.subscriptions.usage import invalidate_usage_cache

        invalidate_usage_cache(job.company_id)
    except Exception:  # noqa: BLE001
        pass


def mark_failed(job, message, *, auth_error=False):
    job.status = PublishJob.Status.FAILED
    job.last_error = message[:2000]
    job.save(update_fields=['status', 'last_error', 'updated_at'])

    if auth_error and job.social_account_id:
        SocialAccount.objects.filter(pk=job.social_account_id).update(
            status=SocialAccount.Status.EXPIRED, last_error=message[:500], updated_at=timezone.now(),
        )

    item = job.content_calendar_item
    if item is not None:
        record_review_event(
            item, ContentReviewEvent.Action.PUBLISH_FAILED, feedback=message[:2000],
            metadata={'job_id': job.id, 'platform': job.platform},
        )
    topic = item.topic if item else f'Post #{job.id}'
    platform = job.get_platform_display()
    notify_admins(
        actor=None, notification_type=Notification.NotificationType.PUBLISHING_FAILED,
        title=f'Publishing "{topic}" to {platform} failed', message=message[:500],
        url=f'/companies/{job.company_id}/publishing', company=job.company,
    )
    log_activity(module=ActivityLog.Module.PUBLISHING, action='Publishing failed',
                 description=f'{topic} → {platform}: {message[:300]}', company=job.company)
    _whatsapp(job.company, 'publishing_failed', {'topic': topic, 'platform': platform, 'error': message[:300]})


def schedule_retry(job, message, delay_minutes):
    job.status = PublishJob.Status.SCHEDULED
    job.scheduled_at = timezone.now() + datetime.timedelta(minutes=delay_minutes)
    job.last_error = message[:2000]
    job.save(update_fields=['status', 'scheduled_at', 'last_error', 'updated_at'])
