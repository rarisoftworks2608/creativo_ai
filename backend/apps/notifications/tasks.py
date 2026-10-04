"""Scheduled tasks (Epic 12/13: Reminder).

Requires a Celery Beat process running alongside the worker for
send_content_reminders to actually fire on schedule:
    celery -A config beat -l info
"""

import datetime

from celery import shared_task
from django.utils import timezone

from apps.authentication.models import User
from apps.content_calendar.models import ContentCalendarItem

from .models import Notification
from .services import notify

REMINDER_WINDOW_DAYS = 1


@shared_task
def send_content_reminders():
    """Reminds admins about content scheduled soon that's still sitting in draft.

    Each (item, admin) pair is only reminded once - a Reminder notification
    already existing for that item/recipient means it was already sent.
    """
    # Local (TIME_ZONE) date, not the UTC date - between midnight and 05:30 IST the UTC
    # date is still "yesterday", which made the window miss content due tomorrow.
    today = timezone.localdate()
    horizon = today + datetime.timedelta(days=REMINDER_WINDOW_DAYS)

    due_items = ContentCalendarItem.objects.filter(
        scheduled_date__gte=today,
        scheduled_date__lte=horizon,
        status=ContentCalendarItem.Status.DRAFT,
    ).select_related('company')

    admins = list(User.objects.filter(role=User.Role.ADMIN, is_active=True))
    sent = 0

    for item in due_items:
        already_reminded = set(
            Notification.objects.filter(
                notification_type=Notification.NotificationType.REMINDER, content_calendar_item=item,
            ).values_list('recipient_id', flat=True)
        )
        for admin in admins:
            if admin.id in already_reminded:
                continue
            notify(
                admin,
                Notification.NotificationType.REMINDER,
                title=f'"{item.topic}" is still in draft',
                message=(
                    f'Scheduled for {item.scheduled_date} at {item.company.name}, '
                    'but has not been generated or approved yet.'
                ),
                url=f'/companies/{item.company_id}/calendar',
                company=item.company,
                content_calendar_item=item,
            )
            sent += 1

    return sent


@shared_task
def send_approval_reminders():
    """Reminds a company's clients about content that has been waiting for their
    approval longer than PlatformSettings.approval_reminder_hours (Epic 09/12: Reminder).

    One reminder per review round: once a REMINDER_SENT event exists after the item last
    entered review, it isn't reminded again until it's regenerated and resubmitted.
    Runs hourly (see CELERY_BEAT_SCHEDULE); a setting of 0 turns reminders off.
    """
    from apps.companies.models import ClientProfile
    from apps.content_calendar.models import ContentReviewEvent
    from apps.content_calendar.services import _whatsapp, content_link, pending_since, record_review_event
    from apps.platform_settings.models import PlatformSettings

    hours = PlatformSettings.load().approval_reminder_hours
    if not hours:
        return 0

    cutoff = timezone.now() - datetime.timedelta(hours=hours)
    items = ContentCalendarItem.objects.filter(
        status=ContentCalendarItem.Status.PENDING_APPROVAL,
    ).select_related('company')

    reminded = 0
    for item in items:
        since = pending_since(item)
        if since > cutoff:
            continue
        if item.review_events.filter(action=ContentReviewEvent.Action.REMINDER_SENT, created_at__gte=since).exists():
            continue

        recipients = [
            profile.user for profile in item.company.clients.select_related('user')
            if profile.user.is_active and profile.can_access(ClientProfile.Page.CALENDAR)
        ]
        waiting_hours = int((timezone.now() - since).total_seconds() // 3600)
        for user in recipients:
            notify(
                user,
                Notification.NotificationType.REMINDER,
                title=f'"{item.topic}" is waiting for your approval',
                message=f'Generated {waiting_hours} hours ago and scheduled for {item.scheduled_date}. '
                        'Please approve it or request changes.',
                url=content_link(item),
                company=item.company,
                content_calendar_item=item,
            )
        record_review_event(item, ContentReviewEvent.Action.REMINDER_SENT, metadata={'recipients': len(recipients)})
        _whatsapp(item.company, 'approval_reminder', {
            'topic': item.topic, 'scheduled_date': item.scheduled_date.isoformat(),
            'hours_waiting': str(waiting_hours), 'url': content_link(item),
        })
        reminded += 1

    return reminded
