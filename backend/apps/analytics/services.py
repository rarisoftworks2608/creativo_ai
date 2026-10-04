"""Analytics sync + aggregation (Epic 15: Performance - Engagement rate, Top posts,
Best content type, Best platform, Growth, Campaign performance)."""

import datetime
import logging
from collections import defaultdict

from django.db.models import Sum
from django.utils import timezone

from apps.publishing.models import PublishJob
from apps.social_accounts.models import SocialAccount

from . import fetchers
from .models import METRIC_FIELDS, AccountMetricSnapshot, AnalyticsSyncLog, PostMetrics, PostMetricSnapshot

logger = logging.getLogger(__name__)

SYNC_WINDOW_DAYS = 90  # posts older than this rarely change - stop polling them


# ------------------------------------------------------------------ sync

def sync_post(job):
    """Fetches and stores the latest metrics for one published job. Raises FetchError."""
    metrics, raw = fetchers.fetch_post_metrics(job)
    item = job.content_calendar_item
    record, _ = PostMetrics.objects.get_or_create(
        publish_job=job,
        defaults={'company_id': job.company_id, 'platform': job.platform},
    )
    record.company_id = job.company_id
    record.platform = job.platform
    record.published_at = job.published_at
    record.post_type = job.post_type
    record.content_type = (item.content_type if item else '')[:100]
    record.campaign = (item.campaign if item else '')[:255]
    for field in METRIC_FIELDS:
        if field in metrics:
            setattr(record, field, max(int(metrics[field] or 0), 0))
    record.recompute()
    record.raw = raw
    record.sync_error = raw.get('insights', {}).get('_insights_error', '') if isinstance(raw.get('insights'), dict) else ''
    record.last_synced_at = timezone.now()
    record.save()
    PostMetricSnapshot.objects.create(
        post_metrics=record, **{field: getattr(record, field) for field in (*METRIC_FIELDS, 'engagements')},
    )
    return record


def snapshot_account(account, day=None):
    data = fetchers.fetch_account_metrics(account)
    snapshot, _ = AccountMetricSnapshot.objects.update_or_create(
        social_account=account, date=day or timezone.localdate(),
        defaults={
            'company_id': account.company_id, 'platform': account.platform,
            'followers': data.get('followers'), 'following': data.get('following'),
            'media_count': data.get('media_count'), 'raw': data.get('raw') or {},
        },
    )
    if data.get('followers') is not None:
        account.metadata = {**(account.metadata or {}), 'followers_count': data['followers']}
        account.save(update_fields=['metadata', 'updated_at'])
    return snapshot


def sync_company(company, *, triggered_by=None):
    log = AnalyticsSyncLog.objects.create(company=company, triggered_by=triggered_by)
    since = timezone.now() - datetime.timedelta(days=SYNC_WINDOW_DAYS)
    jobs = PublishJob.objects.filter(
        company=company, status=PublishJob.Status.PUBLISHED, published_at__gte=since,
    ).exclude(external_post_id='').select_related('social_account', 'content_calendar_item')

    errors = []
    for job in jobs:
        try:
            sync_post(job)
            log.posts_synced += 1
        except fetchers.FetchError as exc:
            log.posts_failed += 1
            errors.append({'type': 'post', 'id': job.id, 'platform': job.platform, 'message': str(exc)[:500]})
            PostMetrics.objects.filter(publish_job=job).update(sync_error=str(exc)[:1000])
        except Exception as exc:  # noqa: BLE001 - one bad post must not abort the run
            logger.exception('Analytics sync failed for job %s', job.id)
            log.posts_failed += 1
            errors.append({'type': 'post', 'id': job.id, 'platform': job.platform, 'message': f'Unexpected: {exc}'[:500]})

    for account in SocialAccount.objects.filter(company=company, status=SocialAccount.Status.CONNECTED).exclude(access_token=''):
        try:
            snapshot_account(account)
            log.accounts_synced += 1
        except fetchers.FetchError as exc:
            errors.append({'type': 'account', 'id': account.id, 'platform': account.platform, 'message': str(exc)[:500]})
        except Exception as exc:  # noqa: BLE001
            logger.exception('Account snapshot failed for %s', account.id)
            errors.append({'type': 'account', 'id': account.id, 'platform': account.platform, 'message': f'Unexpected: {exc}'[:500]})

    if not errors:
        log.status = AnalyticsSyncLog.Status.SUCCEEDED
    elif log.posts_synced or log.accounts_synced:
        log.status = AnalyticsSyncLog.Status.PARTIAL
    else:
        log.status = AnalyticsSyncLog.Status.FAILED
    log.errors = errors[:100]
    log.finished_at = timezone.now()
    log.save()
    return log


