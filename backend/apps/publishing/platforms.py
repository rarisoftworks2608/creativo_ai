"""Platform publishers (Epic 11: Publish now / Multi-platform publishing).

- Facebook Pages  - Graph API, media uploaded as file bytes (works on localhost too).
- Instagram       - Graph API content publishing: create a media container from a
                    *public* URL, wait until Meta has processed it, then publish it.
- LinkedIn        - Posts API: upload image/video bytes, then create the post as the
                    member or Company Page the account represents.

Every failure is raised as PublishError, classified as retryable (rate limits, timeouts,
5xx, "media not ready") or not (bad request, missing permission), plus whether it's an
auth problem - which marks the social account EXPIRED so an admin reconnects it.
"""

import json
import re
import time

import httpx
from django.conf import settings

from common.crypto import decrypt_secret

from . import media as media_utils
from .models import PublishJob

TIMEOUT = httpx.Timeout(60.0, connect=15.0)
UPLOAD_TIMEOUT = httpx.Timeout(600.0, connect=20.0)

# Meta error codes worth retrying (temporary/rate limited) - see
# developers.facebook.com/docs/graph-api/guides/error-handling
META_TRANSIENT_CODES = {1, 2, 4, 17, 32, 341, 613, 9007, 2207051}
META_AUTH_CODES = {102, 190, 463, 467}
# Instagram container processing can take a while for video.
IG_IMAGE_POLL = (2, 30)     # seconds between polls, max polls
IG_VIDEO_POLL = (10, 60)


class PublishError(Exception):
    def __init__(self, message, *, retryable=True, auth_error=False):
        super().__init__(message)
        self.retryable = retryable
        self.auth_error = auth_error


class PublishResult:
    def __init__(self, external_id, url='', raw=None):
        self.external_id = str(external_id)
        self.url = url
        self.raw = raw or {}


def _sleep(seconds):
    time.sleep(seconds)


# ------------------------------------------------------------------ Meta helpers

def _graph(path, *, video=False):
    host = 'graph-video.facebook.com' if video else 'graph.facebook.com'
    return f'https://{host}/{settings.META_GRAPH_API_VERSION}/{path.lstrip("/")}'


def _meta_raise(response):
    try:
        error = response.json().get('error') or {}
    except ValueError:
        error = {}
    code = error.get('code')
    message = error.get('error_user_msg') or error.get('message') or response.text[:300]
    auth = response.status_code == 401 or code in META_AUTH_CODES
    permission = code == 10 or (isinstance(code, int) and 200 <= code <= 299)
    retryable = not auth and not permission and (
        response.status_code >= 500 or response.status_code == 429 or code in META_TRANSIENT_CODES
        or bool(error.get('is_transient'))
    )
    if permission:
        message = f'{message} (missing permission - reconnect the account and grant all requested permissions)'
    raise PublishError(f'Meta API error{f" {code}" if code else ""}: {message}', retryable=retryable, auth_error=auth)


def _meta_request(method, url, **kwargs):
    try:
        response = httpx.request(method, url, timeout=kwargs.pop('timeout', TIMEOUT), **kwargs)
    except httpx.HTTPError as exc:
        raise PublishError(f'Could not reach Meta: {exc}', retryable=True) from exc
    if response.status_code >= 400:
        _meta_raise(response)
    try:
        return response.json()
    except ValueError as exc:
        raise PublishError('Meta returned a non-JSON response.', retryable=True) from exc


# ------------------------------------------------------------------ Facebook

