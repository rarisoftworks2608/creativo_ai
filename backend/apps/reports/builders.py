"""Report builders (Epic 16: Client reports + Admin reports).

Each builder returns a format-neutral document:

    {
      'title': str, 'subtitle': str,
      'kpis': [{'label': str, 'value': number|str, 'hint': str}],
      'sections': [{'title': str, 'description': str, 'columns': [str], 'rows': [[cell, ...]]}],
    }

which reports/exporters.py renders identically to PDF, Excel and CSV.
"""

import datetime
from collections import Counter, defaultdict

from django.db.models import Count, Sum

from apps.companies.models import ClientProfile, Company
from apps.content_calendar.models import ContentCalendarItem, ContentReviewEvent
from apps.creative_generation.models import GenerationRequest
from apps.publishing.models import PublishJob
from apps.video_generation.models import VideoGenerationRequest


def _fmt_date(value):
    if not value:
        return ''
    if isinstance(value, datetime.datetime):
        from django.utils import timezone

        return timezone.localtime(value).strftime('%d %b %Y %H:%M')
    return value.strftime('%d %b %Y')


def _period(start, end):
    return f'{_fmt_date(start)} – {_fmt_date(end)}'


def _pct(value):
    return f'{value:.1f}%' if isinstance(value, (int, float)) else '—'


def _change(value):
    if value is None:
        return 'no previous data'
    return f'{"+" if value >= 0 else ""}{value:.1f}% vs previous period'


def _items_in_period(company, start, end):
    return ContentCalendarItem.objects.filter(company=company, scheduled_date__gte=start, scheduled_date__lte=end)


def _events_in_period(start, end, company=None):
    events = ContentReviewEvent.objects.filter(created_at__date__gte=start, created_at__date__lte=end)
    return events.filter(company=company) if company is not None else events


def _approval_hours(events):
    """Average hours between an item entering review and its approval, per item round."""
    by_item = defaultdict(list)
    for event in events.order_by('created_at').values('item_id', 'action', 'created_at'):
        by_item[event['item_id']].append(event)
    durations = []
    for item_events in by_item.values():
        submitted = None
        for event in item_events:
            if event['action'] in (ContentReviewEvent.Action.GENERATED, ContentReviewEvent.Action.REGENERATED):
                submitted = event['created_at']
            elif event['action'] == ContentReviewEvent.Action.APPROVED and submitted:
                durations.append((event['created_at'] - submitted).total_seconds() / 3600)
                submitted = None
    return round(sum(durations) / len(durations), 1) if durations else None


# ------------------------------------------------------------------ client reports

def build_content(company, start, end):
    items = _items_in_period(company, start, end)
    status_counts = dict(items.values_list('status').annotate(n=Count('id')).values_list('status', 'n'))
    events = _events_in_period(start, end, company)
    action_counts = Counter(events.values_list('action', flat=True))
    creatives = GenerationRequest.objects.filter(company=company, created_at__date__gte=start, created_at__date__lte=end)
    videos = VideoGenerationRequest.objects.filter(company=company, created_at__date__gte=start, created_at__date__lte=end)
    avg_hours = _approval_hours(events)

    type_rows = [[t or 'Unspecified', n] for t, n in items.values_list('content_type').annotate(n=Count('id')).order_by('-n')]
    return {
        'title': f'Content report — {company.name}',
        'subtitle': _period(start, end),
        'kpis': [
            {'label': 'Content planned', 'value': items.count()},
            {'label': 'Creatives generated', 'value': creatives.filter(status=GenerationRequest.Status.SUCCEEDED).count()},
            {'label': 'Videos generated', 'value': videos.filter(status=VideoGenerationRequest.Status.SUCCEEDED).count()},
            {'label': 'Approved', 'value': action_counts.get(ContentReviewEvent.Action.APPROVED, 0)},
            {'label': 'Rejected', 'value': action_counts.get(ContentReviewEvent.Action.REJECTED, 0)},
            {'label': 'Avg. approval time', 'value': f'{avg_hours} h' if avg_hours is not None else '—'},
        ],
        'sections': [
            {
                'title': 'Content by status', 'columns': ['Status', 'Items'],
                'rows': [[label, status_counts.get(value, 0)] for value, label in ContentCalendarItem.Status.choices],
            },
            {'title': 'Content by format', 'columns': ['Format', 'Items'], 'rows': type_rows},
            {
                'title': 'Review activity', 'columns': ['Event', 'Count'],
                'rows': [[label, action_counts.get(value, 0)] for value, label in ContentReviewEvent.Action.choices
                         if action_counts.get(value)],
            },
            {
                'title': 'Content calendar', 'columns': ['Date', 'Topic', 'Format', 'Platforms', 'Status', 'Regenerated'],
                'rows': [
                    [_fmt_date(i.scheduled_date), i.topic, i.content_type, ', '.join(i.platforms or []),
                     i.get_status_display(), 'Yes' if i.regeneration_count else 'No']
                    for i in items.order_by('scheduled_date')
                ],
            },
        ],
    }


