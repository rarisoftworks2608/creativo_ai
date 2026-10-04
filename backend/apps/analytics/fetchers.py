"""Platform analytics fetchers (Epic 15: Fetch analytics / API failure handling).

Meta and LinkedIn rename and deprecate insight metrics regularly, so every fetcher asks
for a full metric set first, falls back to a minimal set if the platform rejects it, and
maps whatever metric names come back onto our fields - a renamed metric degrades to a
missing number instead of failing the whole sync.
"""

from urllib.parse import quote

import httpx
from django.conf import settings

from common.crypto import decrypt_secret

TIMEOUT = 30.0

# Platform metric name -> PostMetrics field
METRIC_MAP = {
    'reach': 'reach', 'impressions': 'impressions', 'views': 'views', 'plays': 'views', 'video_views': 'views',
    'saved': 'saves', 'saves': 'saves', 'shares': 'shares', 'likes': 'likes', 'comments': 'comments',
    'post_impressions': 'impressions', 'post_impressions_unique': 'reach', 'post_clicks': 'clicks',
    'post_media_view': 'views', 'total_video_views': 'views', 'total_video_impressions': 'impressions',
    'total_video_impressions_unique': 'reach',
}


class FetchError(Exception):
    def __init__(self, message, *, auth_error=False):
        super().__init__(message)
        self.auth_error = auth_error


def _graph(path):
    return f'https://graph.facebook.com/{settings.META_GRAPH_API_VERSION}/{path.lstrip("/")}'


def _get(url, params=None, headers=None):
    try:
        response = httpx.get(url, params=params, headers=headers, timeout=TIMEOUT)
    except httpx.HTTPError as exc:
        raise FetchError(f'Network error: {exc}') from exc
    if response.status_code >= 400:
        try:
            error = response.json().get('error') or {}
            message = error.get('message') if isinstance(error, dict) else str(error)
            message = message or response.json().get('message') or response.text[:300]
            code = error.get('code') if isinstance(error, dict) else None
        except ValueError:
            message, code = response.text[:300], None
        raise FetchError(message, auth_error=response.status_code == 401 or code in (102, 190))
    return response.json()


def _insight_values(payload):
    values = {}
    for metric in payload.get('data', []):
        name = metric.get('name')
        if 'total_value' in metric:
            value = (metric.get('total_value') or {}).get('value')
        else:
            series = metric.get('values') or [{}]
            value = series[-1].get('value')
        if isinstance(value, dict):  # e.g. reactions by type
            value = sum(v for v in value.values() if isinstance(v, (int, float)))
        if isinstance(value, (int, float)):
            values[name] = int(value)
    return values


def _try_insights(url, metric_sets, token, extra_params=None):
    last_error = None
    for metrics in metric_sets:
        try:
            return _insight_values(_get(url, {'metric': ','.join(metrics), 'access_token': token, **(extra_params or {})}))
        except FetchError as exc:
            if exc.auth_error:
                raise
            last_error = exc
    if last_error:
        return {'_insights_error': str(last_error)}
    return {}


def _map(values):
    mapped = {}
    for name, value in values.items():
        field = METRIC_MAP.get(name)
        if field and isinstance(value, int):
            mapped[field] = max(mapped.get(field, 0), value)
    return mapped


# ------------------------------------------------------------------ posts

def fetch_instagram_post(job, token):
    media_id = job.external_post_id
    fields = _get(_graph(media_id), {'fields': 'like_count,comments_count,media_type,media_product_type', 'access_token': token})
    is_story = job.post_type == 'story'
    metric_sets = (
        [['reach', 'views', 'replies', 'shares'], ['reach']] if is_story else
        [['reach', 'views', 'saved', 'shares', 'likes', 'comments', 'total_interactions'], ['reach', 'saved', 'shares'], ['reach']]
    )
    insights = _try_insights(_graph(f'{media_id}/insights'), metric_sets, token)
    metrics = _map(insights)
    metrics.setdefault('likes', int(fields.get('like_count') or 0))
    metrics.setdefault('comments', int(fields.get('comments_count') or 0))
    return metrics, {'fields': fields, 'insights': insights}