class FacebookPublisher:
    def __init__(self, account):
        self.account = account
        self.token = decrypt_secret(account.access_token)
        self.page_id = account.account_id or (account.metadata or {}).get('page_id', '')
        if not self.token:
            raise PublishError('The Facebook Page has no access token - reconnect it.', retryable=False, auth_error=True)
        if not self.page_id:
            raise PublishError('The Facebook account has no Page ID - reconnect it via "Connect with Facebook".', retryable=False)

    def publish(self, job):
        if job.post_type == PublishJob.PostType.TEXT or not job.media:
            data = _meta_request('POST', _graph(f'{self.page_id}/feed'), data={'message': job.caption, 'access_token': self.token})
            return PublishResult(data['id'], f'https://www.facebook.com/{data["id"]}', data)

        first = job.media[0]
        if first.get('kind') == 'video':
            field = media_utils.media_field(first)
            content = media_utils.read_bytes(field)
            data = _meta_request(
                'POST', _graph(f'{self.page_id}/videos', video=True),
                data={'description': job.caption, 'access_token': self.token},
                files={'source': ('video.mp4', content, 'video/mp4')},
                timeout=UPLOAD_TIMEOUT,
            )
            return PublishResult(data['id'], f'https://www.facebook.com/{self.page_id}/videos/{data["id"]}', data)

        images = [m for m in job.media if m.get('kind') == 'image']
        if len(images) == 1:
            data = self._upload_photo(images[0], caption=job.caption, published=True)
            post_id = data.get('post_id') or data['id']
            return PublishResult(post_id, f'https://www.facebook.com/{post_id}', data)

        photo_ids = [self._upload_photo(image, published=False)['id'] for image in images]
        data = _meta_request('POST', _graph(f'{self.page_id}/feed'), data={
            'message': job.caption,
            'attached_media': json.dumps([{'media_fbid': photo_id} for photo_id in photo_ids]),
            'access_token': self.token,
        })
        return PublishResult(data['id'], f'https://www.facebook.com/{data["id"]}', data)

    def _upload_photo(self, media_item, *, caption='', published=True):
        field = media_utils.media_field(media_item)
        content = media_utils.read_bytes(field)
        filename = field.name.rsplit('/', 1)[-1] or 'image.png'
        payload = {'published': 'true' if published else 'false', 'access_token': self.token}
        if caption:
            payload['caption'] = caption
        return _meta_request(
            'POST', _graph(f'{self.page_id}/photos'), data=payload,
            files={'source': (filename, content, 'application/octet-stream')}, timeout=UPLOAD_TIMEOUT,
        )


# ------------------------------------------------------------------ Instagram

class InstagramPublisher:
    def __init__(self, account):
        self.account = account
        self.token = decrypt_secret(account.access_token)
        self.ig_user_id = account.account_id
        if not self.token:
            raise PublishError('The Instagram account has no access token - reconnect it.', retryable=False, auth_error=True)
        if not self.ig_user_id:
            raise PublishError('The Instagram account has no IG user ID - reconnect it via "Connect with Facebook".', retryable=False)

    def _url_for(self, media_item, *, is_story=False):
        if media_item.get('kind') == 'image':
            url = media_utils.instagram_image_url(media_item, is_story=is_story)
        else:
            url = media_utils.public_url(media_utils.media_field(media_item))
        if not media_utils.is_publicly_reachable(url):
            raise PublishError(
                f'Instagram downloads media from a public URL, but this server\'s media URL is "{url}", which the '
                'internet can\'t reach. Set PUBLIC_MEDIA_BASE_URL (or BACKEND_PUBLIC_URL) in .env to a public '
                'https address - e.g. your domain, S3/R2 bucket, or a cloudflared/ngrok tunnel in development.',
                retryable=False,
            )
        return url

    def _create_container(self, params):
        data = _meta_request('POST', _graph(f'{self.ig_user_id}/media'), data={**params, 'access_token': self.token})
        return data['id']

    def _wait_until_ready(self, container_id, *, video):
        interval, max_polls = IG_VIDEO_POLL if video else IG_IMAGE_POLL
        for _ in range(max_polls):
            data = _meta_request('GET', _graph(container_id), params={'fields': 'status_code,status', 'access_token': self.token})
            status_code = data.get('status_code')
            if status_code in ('FINISHED', 'PUBLISHED'):
                return
            if status_code in ('ERROR', 'EXPIRED'):
                raise PublishError(f'Instagram could not process the media: {data.get("status") or status_code}', retryable=False)
            _sleep(interval)
        raise PublishError('Instagram is still processing the media - will retry.', retryable=True)

    def publish(self, job):
        if not job.media:
            raise PublishError('Instagram posts need an image or video.', retryable=False)

        is_video = job.media[0].get('kind') == 'video'
        if job.post_type == PublishJob.PostType.CAROUSEL and len(job.media) > 1:
            children = []
            for media_item in job.media[:10]:
                params = {'is_carousel_item': 'true'}
                if media_item.get('kind') == 'video':
                    params.update({'media_type': 'VIDEO', 'video_url': self._url_for(media_item)})
                else:
                    params['image_url'] = self._url_for(media_item)
                child_id = self._create_container(params)
                self._wait_until_ready(child_id, video=media_item.get('kind') == 'video')
                children.append(child_id)
            container_id = self._create_container({'media_type': 'CAROUSEL', 'children': ','.join(children), 'caption': job.caption})
            self._wait_until_ready(container_id, video=False)
        elif job.post_type == PublishJob.PostType.STORY:
            key = 'video_url' if is_video else 'image_url'
            container_id = self._create_container({'media_type': 'STORIES', key: self._url_for(job.media[0], is_story=True)})
            self._wait_until_ready(container_id, video=is_video)
        elif is_video:
            container_id = self._create_container({
                'media_type': 'REELS', 'video_url': self._url_for(job.media[0]),
                'caption': job.caption, 'share_to_feed': 'true',
            })
            self._wait_until_ready(container_id, video=True)
        else:
            container_id = self._create_container({'image_url': self._url_for(job.media[0]), 'caption': job.caption})
            self._wait_until_ready(container_id, video=False)

        published = _meta_request(
            'POST', _graph(f'{self.ig_user_id}/media_publish'), data={'creation_id': container_id, 'access_token': self.token},
        )
        media_id = published['id']
        permalink = ''
        try:
            permalink = _meta_request(
                'GET', _graph(media_id), params={'fields': 'permalink', 'access_token': self.token},
            ).get('permalink', '')
        except PublishError:
            pass
        return PublishResult(media_id, permalink, published)


