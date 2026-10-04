"""Resolves *what* gets posted for a calendar item, and *how* platforms can reach it
(Epic 11: Publish approved content).

- Images come from the approved creative variation (or every variation, in order, for a
  Carousel creative); videos from the item's latest successfully rendered video.
- Facebook and LinkedIn receive the actual file bytes (uploaded by us). Instagram (and
  WhatsApp) only accept a URL they download themselves, so those need a *public* media
  URL - see settings.PUBLIC_MEDIA_BASE_URL.
"""

import hashlib
import io
from urllib.parse import urlparse

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from PIL import Image

from apps.creative_generation.models import GenerationRequest, GenerationVariation
from apps.video_generation.models import VideoGenerationRequest

from .models import PublishJob

LOCAL_HOSTS = {'localhost', '127.0.0.1', '0.0.0.0', '::1', 'backend', 'web'}


class MediaUnavailable(Exception):
    """The item has no publishable media (nothing generated/approved yet)."""


def _latest_succeeded_video(item):
    return item.video_generation_requests.filter(status=VideoGenerationRequest.Status.SUCCEEDED).order_by('-created_at').first()


def _latest_succeeded_creative(item):
    return item.generation_requests.filter(status=GenerationRequest.Status.SUCCEEDED).order_by('-created_at').first()


def resolve_content(item):
    """Returns (post_type, media_list, caption) for a calendar item's approved content."""
    video = _latest_succeeded_video(item)
    creative = _latest_succeeded_creative(item)

    use_video = video is not None and video.video_file and (
        creative is None or video.created_at >= creative.created_at
    )
    if use_video:
        media = [{
            'kind': 'video', 'source': 'video_request', 'id': video.id,
            'name': video.prompt_brief.strip()[:80] or video.get_video_type_display(),
            'duration_seconds': video.duration_seconds, 'aspect_ratio': video.aspect_ratio,
        }]
        is_short_vertical = video.aspect_ratio == VideoGenerationRequest.AspectRatio.VERTICAL
        post_type = PublishJob.PostType.REEL if is_short_vertical else PublishJob.PostType.VIDEO
        return post_type, media, build_caption(item, variation=None)

    if creative is not None:
        variations = list(creative.variations.order_by('variation_number'))
        variations = [v for v in variations if v.image]
        if not variations:
            raise MediaUnavailable('The approved creative has no images.')
        if creative.creative_type == GenerationRequest.CreativeType.CAROUSEL and len(variations) >= 2:
            media = [_variation_media(v) for v in variations]
            primary = next((v for v in variations if v.is_selected), variations[0])
            return PublishJob.PostType.CAROUSEL, media, build_caption(item, variation=primary)
        chosen = next((v for v in variations if v.is_selected), variations[0])
        post_type = (
            PublishJob.PostType.STORY if creative.creative_type == GenerationRequest.CreativeType.STORY
            else PublishJob.PostType.IMAGE
        )
        return post_type, [_variation_media(chosen)], build_caption(item, variation=chosen)

    raise MediaUnavailable('This content has no generated creative or video to publish yet.')


def _variation_media(variation):
    return {
        'kind': 'image', 'source': 'variation', 'id': variation.id,
        'name': variation.headline or f'Variation {variation.variation_number}',
    }


def build_caption(item, variation=None):
    """Final post text: the approved variation's caption (or the calendar brief), the CTA,
    then hashtags - de-duplicated so a caption that already ends with them isn't doubled."""
    if variation is not None and variation.caption:
        body = variation.caption.strip()
        cta = variation.cta.strip()
        hashtags = list(variation.hashtags or []) or list(item.hashtags or [])
    else:
        body = (item.caption_requirements or item.topic or '').strip()
        cta = (item.cta or '').strip()
        hashtags = list(item.hashtags or [])

    parts = [body]
    if cta and cta.lower() not in body.lower():
        parts.append(cta)
    tags = []
    for tag in hashtags:
        tag = str(tag).strip()
        if not tag:
            continue
        tag = tag if tag.startswith('#') else f'#{tag.replace(" ", "")}'
        if tag.lower() not in body.lower() and tag not in tags:
            tags.append(tag)
    if tags:
        parts.append(' '.join(tags))
    return '\n\n'.join(p for p in parts if p)