def build_publishing(company, start, end):
    jobs = PublishJob.objects.filter(
        company=company, scheduled_at__date__gte=start, scheduled_at__date__lte=end,
    ).select_related('content_calendar_item', 'social_account')
    counts = Counter(jobs.values_list('status', flat=True))
    by_platform = defaultdict(Counter)
    for platform, job_status in jobs.values_list('platform', 'status'):
        by_platform[platform][job_status] += 1
    published = jobs.filter(status=PublishJob.Status.PUBLISHED).order_by('published_at')
    failed = jobs.filter(status=PublishJob.Status.FAILED)
    return {
        'title': f'Publishing report — {company.name}',
        'subtitle': _period(start, end),
        'kpis': [
            {'label': 'Published', 'value': counts.get(PublishJob.Status.PUBLISHED, 0)},
            {'label': 'Scheduled', 'value': counts.get(PublishJob.Status.SCHEDULED, 0) + counts.get(PublishJob.Status.QUEUED, 0)},
            {'label': 'Failed', 'value': counts.get(PublishJob.Status.FAILED, 0)},
            {'label': 'Platforms used', 'value': len(by_platform)},
        ],
        'sections': [
            {
                'title': 'By platform', 'columns': ['Platform', 'Published', 'Scheduled', 'Failed', 'Cancelled'],
                'rows': [[p.title(), c[PublishJob.Status.PUBLISHED], c[PublishJob.Status.SCHEDULED] + c[PublishJob.Status.QUEUED],
                          c[PublishJob.Status.FAILED], c[PublishJob.Status.CANCELLED]] for p, c in sorted(by_platform.items())],
            },
            {
                'title': 'Published content', 'columns': ['Published', 'Platform', 'Account', 'Topic', 'Type', 'Link'],
                'rows': [[_fmt_date(j.published_at), j.get_platform_display(),
                          j.social_account.account_name if j.social_account else '', j.content_calendar_item.topic if j.content_calendar_item else '',
                          j.get_post_type_display(), j.external_url] for j in published],
            },
            {
                'title': 'Failed posts', 'columns': ['Scheduled', 'Platform', 'Topic', 'Attempts', 'Error'],
                'rows': [[_fmt_date(j.scheduled_at), j.get_platform_display(),
                          j.content_calendar_item.topic if j.content_calendar_item else '', j.attempts, j.last_error[:300]] for j in failed],
            },
        ],
    }


