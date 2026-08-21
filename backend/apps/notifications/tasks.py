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
    today = timezone.now().date()
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