# ------------------------------------------------------------------ aggregation

def _rate(engagements, base):
    return round(engagements / base * 100, 2) if base else 0.0


def _totals(rows):
    totals = {field: sum(getattr(r, field) for r in rows) for field in (*METRIC_FIELDS, 'engagements')}
    base = totals['reach'] or totals['impressions'] or totals['views']
    totals['posts'] = len(rows)
    totals['engagement_rate'] = _rate(totals['engagements'], base)
    return totals


def _parse_range(start, end):
    today = timezone.localdate()
    end_date = end or today
    start_date = start or (end_date - datetime.timedelta(days=29))
    if start_date > end_date:
        start_date, end_date = end_date, start_date
    return start_date, end_date


def summary(company, *, start=None, end=None, platform=None, request=None):
    start_date, end_date = _parse_range(start, end)
    jobs = PublishJob.objects.filter(
        company=company, status=PublishJob.Status.PUBLISHED,
        published_at__date__gte=start_date, published_at__date__lte=end_date,
    ).select_related('content_calendar_item', 'social_account')
    if platform:
        jobs = jobs.filter(platform=platform)
    jobs = list(jobs)
    metrics_by_job = {m.publish_job_id: m for m in PostMetrics.objects.filter(publish_job__in=jobs)}
    rows = list(metrics_by_job.values())

    # Previous period of the same length, for growth deltas.
    length = (end_date - start_date).days + 1
    prev_start, prev_end = start_date - datetime.timedelta(days=length), start_date - datetime.timedelta(days=1)
    prev_rows = list(PostMetrics.objects.filter(
        company=company, published_at__date__gte=prev_start, published_at__date__lte=prev_end,
        **({'platform': platform} if platform else {}),
    ))
    totals = _totals(rows)
    totals['posts'] = len(jobs)
    previous = _totals(prev_rows)

    def delta(key):
        before, now = previous.get(key, 0), totals.get(key, 0)
        if not before:
            return None
        return round((now - before) / before * 100, 1)

    by_platform = defaultdict(list)
    by_type = defaultdict(list)
    by_campaign = defaultdict(list)
    for row in rows:
        by_platform[row.platform].append(row)
        by_type[row.content_type or row.post_type or 'Other'].append(row)
        if row.campaign:
            by_campaign[row.campaign].append(row)

    platform_rows = [{'platform': key, **_totals(value)} for key, value in by_platform.items()]
    for job in jobs:  # platforms with posts but no metrics yet still show their post count
        if job.platform not in by_platform:
            platform_rows.append({'platform': job.platform, **_totals([]), 'posts': 0})
            by_platform[job.platform] = []
    for row in platform_rows:
        row['posts'] = sum(1 for job in jobs if job.platform == row['platform'])
    type_rows = sorted(
        [{'content_type': key, **_totals(value)} for key, value in by_type.items()],
        key=lambda r: r['engagement_rate'], reverse=True,
    )
    campaign_rows = sorted(
        [{'campaign': key, **_totals(value)} for key, value in by_campaign.items()],
        key=lambda r: r['engagements'], reverse=True,
    )
    ranked_platforms = [r for r in platform_rows if r['engagements'] or r['reach']]
    best_platform = max(ranked_platforms, key=lambda r: r['engagement_rate'], default=None)

    top = sorted(rows, key=lambda r: (r.engagements, r.reach), reverse=True)[:5]
    from apps.publishing.media import media_preview

    top_posts = [{
        'job_id': r.publish_job_id,
        'topic': r.publish_job.content_calendar_item.topic if r.publish_job.content_calendar_item else '',
        'platform': r.platform, 'post_type': r.post_type, 'content_type': r.content_type,
        'published_at': r.published_at, 'url': r.publish_job.external_url,
        'reach': r.reach, 'impressions': r.impressions, 'engagements': r.engagements,
        'engagement_rate': r.engagement_rate, 'likes': r.likes, 'comments': r.comments, 'shares': r.shares,
        'saves': r.saves, 'media': media_preview(r.publish_job.media[:1], request),
    } for r in top]

    timeline = []
    day_rows = defaultdict(list)
    day_posts = defaultdict(int)
    for row in rows:
        if row.published_at:
            day_rows[timezone.localtime(row.published_at).date()].append(row)
    for job in jobs:
        day_posts[timezone.localtime(job.published_at).date()] += 1
    cursor = start_date
    while cursor <= end_date:
        day = day_rows.get(cursor, [])
        timeline.append({
            'date': cursor.isoformat(), 'posts': day_posts.get(cursor, 0),
            'engagements': sum(r.engagements for r in day), 'reach': sum(r.reach for r in day),
            'impressions': sum(r.impressions for r in day),
        })
        cursor += datetime.timedelta(days=1)

    followers = follower_growth(company, start_date, end_date, platform)

    return {
        'range': {'start': start_date.isoformat(), 'end': end_date.isoformat(), 'days': length},
        'totals': totals,
        'previous_totals': previous,
        'changes': {key: delta(key) for key in ('posts', 'reach', 'impressions', 'engagements', 'engagement_rate')},
        'by_platform': sorted(platform_rows, key=lambda r: r['engagements'], reverse=True),
        'by_content_type': type_rows,
        'campaigns': campaign_rows,
        'best_platform': best_platform['platform'] if best_platform else None,
        'best_content_type': type_rows[0]['content_type'] if type_rows and (type_rows[0]['engagements'] or type_rows[0]['reach']) else None,
        'top_posts': top_posts,
        'timeline': timeline,
        'followers': followers,
        'last_synced_at': (
            PostMetrics.objects.filter(company=company).order_by('-last_synced_at').values_list('last_synced_at', flat=True).first()
        ),
        'metrics_pending': max(len(jobs) - len(rows), 0),
    }


