"""OAuth connection flows for Meta (Facebook Pages + Instagram professional accounts)
and LinkedIn (member profile + Company Pages) - Epic 10: Connect / OAuth / Page &
Organization selection / Token management.

Flow (both providers):
  1. start      - the API returns the provider's authorization URL, with a signed `state`
                  binding the login to this company + admin.
  2. provider   - the admin logs in and grants permissions; the provider redirects the
                  browser to the frontend route /oauth/callback/<provider>?code=..&state=..
  3. complete   - the frontend posts code+state to the API, which exchanges the code for
                  tokens and discovers every page / IG account / organization the login
                  can manage, storing them (encrypted) in a short-lived SocialOAuthSession.
  4. connect    - the admin ticks which accounts to connect; SocialAccount rows are
                  created/updated with encrypted tokens.

All HTTP goes through httpx; any failure is raised as OAuthError with a message that is
safe to show an admin.
"""

import json
import secrets
from datetime import timedelta
from urllib.parse import urlencode

import httpx
from django.conf import settings
from django.core import signing
from django.utils import timezone

from common.crypto import decrypt_secret, encrypt_secret

STATE_SALT = 'social-oauth-state'
STATE_MAX_AGE_SECONDS = 15 * 60
SESSION_LIFETIME = timedelta(minutes=30)
TIMEOUT = 20.0


class OAuthError(Exception):
    """A provider rejected the request or returned something unusable."""


# ---------------------------------------------------------------- shared helpers

def redirect_uri(provider):
    return f'{settings.SOCIAL_OAUTH_REDIRECT_BASE.rstrip("/")}/oauth/callback/{provider}'


def build_state(*, company_id, user_id, provider):
    return signing.dumps(
        {'c': company_id, 'u': user_id, 'p': provider, 'n': secrets.token_urlsafe(8)}, salt=STATE_SALT,
    )


def parse_state(state, *, provider, company_id, user_id):
    try:
        data = signing.loads(state, salt=STATE_SALT, max_age=STATE_MAX_AGE_SECONDS)
    except signing.SignatureExpired as exc:
        raise OAuthError('The login took too long and expired - please start again.') from exc
    except signing.BadSignature as exc:
        raise OAuthError('Invalid login state - please start the connection again.') from exc
    if data.get('p') != provider or data.get('c') != company_id or data.get('u') != user_id:
        raise OAuthError('This login was started for a different company or user - please start again.')
    return data


def provider_status():
    return {
        'meta': {
            'configured': bool(settings.META_APP_ID and settings.META_APP_SECRET),
            'redirect_uri': redirect_uri('meta'),
            'graph_api_version': settings.META_GRAPH_API_VERSION,
            'scopes': [] if settings.META_LOGIN_CONFIG_ID else list(settings.META_OAUTH_SCOPES),
            'uses_login_configuration': bool(settings.META_LOGIN_CONFIG_ID),
        },
        'linkedin': {
            'configured': bool(settings.LINKEDIN_CLIENT_ID and settings.LINKEDIN_CLIENT_SECRET),
            'redirect_uri': redirect_uri('linkedin'),
            'api_version': settings.LINKEDIN_API_VERSION,
            'scopes': list(settings.LINKEDIN_OAUTH_SCOPES),
        },
    }


def encrypt_payload(candidates):
    return encrypt_secret(json.dumps(candidates))


def decrypt_payload(ciphertext):
    plaintext = decrypt_secret(ciphertext)
    if not plaintext:
        return []
    try:
        return json.loads(plaintext)
    except json.JSONDecodeError:
        return []


def public_candidates(candidates):
    """Strip tokens before anything goes back to the browser."""
    hidden = {'token', 'refresh_token'}
    return [{k: v for k, v in c.items() if k not in hidden} for c in candidates]


def _error_message(response):
    try:
        data = response.json()
    except ValueError:
        return response.text[:300]
    error = data.get('error')
    if isinstance(error, dict):
        return error.get('message') or str(error)[:300]
    return data.get('error_description') or data.get('message') or str(error or data)[:300]


