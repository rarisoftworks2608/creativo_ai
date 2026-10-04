"""Subscription limit enforcement (Epic 17: Usage limits).

Everything here is a no-op unless Admin Settings > "Enforce subscription limits" is on,
so usage is always tracked but only blocks work once the platform owner opts in.
"""

from django.core.cache import cache
from django.utils import timezone
from rest_framework import status
from rest_framework.exceptions import APIException

from .usage import METRIC_LABELS, compute_usage, get_current_subscription


class QuotaExceeded(APIException):
    status_code = status.HTTP_403_FORBIDDEN
    default_detail = 'This company has reached its subscription limit.'
    default_code = 'quota_exceeded'


def _enforced():
    from apps.platform_settings.models import PlatformSettings

    return PlatformSettings.load().enforce_subscription_limits


def _alert_admins_once(company, kind, message):
    """At most one "limit reached" notification per company+metric per day."""
    key = f'quota-alert:{company.id}:{kind}:{timezone.localdate().isoformat()}'
    if not cache.add(key, True, 60 * 60 * 26):
        return
    from apps.notifications.models import Notification
    from apps.notifications.services import notify_admins

    notify_admins(
        actor=None,
        notification_type=Notification.NotificationType.USAGE_LIMIT_REACHED,
        title=f'{company.name} reached a subscription limit',
        message=message,
        url=f'/companies/{company.id}/subscription',
        company=company,
    )


def check_quota(company, kind, amount=1):
    """kind: 'creative' | 'video' | 'publishing'. Raises QuotaExceeded when starting
    `amount` more would exceed the period's allowance."""
    if not _enforced():
        return
    if get_current_subscription(company) is None:
        message = f'{company.name} has no active subscription - assign a plan under Subscriptions.'
        _alert_admins_once(company, 'none', message)
        raise QuotaExceeded(message)

    metric = compute_usage(company, use_cache=False)['metrics'][kind]
    if metric['unlimited']:
        return
    if metric['used'] + amount > metric['limit']:
        message = (
            f'{METRIC_LABELS[kind]} limit reached for this period ({metric["used"]}/{metric["limit"]}). '
            'Upgrade the plan or raise the limit to continue.'
        )
        _alert_admins_once(company, kind, message)
        raise QuotaExceeded(message)


def check_storage(company, additional_bytes):
    if not _enforced():
        return
    subscription = get_current_subscription(company)
    if subscription is None:
        raise QuotaExceeded(f'{company.name} has no active subscription.')
    limit_mb = subscription.effective_limits['storage_mb']
    if not limit_mb:
        return
    used_bytes = compute_usage(company, use_cache=False)['metrics']['storage']['bytes']
    if used_bytes + additional_bytes > limit_mb * 1024 * 1024:
        message = f'Storage limit of {limit_mb} MB reached - delete old assets or upgrade the plan.'
        _alert_admins_once(company, 'storage', message)
        raise QuotaExceeded(message)


def check_social_account_limit(company, platform):
    if not _enforced():
        return
    subscription = get_current_subscription(company)
    if subscription is None:
        raise QuotaExceeded(f'{company.name} has no active subscription.')
    allowed = subscription.plan.allowed_platforms or []
    if allowed and platform not in allowed:
        raise QuotaExceeded(f'The {subscription.plan.name} plan does not include {platform}.')
    metric = compute_usage(company, use_cache=False)['metrics']['social_accounts']
    if not metric['unlimited'] and metric['used'] >= metric['limit']:
        raise QuotaExceeded(f'The plan allows {metric["limit"]} connected social accounts.')