def follower_growth(company, start_date, end_date, platform=None):
    accounts = SocialAccount.objects.filter(company=company).exclude(status=SocialAccount.Status.DISCONNECTED)
    if platform:
        accounts = accounts.filter(platform=platform)
    result, total_now, total_start = [], 0, 0
    for account in accounts:
        snapshots = list(
            AccountMetricSnapshot.objects.filter(
                social_account=account, date__gte=start_date, date__lte=end_date, followers__isnull=False,
            ).order_by('date')
        )
        current = snapshots[-1].followers if snapshots else (account.metadata or {}).get('followers_count')
        first = snapshots[0].followers if snapshots else current
        if current is not None:
            total_now += current
            total_start += first or 0
        result.append({
            'account_id': account.id, 'account_name': account.account_name, 'platform': account.platform,
            'followers': current, 'growth': (current - first) if current is not None and first is not None else None,
            'series': [{'date': s.date.isoformat(), 'followers': s.followers} for s in snapshots],
        })
    return {
        'total': total_now,
        'growth': total_now - total_start,
        'growth_rate': round((total_now - total_start) / total_start * 100, 1) if total_start else None,
        'accounts': result,
    }


def platform_overview(days=30):
    """Admin: every company's headline numbers for the last `days` days."""
    from apps.companies.models import Company

    since = timezone.now() - datetime.timedelta(days=days)
    rows = []
    for company in Company.objects.filter(status=Company.Status.ACTIVE):
        published = PublishJob.objects.filter(company=company, status=PublishJob.Status.PUBLISHED, published_at__gte=since)
        agg = PostMetrics.objects.filter(company=company, published_at__gte=since).aggregate(
            reach=Sum('reach'), impressions=Sum('impressions'), engagements=Sum('engagements'),
        )
        reach, engagements = agg['reach'] or 0, agg['engagements'] or 0
        rows.append({
            'company_id': company.id, 'company_name': company.name, 'posts': published.count(),
            'reach': reach, 'impressions': agg['impressions'] or 0, 'engagements': engagements,
            'engagement_rate': _rate(engagements, reach or agg['impressions'] or 0),
        })
    rows.sort(key=lambda r: r['engagements'], reverse=True)
    totals = {
        'posts': sum(r['posts'] for r in rows), 'reach': sum(r['reach'] for r in rows),
        'engagements': sum(r['engagements'] for r in rows),
    }
    totals['engagement_rate'] = _rate(totals['engagements'], totals['reach'])
    return {'days': days, 'totals': totals, 'companies': rows}