# ------------------------------------------------------------------ LinkedIn

LINKEDIN_API = 'https://api.linkedin.com/rest'
LINKEDIN_RESERVED = re.compile(r'([\\|{}@\[\]()<>#*_~])')
LINKEDIN_ESCAPED_HASHTAG = re.compile(r'\\#(\w+)')


def linkedin_commentary(text):
    """LinkedIn's Posts API reads `commentary` as "little text format": reserved
    characters must be backslash-escaped or the post is rejected/garbled, and hashtags
    must be written as {hashtag|\\#|tag} templates to become real, clickable hashtags."""
    escaped = LINKEDIN_RESERVED.sub(r'\\\1', text or '')
    return LINKEDIN_ESCAPED_HASHTAG.sub(lambda m: '{hashtag|\\#|' + m.group(1) + '}', escaped)


class LinkedInPublisher:
    def __init__(self, account):
        self.account = account
        self.token = decrypt_secret(account.access_token)
        if not self.token:
            raise PublishError('The LinkedIn account has no access token - reconnect it.', retryable=False, auth_error=True)
        self.author = account.linkedin_urn

    def _headers(self, extra=None):
        return {
            'Authorization': f'Bearer {self.token}',
            'LinkedIn-Version': settings.LINKEDIN_API_VERSION,
            'X-Restli-Protocol-Version': '2.0.0',
            **(extra or {}),
        }

    def _raise(self, response):
        try:
            data = response.json()
            message = data.get('message') or data.get('error_description') or response.text[:300]
        except ValueError:
            message = response.text[:300]
        auth = response.status_code == 401
        retryable = response.status_code == 429 or response.status_code >= 500
        if response.status_code == 403:
            message = f'{message} (the token lacks posting permission for this author - reconnect with LinkedIn)'
        raise PublishError(f'LinkedIn API error {response.status_code}: {message}', retryable=retryable, auth_error=auth)

    def _request(self, method, url, **kwargs):
        try:
            response = httpx.request(method, url, timeout=kwargs.pop('timeout', TIMEOUT), **kwargs)
        except httpx.HTTPError as exc:
            raise PublishError(f'Could not reach LinkedIn: {exc}', retryable=True) from exc
        if response.status_code >= 400:
            self._raise(response)
        return response

    def _upload_image(self, media_item):
        field = media_utils.media_field(media_item)
        content = media_utils.read_bytes(field)
        init = self._request(
            'POST', f'{LINKEDIN_API}/images?action=initializeUpload', headers=self._headers(),
            json={'initializeUploadRequest': {'owner': self.author}},
        ).json()['value']
        self._request('PUT', init['uploadUrl'], content=content, headers={'Authorization': f'Bearer {self.token}'}, timeout=UPLOAD_TIMEOUT)
        return init['image']

    def _upload_video(self, media_item):
        field = media_utils.media_field(media_item)
        content = media_utils.read_bytes(field)
        init = self._request(
            'POST', f'{LINKEDIN_API}/videos?action=initializeUpload', headers=self._headers(),
            json={'initializeUploadRequest': {
                'owner': self.author, 'fileSizeBytes': len(content), 'uploadCaptions': False, 'uploadThumbnail': False,
            }},
        ).json()['value']
        etags = []
        for instruction in init.get('uploadInstructions', []):
            chunk = content[int(instruction['firstByte']):int(instruction['lastByte']) + 1]
            response = self._request(
                'PUT', instruction['uploadUrl'], content=chunk,
                headers={'Authorization': f'Bearer {self.token}', 'Content-Type': 'application/octet-stream'},
                timeout=UPLOAD_TIMEOUT,
            )
            etags.append(response.headers.get('etag', '').strip('"'))
        self._request(
            'POST', f'{LINKEDIN_API}/videos?action=finalizeUpload', headers=self._headers(),
            json={'finalizeUploadRequest': {
                'video': init['video'], 'uploadToken': init.get('uploadToken', ''), 'uploadedPartIds': etags,
            }},
        )
        return init['video']

    def publish(self, job):
        body = {
            'author': self.author,
            'commentary': linkedin_commentary(job.caption),
            'visibility': 'PUBLIC',
            'distribution': {'feedDistribution': 'MAIN_FEED', 'targetEntities': [], 'thirdPartyDistributionChannels': []},
            'lifecycleState': 'PUBLISHED',
            'isReshareDisabledByAuthor': False,
        }
        images = [m for m in job.media if m.get('kind') == 'image']
        videos = [m for m in job.media if m.get('kind') == 'video']
        if videos:
            body['content'] = {'media': {'id': self._upload_video(videos[0]), 'title': (videos[0].get('name') or '')[:200]}}
        elif len(images) > 1:
            body['content'] = {'multiImage': {'images': [{'id': self._upload_image(m), 'altText': (m.get('name') or '')[:120]} for m in images[:20]]}}
        elif images:
            body['content'] = {'media': {'id': self._upload_image(images[0]), 'altText': (images[0].get('name') or '')[:120]}}

        response = self._request('POST', f'{LINKEDIN_API}/posts', headers=self._headers(), json=body)
        urn = response.headers.get('x-restli-id') or response.headers.get('x-linkedin-id') or ''
        return PublishResult(urn, f'https://www.linkedin.com/feed/update/{urn}/' if urn else '', {'urn': urn})


