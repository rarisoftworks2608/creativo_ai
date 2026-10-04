"""Subscription automation (Epic 17: Renewal date / Expiry; Epic 23: daily jobs)."""

import datetime

from celery import shared_task
from django.utils import timezone

from apps.activity_log.models import ActivityLog
from apps.activity_log.services import log_activity
from apps.notifications.models import Notification
from apps.notifications.services import notify_admins

from .models import BillingRecord, Subscription


@shared_task
def check_subscriptions():
    """Daily: expires subscriptions past their end date, reminds admins (once per day
    at most) about ones expiring within the configured window, and flags overdue invoices."""
    from apps.platform_settings.models import PlatformSettings

    today = timezone.localdate()
    reminder_days = PlatformSettings.load().subscription_expiry_reminder_days
    expired = reminded = overdue = 0

    for subscription in Subscription.objects.filter(
        status__in=Subscription.CURRENT_STATUSES, end_date__lt=today,
    ).select_related('company', 'plan'):
        subscription.status = Subscription.Status.EXPIRED
        subscription.save(update_fields=['status', 'updated_at'])
        expired += 1
        notify_admins(
            actor=None, notification_type=Notification.NotificationType.SUBSCRIPTION_EXPIRED,
            title=f'{subscription.company.name}\'s subscription expired',
            message=f'{subscription.plan.name} ended on {subscription.end_date}. Renew it under Subscriptions.',
            url=f'/companies/{subscription.company_id}/subscription', company=subscription.company,
        )
        log_activity(module=ActivityLog.Module.SUBSCRIPTION, action='Subscription expired',
                     description=f'{subscription.company.name} — {subscription.plan.name}', company=subscription.company)

    if reminder_days:
        horizon = today + datetime.timedelta(days=reminder_days)
        for subscription in Subscription.objects.filter(
            status__in=Subscription.CURRENT_STATUSES, end_date__gte=today, end_date__lte=horizon,
        ).exclude(last_reminder_sent_on=today).select_related('company', 'plan'):
            days_left = (subscription.end_date - today).days
            # Remind at the start of the window, a few days out, and the final day.
            if days_left not in (reminder_days, 3, 1, 0) and subscription.last_reminder_sent_on is not None:
                continue
            notify_admins(
                actor=None, notification_type=Notification.NotificationType.SUBSCRIPTION_EXPIRING,
                title=f'{subscription.company.name}\'s subscription expires in {days_left} day(s)',
                message=f'{subscription.plan.name} ends on {subscription.end_date}'
                        f'{" (marked auto-renew - record the renewal)" if subscription.auto_renew else ""}.',
                url=f'/companies/{subscription.company_id}/subscription', company=subscription.company,
            )
            subscription.last_reminder_sent_on = today
            subscription.save(update_fields=['last_reminder_sent_on', 'updated_at'])
            reminded += 1

    overdue = BillingRecord.objects.filter(
        payment_status__in=[BillingRecord.PaymentStatus.PENDING, BillingRecord.PaymentStatus.PARTIALLY_PAID],
        due_date__lt=today,
    ).update(payment_status=BillingRecord.PaymentStatus.OVERDUE, updated_at=timezone.now())

    return {'expired': expired, 'reminded': reminded, 'overdue_invoices': overdue}


@shared_task
def recalculate_storage_usage():
    from apps.companies.models import Company

    from .usage import calculate_storage

    count = 0
    for company in Company.objects.all():
        calculate_storage(company)
        count += 1
    return count