# ---------------------------------------------------------------- Meta

def _graph_url(path):
    return f'https://graph.facebook.com/{settings.META_GRAPH_API_VERSION}/{path.lstrip("/")}'


def meta_authorization_url(state):
    if not (settings.META_APP_ID and settings.META_APP_SECRET):
        raise OAuthError('Meta app credentials are not configured. Set META_APP_ID and META_APP_SECRET in the backend .env.')
    params = {
        'client_id': settings.META_APP_ID,
        'redirect_uri': redirect_uri('meta'),
        'state': state,
        'response_type': 'code',
    }
    if settings.META_LOGIN_CONFIG_ID:
        params['config_id'] = settings.META_LOGIN_CONFIG_ID
        params['override_default_response_type'] = 'true'
    else:
        params['scope'] = ','.join(settings.META_OAUTH_SCOPES)
    return f'https://www.facebook.com/{settings.META_GRAPH_API_VERSION}/dialog/oauth?{urlencode(params)}'


def _meta_get(path, params):
    try:
        response = httpx.get(_graph_url(path), params=params, timeout=TIMEOUT)
    except httpx.HTTPError as exc:
        raise OAuthError(f'Could not reach Facebook: {exc}') from exc
    if response.status_code >= 400:
        raise OAuthError(f'Facebook returned an error: {_error_message(response)}')
    return response.json()


def meta_exchange_code(code):
    """code -> short-lived user token -> long-lived (~60 day) user token."""
    short = _meta_get('oauth/access_token', {
        'client_id': settings.META_APP_ID,
        'client_secret': settings.META_APP_SECRET,
        'redirect_uri': redirect_uri('meta'),
        'code': code,
    })
    short_token = short.get('access_token')
    if not short_token:
        raise OAuthError('Facebook did not return an access token.')
    long_lived = _meta_get('oauth/access_token', {
        'grant_type': 'fb_exchange_token',
        'client_id': settings.META_APP_ID,
        'client_secret': settings.META_APP_SECRET,
        'fb_exchange_token': short_token,
    })
    token = long_lived.get('access_token') or short_token
    expires_in = long_lived.get('expires_in')
    return token, (timezone.now() + timedelta(seconds=int(expires_in))) if expires_in else None


def meta_granted_scopes(user_token):
    try:
        data = _meta_get('me/permissions', {'access_token': user_token})
    except OAuthError:
        return []
    return [p['permission'] for p in data.get('data', []) if p.get('status') == 'granted']