PUBLISHERS = {
    'facebook': FacebookPublisher,
    'instagram': InstagramPublisher,
    'linkedin': LinkedInPublisher,
}


def get_publisher(account):
    publisher_class = PUBLISHERS.get(account.platform)
    if publisher_class is None:
        raise PublishError(f'Publishing to {account.platform} is not supported.', retryable=False)
    return publisher_class(account)


def validate_job_for_platform(platform, post_type, media):
    """Pre-flight checks shown before scheduling, so an impossible post is caught then
    rather than failing at publish time."""
    problems = []
    kinds = [m.get('kind') for m in media or []]
    if platform == 'instagram':
        if not kinds:
            problems.append('Instagram requires an image or video.')
        if post_type == PublishJob.PostType.CAROUSEL and len(kinds) > 10:
            problems.append('Instagram carousels are limited to 10 items - only the first 10 will be posted.')
        if media:
            try:
                url = media_utils.public_url(media_utils.media_field(media[0]))
                if not media_utils.is_publicly_reachable(url):
                    problems.append(
                        'Instagram needs a public media URL - set PUBLIC_MEDIA_BASE_URL in the backend .env '
                        '(see docs/meta-setup-guide.md) or publishing to Instagram will fail.'
                    )
            except media_utils.MediaUnavailable as exc:
                problems.append(str(exc))
    if platform == 'linkedin' and post_type == PublishJob.PostType.STORY:
        problems.append('LinkedIn has no stories - it will be posted as a regular image post.')
    if platform == 'facebook' and post_type == PublishJob.PostType.STORY:
        problems.append('Facebook Page stories are not supported via this integration - it will be posted as a photo.')
    return problems
