"""Usage tracking (Epic 17: Creative / Video / Publishing / Storage usage, Usage
percentage, Usage limits).

Usage is counted per monthly period anchored on the subscription's start day (a
subscription starting on the 15th renews its allowance on the 15th of each month);
without a subscription the calendar month is used. Counting rules:
  - creatives / videos: generation requests started in the period, excluding failed ones
    (a failed generation produced nothing, so it doesn't burn allowance)
  - publishing: posts created in the period that weren't cancelled/failed
  - storage: every stored media file for the company (cached, recalculated daily)
"""

import calendar
import datetime

from django.core.cache import cache
from django.db.models import Q
from django.utils import timezone

from .models import Subscription, UsageSnapshot

CACHE_SECONDS = 60
METRIC_LABELS = {
    'creative': 'Creative generations',
    'video': 'Video generations',
    'publishing': 'Published posts',
    'storage': 'Storage',
    'social_accounts': 'Social accounts',
}


def get_current_subscription(company, today=None):
    today = today or timezone.localdate()
    return (
        Subscription.objects.select_related('plan')
        .filter(company=company, status__in=Subscription.CURRENT_STATUSES, start_date__lte=today)
        .filter(Q(end_date__isnull=True) | Q(end_date__gte=today))
        .order_by('-start_date', '-created_at')
        .first()
    )


def _clamp(year, month, day):
    return datetime.date(year, month, min(day, calendar.monthrange(year, month)[1]))


def usage_period(subscription, today=None):
    today = today or timezone.localdate()
    if subscription is None:
        return today.replace(day=1), _clamp(today.year, today.month, 31)

    anchor = subscription.start_date.day
    start = _clamp(today.year, today.month, anchor)
    if start > today:
        year, month = (today.year, today.month - 1) if today.month > 1 else (today.year - 1, 12)
        start = _clamp(year, month, anchor)
    start = max(start, subscription.start_date)
    next_year, next_month = (start.year, start.month + 1) if start.month < 12 else (start.year + 1, 1)
    end = _clamp(next_year, next_month, anchor) - datetime.timedelta(days=1)
    if subscription.end_date and end > subscription.end_date:
        end = subscription.end_date
    return start, end


def _metric(used, limit):
    unlimited = not limit
    percentage = 0 if unlimited else min(round(used / limit * 100, 1), 999)
    return {
        'used': used,
        'limit': limit or 0,
        'unlimited': unlimited,
        'remaining': None if unlimited else max(limit - used, 0),
        'percentage': percentage,
        'exceeded': (not unlimited) and used >= limit,
    }


def _cache_key(company_id):
    return f'subscription-usage:{company_id}'


def invalidate_usage_cache(company_id):
    cache.delete(_cache_key(company_id))


def compute_usage(company, today=None, *, use_cache=True):
    from apps.creative_generation.models import GenerationRequest
    from apps.publishing.models import PublishJob
    from apps.social_accounts.models import SocialAccount
    from apps.video_generation.models import VideoGenerationRequest

    if use_cache and today is None:
        cached = cache.get(_cache_key(company.id))
        if cached is not None:
            return cached

    subscription = get_current_subscription(company, today)
    start, end = usage_period(subscription, today)
    limits = subscription.effective_limits if subscription else {
        'creative': 0, 'video': 0, 'publishing': 0, 'storage_mb': 0, 'social_accounts': 0,
    }

    creative_used = GenerationRequest.objects.filter(
        company=company, created_at__date__gte=start, created_at__date__lte=end,
    ).exclude(status=GenerationRequest.Status.FAILED).count()
    video_used = VideoGenerationRequest.objects.filter(
        company=company, created_at__date__gte=start, created_at__date__lte=end,
    ).exclude(status=VideoGenerationRequest.Status.FAILED).count()
    publishing_used = PublishJob.objects.filter(
        company=company, created_at__date__gte=start, created_at__date__lte=end,
    ).exclude(status__in=[PublishJob.Status.FAILED, PublishJob.Status.CANCELLED]).count()
    social_used = SocialAccount.objects.filter(company=company).exclude(status=SocialAccount.Status.DISCONNECTED).count()

    snapshot = UsageSnapshot.objects.filter(company=company).first()
    storage_bytes = snapshot.storage_bytes if snapshot else 0
    storage_mb = round(storage_bytes / (1024 * 1024), 2)

    result = {
        'subscription_id': subscription.id if subscription else None,
        'has_subscription': subscription is not None,
        'period': {'start': start.isoformat(), 'end': end.isoformat()},
        'metrics': {
            'creative': _metric(creative_used, limits['creative']),
            'video': _metric(video_used, limits['video']),
            'publishing': _metric(publishing_used, limits['publishing']),
            'storage': {**_metric(storage_mb, limits['storage_mb']), 'unit': 'MB', 'bytes': storage_bytes},
            'social_accounts': _metric(social_used, limits['social_accounts']),
        },
        'storage_calculated_at': snapshot.calculated_at.isoformat() if snapshot else None,
    }
    if use_cache and today is None:
        cache.set(_cache_key(company.id), result, CACHE_SECONDS)
    return result


def _file_size(field):
    if not field:
        return 0
    try:
        return field.storage.size(field.name)
    except Exception:  # noqa: BLE001 - missing file / remote storage hiccup
        return 0


def calculate_storage(company):
    """Walks every stored media file for the company and caches the total."""
    from apps.brand.models import BrandAsset, BrandProfile
    from apps.creative_generation.models import GenerationVariation
    from apps.video_generation.models import VideoGenerationRequest, VideoScene

    breakdown = {'brand': 0, 'creatives': 0, 'videos': 0, 'reports': 0}
    count = 0

    profile = BrandProfile.objects.filter(company=company).first()
    if profile:
        for field in (profile.logo, profile.secondary_logo, profile.favicon):
            size = _file_size(field)
            breakdown['brand'] += size
            count += bool(size)
    for asset in BrandAsset.objects.filter(company=company).only('file'):
        size = _file_size(asset.file)
        breakdown['brand'] += size
        count += bool(size)
    for variation in GenerationVariation.objects.filter(generation_request__company=company).only('image'):
        size = _file_size(variation.image)
        breakdown['creatives'] += size
        count += bool(size)
    for video in VideoGenerationRequest.objects.filter(company=company).only('video_file', 'thumbnail'):
        for field in (video.video_file, video.thumbnail):
            size = _file_size(field)
            breakdown['videos'] += size
            count += bool(size)
    for scene in VideoScene.objects.filter(video_request__company=company).only('image', 'voice_over_audio', 'video_clip'):
        for field in (scene.image, scene.voice_over_audio, scene.video_clip):
            size = _file_size(field)
            breakdown['videos'] += size
            count += bool(size)
    try:
        from apps.reports.models import Report

        for report in Report.objects.filter(company=company).only('pdf_file', 'xlsx_file', 'csv_file'):
            for field in (report.pdf_file, report.xlsx_file, report.csv_file):
                size = _file_size(field)
                breakdown['reports'] += size
                count += bool(size)
    except Exception:  # noqa: BLE001 - reports app optional at migration time
        pass

    total = sum(breakdown.values())
    snapshot, _ = UsageSnapshot.objects.update_or_create(
        company=company, defaults={'storage_bytes': total, 'file_count': count, 'breakdown': breakdown},
    )
    invalidate_usage_cache(company.id)
    return snapshot
