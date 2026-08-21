"""Notification-creation helpers other apps call (Epic 13: Notification Center).

Kept here rather than on the model so callers (creative_generation,
video_generation, ...) depend on a small stable function surface instead of
constructing Notification rows by hand.
"""

from django.utils import timezone

from .models import Notification


def notify(recipient, notification_type, title, *, message='', url='', company=None, content_calendar_item=None):
    return Notification.objects.create(
        recipient=recipient,
        notification_type=notification_type,
        title=title,
        message=message,
        url=url,
        company=company,
        content_calendar_item=content_calendar_item,
    )


def notify_content_ready(*, company, created_by, notification_type, title, message='', url=''):
    """Notifies the admin who requested an AI generation, plus every client
    contact at the company - both "sides" care that new content is ready.
    """
    recipients = set()
    if created_by is not None:
        recipients.add(created_by)
    for profile in company.clients.select_related('user').all():
        recipients.add(profile.user)

    return [
        notify(user, notification_type, title, message=message, url=url, company=company)
        for user in recipients
    ]


def mark_read(notification):
    if notification.is_read:
        return notification
    notification.is_read = True
    notification.read_at = timezone.now()
    notification.save(update_fields=['is_read', 'read_at', 'updated_at'])
    return notification
