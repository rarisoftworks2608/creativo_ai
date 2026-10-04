"""Publishing queue (Epic 11: Publishing queue / Retry; Epic 23: scheduled publishing).

`dispatch_due_publish_jobs` runs every minute (CELERY_BEAT_SCHEDULE) and hands every due
SCHEDULED job to `publish_job`. Retries go back through the same scheduler with
exponential backoff instead of Celery's own retry, so a worker restart never loses one.
"""

import datetime
import logging

from celery import shared_task
from django.db.models import F
from django.utils import timezone

from .models import PublishJob

logger = logging.getLogger(__name__)

STUCK_AFTER = datetime.timedelta(minutes=30)
BATCH_SIZE = 50


@shared_task
def dispatch_due_publish_jobs():
    from apps.platform_settings.models import PlatformSettings

    now = timezone.now()

    # Recover jobs a crashed worker left mid-flight.
    stuck = PublishJob.objects.filter(
        status__in=[PublishJob.Status.PROCESSING, PublishJob.Status.QUEUED], updated_at__lte=now - STUCK_AFTER,
    )
    for job in stuck:
        if job.attempts >= job.max_attempts:
            from .services import mark_failed

            mark_failed(job, job.last_error or 'The publishing worker stopped responding.')
        else:
            PublishJob.objects.filter(pk=job.pk).update(status=PublishJob.Status.SCHEDULED, scheduled_at=now, updated_at=now)

    if not PlatformSettings.load().publishing_enabled:
        return 0

    due_ids = list(
        PublishJob.objects.filter(status=PublishJob.Status.SCHEDULED, scheduled_at__lte=now)
        .order_by('scheduled_at').values_list('id', flat=True)[:BATCH_SIZE]
    )
    dispatched = 0
    for job_id in due_ids:
        claimed = PublishJob.objects.filter(pk=job_id, status=PublishJob.Status.SCHEDULED).update(
            status=PublishJob.Status.QUEUED, updated_at=timezone.now(),
        )
        if not claimed:
            continue
        result = publish_job.delay(job_id)
        PublishJob.objects.filter(pk=job_id).update(celery_task_id=result.id or '')
        dispatched += 1
    return dispatched


@shared_task(bind=True)
def publish_job(self, job_id):
    from .platforms import PublishError, get_publisher
    from .services import mark_failed, mark_published, schedule_retry

    # Atomic claim: only one worker can move QUEUED -> PROCESSING, so a job can never be
    # posted twice even if it was enqueued twice.
    claimed = PublishJob.objects.filter(pk=job_id, status=PublishJob.Status.QUEUED).update(
        status=PublishJob.Status.PROCESSING, attempts=F('attempts') + 1,
        celery_task_id=self.request.id or '', updated_at=timezone.now(),
    )
    if not claimed:
        return None

    job = PublishJob.objects.select_related('social_account', 'company', 'content_calendar_item').get(pk=job_id)
    account = job.social_account
    if account is None:
        mark_failed(job, 'The social account for this post was removed.')
        return None

    try:
        publisher = get_publisher(account)
        result = publisher.publish(job)
    except PublishError as exc:
        _log_attempt(job, str(exc))
        if exc.retryable and job.attempts < job.max_attempts:
            delay = min(2 ** job.attempts, 60)
            schedule_retry(job, str(exc), delay_minutes=delay)
            logger.warning('Publish job %s failed (attempt %s), retrying in %s min: %s', job.id, job.attempts, delay, exc)
        else:
            mark_failed(job, str(exc), auth_error=exc.auth_error)
        return None
    except Exception as exc:  # noqa: BLE001 - a job must never stay stuck in PROCESSING
        logger.exception('Unexpected error publishing job %s', job.id)
        _log_attempt(job, f'Unexpected error: {exc}')
        if job.attempts < job.max_attempts:
            schedule_retry(job, f'Unexpected error: {exc}', delay_minutes=min(2 ** job.attempts, 60))
        else:
            mark_failed(job, f'Unexpected error: {exc}')
        return None

    mark_published(job, result)
    return result.external_id


def _log_attempt(job, message):
    log = list(job.error_log or [])
    log.append({'at': timezone.now().isoformat(), 'attempt': job.attempts, 'message': message[:1000]})
    job.error_log = log[-20:]
    job.save(update_fields=['error_log', 'updated_at'])