def build_engagement(company, start, end):
    from apps.analytics.services import summary

    data = summary(company, start=start, end=end)
    totals, changes = data['totals'], data['changes']
    return {
        'title': f'Engagement report — {company.name}',
        'subtitle': _period(start, end),
        'kpis': [
            {'label': 'Posts published', 'value': totals['posts'], 'hint': _change(changes.get('posts'))},
            {'label': 'Reach', 'value': totals['reach'], 'hint': _change(changes.get('reach'))},
            {'label': 'Impressions', 'value': totals['impressions'], 'hint': _change(changes.get('impressions'))},
            {'label': 'Engagements', 'value': totals['engagements'], 'hint': _change(changes.get('engagements'))},
            {'label': 'Engagement rate', 'value': _pct(totals['engagement_rate'])},
            {'label': 'Best platform', 'value': (data['best_platform'] or '—').title()},
        ],
        'sections': [
            {
                'title': 'Performance by platform',
                'columns': ['Platform', 'Posts', 'Reach', 'Impressions', 'Likes', 'Comments', 'Shares', 'Saves', 'Engagement rate'],
                'rows': [[r['platform'].title(), r['posts'], r['reach'], r['impressions'], r['likes'], r['comments'],
                          r['shares'], r['saves'], _pct(r['engagement_rate'])] for r in data['by_platform']],
            },
            {
                'title': 'Performance by content type', 'columns': ['Content type', 'Posts', 'Reach', 'Engagements', 'Engagement rate'],
                'rows': [[r['content_type'], r['posts'], r['reach'], r['engagements'], _pct(r['engagement_rate'])]
                         for r in data['by_content_type']],
            },
            {
                'title': 'Top posts', 'columns': ['Topic', 'Platform', 'Published', 'Reach', 'Engagements', 'Rate', 'Link'],
                'rows': [[p['topic'], p['platform'].title(), _fmt_date(p['published_at']), p['reach'], p['engagements'],
                          _pct(p['engagement_rate']), p['url']] for p in data['top_posts']],
            },
            {
                'title': 'Campaign performance', 'columns': ['Campaign', 'Posts', 'Reach', 'Engagements', 'Engagement rate'],
                'rows': [[c['campaign'], c['posts'], c['reach'], c['engagements'], _pct(c['engagement_rate'])] for c in data['campaigns']],
            },
        ],
    }


def build_growth(company, start, end):
    from apps.analytics.services import follower_growth, summary

    growth = follower_growth(company, start, end)
    data = summary(company, start=start, end=end)
    return {
        'title': f'Growth report — {company.name}',
        'subtitle': _period(start, end),
        'kpis': [
            {'label': 'Total followers', 'value': growth['total']},
            {'label': 'Follower growth', 'value': growth['growth'],
             'hint': f'{growth["growth_rate"]:+.1f}%' if growth['growth_rate'] is not None else ''},
            {'label': 'Reach change', 'value': _change(data['changes'].get('reach'))},
            {'label': 'Engagement change', 'value': _change(data['changes'].get('engagements'))},
        ],
        'sections': [
            {
                'title': 'Followers by account', 'columns': ['Account', 'Platform', 'Followers', 'Growth in period'],
                'rows': [[a['account_name'], a['platform'].title(), a['followers'] if a['followers'] is not None else '—',
                          a['growth'] if a['growth'] is not None else '—'] for a in growth['accounts']],
            },
            {
                'title': 'Daily activity', 'columns': ['Date', 'Posts', 'Reach', 'Engagements'],
                'rows': [[d['date'], d['posts'], d['reach'], d['engagements']] for d in data['timeline'] if d['posts'] or d['reach']],
            },
        ],
    }


def build_monthly(company, start, end):
    content = build_content(company, start, end)
    publishing = build_publishing(company, start, end)
    engagement = build_engagement(company, start, end)
    growth = build_growth(company, start, end)
    kpi = {k['label']: k for k in content['kpis'] + publishing['kpis'] + engagement['kpis'] + growth['kpis']}
    pick = ['Content planned', 'Approved', 'Published', 'Reach', 'Engagements', 'Engagement rate', 'Total followers',
            'Follower growth', 'Best platform']
    return {
        'title': f'Monthly marketing report — {company.name}',
        'subtitle': f'{start.strftime("%B %Y")} · {_period(start, end)}',
        'kpis': [kpi[label] for label in pick if label in kpi],
        'sections': [
            engagement['sections'][0], engagement['sections'][2], engagement['sections'][1],
            growth['sections'][0], publishing['sections'][1], content['sections'][0], engagement['sections'][3],
        ],
    }


# ------------------------------------------------------------------ admin reports