def media_field(media_item):
    """The FieldFile behind one media snapshot entry."""
    if media_item.get('source') == 'variation':
        variation = GenerationVariation.objects.filter(pk=media_item.get('id')).first()
        if variation is None or not variation.image:
            raise MediaUnavailable('The image for this post no longer exists.')
        return variation.image
    if media_item.get('source') == 'video_request':
        video = VideoGenerationRequest.objects.filter(pk=media_item.get('id')).first()
        if video is None or not video.video_file:
            raise MediaUnavailable('The video for this post no longer exists.')
        return video.video_file
    raise MediaUnavailable(f'Unknown media source "{media_item.get("source")}".')


def read_bytes(field):
    with field.open('rb') as handle:
        return handle.read()


def public_url_for_name(name, storage=None):
    """An absolute URL for a stored file name that an external platform can download."""
    storage = storage or default_storage
    url = storage.url(name)
    if url.startswith(('http://', 'https://')):
        return url
    if settings.PUBLIC_MEDIA_BASE_URL:
        return f'{settings.PUBLIC_MEDIA_BASE_URL.rstrip("/")}/{name.lstrip("/")}'
    return f'{settings.BACKEND_PUBLIC_URL.rstrip("/")}/{url.lstrip("/")}'


def public_url(field):
    return public_url_for_name(field.name, field.storage)


# Instagram's content publishing API only accepts JPEG images, and feed posts must have
# an aspect ratio between 4:5 (portrait) and 1.91:1 (landscape) - anything else is
# rejected. Generated images can be PNG (Gemini / Hugging Face / OpenAI output when no
# overlay is composited) or 2:3 portrait (OpenAI's 1024x1536), so Instagram gets a
# prepared copy: JPEG, centre-cropped into the allowed range. Copies are content-hashed,
# so re-publishing the same image reuses the same file.
IG_MIN_RATIO = 4 / 5
IG_MAX_RATIO = 1.91


def _fit_instagram_ratio(image):
    width, height = image.size
    ratio = width / height
    if ratio < IG_MIN_RATIO:
        new_height = int(width / IG_MIN_RATIO)
        top = (height - new_height) // 2
        return image.crop((0, top, width, top + new_height))
    if ratio > IG_MAX_RATIO:
        new_width = int(height * IG_MAX_RATIO)
        left = (width - new_width) // 2
        return image.crop((left, 0, left + new_width, height))
    return image


def instagram_image_url(media_item, *, is_story=False):
    field = media_field(media_item)
    data = read_bytes(field)
    image = Image.open(io.BytesIO(data))
    is_jpeg = (image.format or '').upper() == 'JPEG'
    ratio_ok = is_story or IG_MIN_RATIO <= image.width / image.height <= IG_MAX_RATIO
    if is_jpeg and ratio_ok:
        return public_url(field)

    prepared = image.convert('RGB')
    if not is_story:
        prepared = _fit_instagram_ratio(prepared)
    buffer = io.BytesIO()
    prepared.save(buffer, format='JPEG', quality=92)
    content = buffer.getvalue()
    name = f'publishing/instagram/{hashlib.sha1(content).hexdigest()[:20]}.jpg'
    if not default_storage.exists(name):
        name = default_storage.save(name, ContentFile(content))
    return public_url_for_name(name)


def is_publicly_reachable(url):
    host = (urlparse(url).hostname or '').lower()
    if not host or host in LOCAL_HOSTS:
        return False
    if host.startswith(('10.', '192.168.')) or host.endswith('.local'):
        return False
    if host.startswith('172.'):
        try:
            if 16 <= int(host.split('.')[1]) <= 31:
                return False
        except (IndexError, ValueError):
            pass
    return True


def media_preview(media_list, request=None):
    """Browser-facing URLs for the UI preview of a job's media."""
    previews = []
    for media_item in media_list or []:
        try:
            field = media_field(media_item)
        except MediaUnavailable:
            continue
        url = field.url
        if request is not None and not url.startswith(('http://', 'https://')):
            url = request.build_absolute_uri(url)
        previews.append({**media_item, 'url': url})
    return previews