def fetch_facebook_post(job, token):
    post_id = job.external_post_id
    if job.post_type in ('video', 'reel'):
        fields = _get(_graph(post_id), {
            'fields': 'likes.summary(true).limit(0),comments.summary(true).limit(0)', 'access_token': token,
        })
        insights = _try_insights(
            _graph(f'{post_id}/video_insights'),
            [['total_video_views', 'total_video_impressions', 'total_video_impressions_unique'], ['total_video_views']],
            token,
        )
        metrics = _map(insights)
        metrics['likes'] = int(((fields.get('likes') or {}).get('summary') or {}).get('total_count') or 0)
        metrics['comments'] = int(((fields.get('comments') or {}).get('summary') or {}).get('total_count') or 0)
        return metrics, {'fields': fields, 'insights': insights}

    fields = _get(_graph(post_id), {
        'fields': 'shares,reactions.summary(total_count).limit(0),comments.summary(total_count).limit(0)',
        'access_token': token,
    })
    insights = _try_insights(
        _graph(f'{post_id}/insights'),
        [['post_impressions', 'post_impressions_unique', 'post_clicks'], ['post_media_view', 'post_clicks'], ['post_clicks']],
        token,
    )
    metrics = _map(insights)
    metrics['likes'] = int(((fields.get('reactions') or {}).get('summary') or {}).get('total_count') or 0)
    metrics['comments'] = int(((fields.get('comments') or {}).get('summary') or {}).get('total_count') or 0)
    metrics['shares'] = int((fields.get('shares') or {}).get('count') or 0)
    return metrics, {'fields': fields, 'insights': insights}


def _linkedin_headers(token):
    return {
        'Authorization': f'Bearer {token}',
        'LinkedIn-Version': settings.LINKEDIN_API_VERSION,
        'X-Restli-Protocol-Version': '2.0.0',
    }


def fetch_linkedin_post(job, token, account):
    urn = job.external_post_id
    if (account.metadata or {}).get('account_type') == 'person':
        raise FetchError('LinkedIn only exposes post analytics for Company Page posts, not personal profiles.')
    param = 'ugcPosts' if ':ugcPost:' in urn else 'shares'
    org = quote(account.linkedin_urn, safe='')
    url = (
        'https://api.linkedin.com/rest/organizationalEntityShareStatistics'
        f'?q=organizationalEntity&organizationalEntity={org}&{param}=List({quote(urn, safe="")})'
    )
    data = _get(url, headers=_linkedin_headers(token))
    elements = data.get('elements') or [{}]
    stats = elements[0].get('totalShareStatistics') or {}
    metrics = {
        'impressions': int(stats.get('impressionCount') or 0),
        'reach': int(stats.get('uniqueImpressionsCount') or 0),
        'clicks': int(stats.get('clickCount') or 0),
        'likes': int(stats.get('likeCount') or 0),
        'comments': int(stats.get('commentCount') or 0),
        'shares': int(stats.get('shareCount') or 0),
    }
    return metrics, {'statistics': stats}


def fetch_post_metrics(job):
    account = job.social_account
    if account is None:
        raise FetchError('The social account for this post was removed.')
    token = decrypt_secret(account.access_token)
    if not token:
        raise FetchError('The social account has no access token.', auth_error=True)
    if not job.external_post_id:
        raise FetchError('This post has no platform ID.')
    if job.platform == 'instagram':
        return fetch_instagram_post(job, token)
    if job.platform == 'facebook':
        return fetch_facebook_post(job, token)
    if job.platform == 'linkedin':
        return fetch_linkedin_post(job, token, account)
    raise FetchError(f'Analytics for {job.platform} is not supported.')


# ------------------------------------------------------------------ accounts

def fetch_account_metrics(account):
    token = decrypt_secret(account.access_token)
    if not token:
        raise FetchError('No access token.', auth_error=True)
    if account.platform == 'instagram':
        data = _get(_graph(account.account_id), {'fields': 'followers_count,follows_count,media_count', 'access_token': token})
        return {'followers': data.get('followers_count'), 'following': data.get('follows_count'),
                'media_count': data.get('media_count'), 'raw': data}
    if account.platform == 'facebook':
        page_id = account.account_id or (account.metadata or {}).get('page_id')
        data = _get(_graph(page_id), {'fields': 'followers_count,fan_count', 'access_token': token})
        return {'followers': data.get('followers_count') or data.get('fan_count'), 'raw': data}
    if account.platform == 'linkedin':
        if (account.metadata or {}).get('account_type') == 'person':
            return {'followers': None, 'raw': {'note': 'Follower counts are only available for Company Pages.'}}
        org = quote(account.linkedin_urn, safe='')
        data = _get(
            f'https://api.linkedin.com/rest/networkSizes/{org}?edgeType=COMPANY_FOLLOWED_BY_MEMBER',
            headers=_linkedin_headers(token),
        )
        return {'followers': data.get('firstDegreeSize'), 'raw': data}
    raise FetchError(f'Analytics for {account.platform} is not supported.')