def build_company_overview(start, end):
    from apps.analytics.models import PostMetrics
    from apps.subscriptions.usage import get_current_subscription

    rows = []
    for company in Company.objects.order_by('name'):
        published = PublishJob.objects.filter(company=company, status=PublishJob.Status.PUBLISHED,
                                              published_at__date__gte=start, published_at__date__lte=end).count()
        engagements = PostMetrics.objects.filter(company=company, published_at__date__gte=start,
                                                 published_at__date__lte=end).aggregate(n=Sum('engagements'))['n'] or 0
        subscription = get_current_subscription(company)
        rows.append([
            company.name, company.get_status_display(), company.industry, company.clients.count(),
            _items_in_period(company, start, end).count(), published, engagements,
            subscription.plan.name if subscription else 'None', subscription.get_status_display() if subscription else '—',
            f'{company.onboarding["completion_percentage"]}%',
        ])
    return {
        'title': 'Company report', 'subtitle': _period(start, end),
        'kpis': [
            {'label': 'Companies', 'value': Company.objects.count()},
            {'label': 'Active companies', 'value': Company.objects.filter(status=Company.Status.ACTIVE).count()},
            {'label': 'Posts published', 'value': sum(r[5] for r in rows)},
            {'label': 'Engagements', 'value': sum(r[6] for r in rows)},
        ],
        'sections': [{
            'title': 'Companies',
            'columns': ['Company', 'Status', 'Industry', 'Clients', 'Content planned', 'Published', 'Engagements', 'Plan',
                        'Subscription', 'Onboarding'],
            'rows': rows,
        }],
    }


def build_client_overview(start, end):
    from apps.authentication.models import LoginHistory

    rows = []
    for profile in ClientProfile.objects.select_related('user', 'company').order_by('company__name', 'user__email'):
        user = profile.user
        events = ContentReviewEvent.objects.filter(actor=user, created_at__date__gte=start, created_at__date__lte=end)
        logins = LoginHistory.objects.filter(user=user, was_successful=True, created_at__date__gte=start,
                                             created_at__date__lte=end).count()
        rows.append([
            profile.company.name, user.get_full_name(), user.email, 'Active' if user.is_active else 'Inactive',
            _fmt_date(user.last_login), logins,
            events.filter(action=ContentReviewEvent.Action.APPROVED).count(),
            events.filter(action=ContentReviewEvent.Action.REJECTED).count(),
            ContentCalendarItem.objects.filter(company=profile.company, status=ContentCalendarItem.Status.PENDING_APPROVAL).count(),
        ])
    return {
        'title': 'Client report', 'subtitle': _period(start, end),
        'kpis': [
            {'label': 'Client logins', 'value': len(rows)},
            {'label': 'Active clients', 'value': sum(1 for r in rows if r[3] == 'Active')},
            {'label': 'Approvals', 'value': sum(r[6] for r in rows)},
            {'label': 'Rejections', 'value': sum(r[7] for r in rows)},
        ],
        'sections': [{
            'title': 'Clients',
            'columns': ['Company', 'Name', 'Email', 'Status', 'Last login', 'Logins in period', 'Approved', 'Rejected',
                        'Pending for company'],
            'rows': rows,
        }],
    }