def meta_discover_accounts(user_token, user_token_expires_at=None):
    """Every Facebook Page the user manages, plus the Instagram professional account
    linked to each Page. Page tokens minted from a long-lived user token don't expire,
    and the Instagram Graph API is called with the parent Page's token."""
    fields = (
        'id,name,category,access_token,followers_count,fan_count,picture{url},'
        'instagram_business_account{id,username,name,profile_picture_url,followers_count}'
    )
    candidates = []
    params = {'fields': fields, 'limit': 100, 'access_token': user_token}
    next_url = None
    pages_seen = 0
    while True:
        if next_url:
            try:
                response = httpx.get(next_url, timeout=TIMEOUT)
            except httpx.HTTPError as exc:
                raise OAuthError(f'Could not reach Facebook: {exc}') from exc
            if response.status_code >= 400:
                raise OAuthError(f'Facebook returned an error: {_error_message(response)}')
            data = response.json()
        else:
            data = _meta_get('me/accounts', params)

        for page in data.get('data', []):
            pages_seen += 1
            page_token = page.get('access_token', '')
            picture = ((page.get('picture') or {}).get('data') or {}).get('url', '')
            candidates.append({
                'key': f'facebook:{page["id"]}',
                'platform': 'facebook',
                'account_id': page['id'],
                'name': page.get('name', ''),
                'username': '',
                'picture_url': picture,
                'followers_count': page.get('followers_count') or page.get('fan_count'),
                'token': page_token,
                'token_expires_at': None,
                'metadata': {
                    'account_type': 'page', 'page_id': page['id'], 'category': page.get('category', ''),
                    'picture_url': picture, 'followers_count': page.get('followers_count') or page.get('fan_count'),
                    'user_token_expires_at': user_token_expires_at.isoformat() if user_token_expires_at else None,
                },
            })
            ig = page.get('instagram_business_account')
            if ig:
                candidates.append({
                    'key': f'instagram:{ig["id"]}',
                    'platform': 'instagram',
                    'account_id': ig['id'],
                    'name': ig.get('name') or ig.get('username', ''),
                    'username': ig.get('username', ''),
                    'picture_url': ig.get('profile_picture_url', ''),
                    'followers_count': ig.get('followers_count'),
                    'token': page_token,
                    'token_expires_at': None,
                    'metadata': {
                        'account_type': 'ig_business', 'page_id': page['id'], 'page_name': page.get('name', ''),
                        'username': ig.get('username', ''), 'picture_url': ig.get('profile_picture_url', ''),
                        'followers_count': ig.get('followers_count'),
                    },
                })
        next_url = (data.get('paging') or {}).get('next')
        if not next_url or pages_seen > 500:
            break

    warnings = []
    if not candidates:
        warnings.append(
            'No Facebook Pages were found for this login. Make sure the account is an admin of the Page '
            'and that you ticked the Page (and its Instagram account) in the Facebook permission dialog.'
        )
    elif not any(c['platform'] == 'instagram' for c in candidates):
        warnings.append(
            'No Instagram professional account is linked to these Pages. Switch the Instagram account to '
            'Business/Creator and link it to the Facebook Page (Instagram app > Settings > Account type and tools).'
        )
    return candidates, warnings


# ---------------------------------------------------------------- LinkedIn

LINKEDIN_AUTH_URL = 'https://www.linkedin.com/oauth/v2/authorization'
LINKEDIN_TOKEN_URL = 'https://www.linkedin.com/oauth/v2/accessToken'
LINKEDIN_API = 'https://api.linkedin.com'


def linkedin_headers(token):
    return {
        'Authorization': f'Bearer {token}',
        'LinkedIn-Version': settings.LINKEDIN_API_VERSION,
        'X-Restli-Protocol-Version': '2.0.0',
    }


def linkedin_authorization_url(state):
    if not (settings.LINKEDIN_CLIENT_ID and settings.LINKEDIN_CLIENT_SECRET):
        raise OAuthError(
            'LinkedIn app credentials are not configured. Set LINKEDIN_CLIENT_ID and LINKEDIN_CLIENT_SECRET in the backend .env.'
        )
    params = {
        'response_type': 'code',
        'client_id': settings.LINKEDIN_CLIENT_ID,
        'redirect_uri': redirect_uri('linkedin'),
        'state': state,
        'scope': ' '.join(settings.LINKEDIN_OAUTH_SCOPES),
    }
    return f'{LINKEDIN_AUTH_URL}?{urlencode(params)}'


def _linkedin_token_request(data):
    try:
        response = httpx.post(
            LINKEDIN_TOKEN_URL,
            data={**data, 'client_id': settings.LINKEDIN_CLIENT_ID, 'client_secret': settings.LINKEDIN_CLIENT_SECRET},
            headers={'Content-Type': 'application/x-www-form-urlencoded'},
            timeout=TIMEOUT,
        )
    except httpx.HTTPError as exc:
        raise OAuthError(f'Could not reach LinkedIn: {exc}') from exc
    if response.status_code >= 400:
        raise OAuthError(f'LinkedIn returned an error: {_error_message(response)}')
    payload = response.json()
    now = timezone.now()
    return {
        'access_token': payload.get('access_token', ''),
        'expires_at': now + timedelta(seconds=int(payload['expires_in'])) if payload.get('expires_in') else None,
        'refresh_token': payload.get('refresh_token', ''),
        'refresh_token_expires_at': (
            now + timedelta(seconds=int(payload['refresh_token_expires_in']))
            if payload.get('refresh_token_expires_in') else None
        ),
        'scopes': [s for s in (payload.get('scope') or '').replace(',', ' ').split() if s],
    }