def build_ai_usage(start, end):
    rows = []
    total_cost = 0
    for company in Company.objects.order_by('name'):
        creatives = GenerationRequest.objects.filter(company=company, created_at__date__gte=start, created_at__date__lte=end)
        videos = VideoGenerationRequest.objects.filter(company=company, created_at__date__gte=start, created_at__date__lte=end)
        cost = (creatives.aggregate(c=Sum('cost_usd'))['c'] or 0) + (videos.aggregate(c=Sum('cost_usd'))['c'] or 0)
        total_cost += cost
        images = sum((r.usage or {}).get('images_generated', 0) for r in creatives.only('usage'))
        if not (creatives.exists() or videos.exists()):
            continue
        rows.append([
            company.name, creatives.count(), creatives.filter(status=GenerationRequest.Status.SUCCEEDED).count(),
            creatives.filter(status=GenerationRequest.Status.FAILED).count(), images, videos.count(),
            videos.filter(status=VideoGenerationRequest.Status.SUCCEEDED).count(),
            videos.filter(status=VideoGenerationRequest.Status.FAILED).count(), f'${cost:.2f}',
        ])
    models_used = Counter(
        list(GenerationRequest.objects.filter(created_at__date__gte=start, created_at__date__lte=end).exclude(model_used='')
             .values_list('model_used', flat=True))
        + list(VideoGenerationRequest.objects.filter(created_at__date__gte=start, created_at__date__lte=end).exclude(model_used='')
               .values_list('model_used', flat=True))
    )
    return {
        'title': 'AI usage report', 'subtitle': _period(start, end),
        'kpis': [
            {'label': 'Creative requests', 'value': sum(r[1] for r in rows)},
            {'label': 'Images generated', 'value': sum(r[4] for r in rows)},
            {'label': 'Video requests', 'value': sum(r[5] for r in rows)},
            {'label': 'Tracked AI cost', 'value': f'${total_cost:.2f}', 'hint': 'Only providers with a configured per-unit cost'},
        ],
        'sections': [
            {
                'title': 'Usage by company',
                'columns': ['Company', 'Creative requests', 'Succeeded', 'Failed', 'Images', 'Video requests', 'Succeeded',
                            'Failed', 'Cost'],
                'rows': rows,
            },
            {'title': 'Models used', 'columns': ['Model', 'Requests'], 'rows': [[m, n] for m, n in models_used.most_common()]},
        ],
    }


def build_approval(start, end):
    rows = []
    all_events = _events_in_period(start, end)
    for company in Company.objects.order_by('name'):
        events = all_events.filter(company=company)
        counts = Counter(events.values_list('action', flat=True))
        if not counts:
            continue
        avg = _approval_hours(events)
        rows.append([
            company.name, counts.get(ContentReviewEvent.Action.GENERATED, 0), counts.get(ContentReviewEvent.Action.APPROVED, 0),
            counts.get(ContentReviewEvent.Action.REJECTED, 0), counts.get(ContentReviewEvent.Action.REGENERATED, 0),
            ContentCalendarItem.objects.filter(company=company, status=ContentCalendarItem.Status.PENDING_APPROVAL).count(),
            f'{avg} h' if avg is not None else '—',
        ])
    totals = Counter(all_events.values_list('action', flat=True))
    decided = totals.get(ContentReviewEvent.Action.APPROVED, 0) + totals.get(ContentReviewEvent.Action.REJECTED, 0)
    return {
        'title': 'Approval report', 'subtitle': _period(start, end),
        'kpis': [
            {'label': 'Submitted for review', 'value': totals.get(ContentReviewEvent.Action.GENERATED, 0)},
            {'label': 'Approved', 'value': totals.get(ContentReviewEvent.Action.APPROVED, 0)},
            {'label': 'Rejected', 'value': totals.get(ContentReviewEvent.Action.REJECTED, 0)},
            {'label': 'First-time approval rate',
             'value': _pct(totals.get(ContentReviewEvent.Action.APPROVED, 0) / decided * 100) if decided else '—'},
            {'label': 'Avg. approval time', 'value': f'{_approval_hours(all_events)} h' if _approval_hours(all_events) is not None else '—'},
        ],
        'sections': [{
            'title': 'Approvals by company',
            'columns': ['Company', 'Submitted', 'Approved', 'Rejected', 'Regenerated', 'Pending now', 'Avg. approval time'],
            'rows': rows,
        }],
    }


def build_publishing_overview(start, end):
    rows = []
    jobs = PublishJob.objects.filter(scheduled_at__date__gte=start, scheduled_at__date__lte=end)
    grouped = defaultdict(Counter)
    for company_name, platform, job_status in jobs.values_list('company__name', 'platform', 'status'):
        grouped[(company_name, platform)][job_status] += 1
    for (company_name, platform), counts in sorted(grouped.items()):
        rows.append([company_name, platform.title(), counts[PublishJob.Status.PUBLISHED], counts[PublishJob.Status.FAILED],
                     counts[PublishJob.Status.SCHEDULED] + counts[PublishJob.Status.QUEUED], counts[PublishJob.Status.CANCELLED]])
    status_counts = Counter(jobs.values_list('status', flat=True))
    attempted = status_counts[PublishJob.Status.PUBLISHED] + status_counts[PublishJob.Status.FAILED]
    return {
        'title': 'Publishing report (all companies)', 'subtitle': _period(start, end),
        'kpis': [
            {'label': 'Published', 'value': status_counts[PublishJob.Status.PUBLISHED]},
            {'label': 'Failed', 'value': status_counts[PublishJob.Status.FAILED]},
            {'label': 'Success rate', 'value': _pct(status_counts[PublishJob.Status.PUBLISHED] / attempted * 100) if attempted else '—'},
            {'label': 'Still scheduled', 'value': status_counts[PublishJob.Status.SCHEDULED] + status_counts[PublishJob.Status.QUEUED]},
        ],
        'sections': [{
            'title': 'By company and platform', 'columns': ['Company', 'Platform', 'Published', 'Failed', 'Scheduled', 'Cancelled'],
            'rows': rows,
        }],
    }


def build_subscription(start, end):
    from apps.subscriptions.models import BillingRecord, Subscription
    from apps.subscriptions.usage import compute_usage, get_current_subscription

    rows = []
    for company in Company.objects.order_by('name'):
        subscription = get_current_subscription(company)
        usage = compute_usage(company, use_cache=False)['metrics']
        outstanding = BillingRecord.objects.filter(
            company=company, payment_status__in=[BillingRecord.PaymentStatus.PENDING, BillingRecord.PaymentStatus.OVERDUE,
                                                 BillingRecord.PaymentStatus.PARTIALLY_PAID],
        ).aggregate(total=Sum('total_amount'), paid=Sum('amount_paid'))
        due = (outstanding['total'] or 0) - (outstanding['paid'] or 0)

        def usage_cell(key):
            metric = usage[key]
            return f'{metric["used"]}/∞' if metric['unlimited'] else f'{metric["used"]}/{metric["limit"]} ({metric["percentage"]}%)'

        rows.append([
            company.name, subscription.plan.name if subscription else 'None',
            subscription.get_status_display() if subscription else '—',
            _fmt_date(subscription.start_date) if subscription else '', _fmt_date(subscription.end_date) if subscription else '',
            usage_cell('creative'), usage_cell('video'), usage_cell('publishing'),
            f'{usage["storage"]["used"]} MB', f'{due:.2f}' if due else '0.00',
        ])
    paid_in_period = BillingRecord.objects.filter(paid_on__gte=start, paid_on__lte=end).aggregate(n=Sum('amount_paid'))['n'] or 0
    current = Subscription.objects.filter(status__in=Subscription.CURRENT_STATUSES)
    return {
        'title': 'Subscription report', 'subtitle': _period(start, end),
        'kpis': [
            {'label': 'Active subscriptions', 'value': current.count()},
            {'label': 'Companies without a plan', 'value': sum(1 for r in rows if r[1] == 'None')},
            {'label': 'Payments received in period', 'value': f'{paid_in_period:.2f}'},
            {'label': 'Outstanding balance', 'value': f'{sum(float(r[9]) for r in rows):.2f}'},
        ],
        'sections': [{
            'title': 'Subscriptions & usage',
            'columns': ['Company', 'Plan', 'Status', 'Start', 'Expiry', 'Creatives', 'Videos', 'Published', 'Storage',
                        'Balance due'],
            'rows': rows,
        }],
    }


CLIENT_BUILDERS = {
    'monthly': build_monthly, 'content': build_content, 'publishing': build_publishing,
    'engagement': build_engagement, 'growth': build_growth,
}
ADMIN_BUILDERS = {
    'company_overview': build_company_overview, 'client_overview': build_client_overview, 'ai_usage': build_ai_usage,
    'approval': build_approval, 'publishing_overview': build_publishing_overview, 'subscription': build_subscription,
}


def build(report):
    if report.report_type in CLIENT_BUILDERS:
        document = CLIENT_BUILDERS[report.report_type](report.company, report.period_start, report.period_end)
    else:
        document = ADMIN_BUILDERS[report.report_type](report.period_start, report.period_end)
    document['generated_for'] = report.company.name if report.company else 'Platform'
    return document