def linkedin_exchange_code(code):
    tokens = _linkedin_token_request({
        'grant_type': 'authorization_code', 'code': code, 'redirect_uri': redirect_uri('linkedin'),
    })
    if not tokens['access_token']:
        raise OAuthError('LinkedIn did not return an access token.')
    return tokens


def linkedin_refresh(refresh_token):
    return _linkedin_token_request({'grant_type': 'refresh_token', 'refresh_token': refresh_token})


def linkedin_discover_accounts(tokens):
    token = tokens['access_token']
    candidates, warnings = [], []
    shared = {
        'token': token,
        'refresh_token': tokens.get('refresh_token', ''),
        'token_expires_at': tokens['expires_at'].isoformat() if tokens.get('expires_at') else None,
        'refresh_token_expires_at': (
            tokens['refresh_token_expires_at'].isoformat() if tokens.get('refresh_token_expires_at') else None
        ),
        'scopes': tokens.get('scopes', []),
    }

    try:
        me = httpx.get(f'{LINKEDIN_API}/v2/userinfo', headers={'Authorization': f'Bearer {token}'}, timeout=TIMEOUT)
    except httpx.HTTPError as exc:
        raise OAuthError(f'Could not reach LinkedIn: {exc}') from exc
    if me.status_code < 400:
        profile = me.json()
        member_id = profile.get('sub', '')
        if member_id:
            candidates.append({
                'key': f'linkedin:person:{member_id}',
                'platform': 'linkedin',
                'account_id': member_id,
                'name': profile.get('name') or 'LinkedIn member',
                'username': '',
                'picture_url': profile.get('picture', ''),
                'followers_count': None,
                'metadata': {'account_type': 'person', 'urn': f'urn:li:person:{member_id}', 'picture_url': profile.get('picture', '')},
                **shared,
            })

    try:
        acls = httpx.get(
            f'{LINKEDIN_API}/rest/organizationAcls',
            params={'q': 'roleAssignee', 'role': 'ADMINISTRATOR', 'state': 'APPROVED'},
            headers=linkedin_headers(token),
            timeout=TIMEOUT,
        )
    except httpx.HTTPError as exc:
        raise OAuthError(f'Could not reach LinkedIn: {exc}') from exc

    if acls.status_code >= 400:
        warnings.append(
            'Company Pages could not be listed - the LinkedIn app needs the Community Management API product '
            f'(and rw_organization_admin scope) to post as a Page. LinkedIn said: {_error_message(acls)}'
        )
    else:
        for element in acls.json().get('elements', []):
            org_urn = element.get('organization') or element.get('organizationTarget') or ''
            org_id = org_urn.rsplit(':', 1)[-1]
            if not org_id:
                continue
            name, vanity = f'Organization {org_id}', ''
            try:
                org = httpx.get(f'{LINKEDIN_API}/rest/organizations/{org_id}', headers=linkedin_headers(token), timeout=TIMEOUT)
                if org.status_code < 400:
                    org_data = org.json()
                    name = org_data.get('localizedName') or name
                    vanity = org_data.get('vanityName', '')
            except httpx.HTTPError:
                pass
            candidates.append({
                'key': f'linkedin:organization:{org_id}',
                'platform': 'linkedin',
                'account_id': org_id,
                'name': name,
                'username': vanity,
                'picture_url': '',
                'followers_count': None,
                'metadata': {'account_type': 'organization', 'urn': f'urn:li:organization:{org_id}', 'vanity_name': vanity},
                **shared,
            })

    if not candidates:
        warnings.append('No LinkedIn profile or Company Page could be read with this login.')
    return candidates, warnings
