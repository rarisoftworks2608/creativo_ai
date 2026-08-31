"""Automation Engine (Epic 22): turns a due content calendar item into a queued AI
generation request automatically, on its scheduled_date, with no admin click needed.

content_type/platforms are deliberately free text on ContentCalendarItem (see its
docstring) - there's no DB-level enum to map 1:1 onto GenerationRequest.creative_type /
VideoGenerationRequest.video_type, so _pick_creative_type/_pick_video_type make a
best-effort keyword match and fall back to a platform-based default. An admin can always
override by editing the item and clicking "Generate" manually before its date arrives -
manual generation already flips status away from DRAFT/SCHEDULED, so this task simply
never picks it up.
"""

from celery import shared_task
from django.utils import timezone

from apps.creative_generation.models import GenerationRequest
from apps.creative_generation.views import _enqueue as _enqueue_creative
from apps.video_generation.models import VideoGenerationRequest
from apps.video_generation.views import _enqueue as _enqueue_video

from .models import ContentCalendarItem

VIDEO_KEYWORDS = ('reel', 'video', 'short')

CREATIVE_TYPE_KEYWORDS = [
    ('carousel', GenerationRequest.CreativeType.CAROUSEL),
    ('story', GenerationRequest.CreativeType.STORY),
    ('festival', GenerationRequest.CreativeType.FESTIVAL_CREATIVE),
    ('product', GenerationRequest.CreativeType.PRODUCT_CREATIVE),
    ('promo', GenerationRequest.CreativeType.PROMOTIONAL_CREATIVE),
]

VIDEO_TYPE_KEYWORDS = [
    ('short', VideoGenerationRequest.VideoType.SHORT_VIDEO),
    ('product', VideoGenerationRequest.VideoType.PRODUCT_VIDEO),
    ('educational', VideoGenerationRequest.VideoType.EDUCATIONAL_VIDEO),
    ('how-to', VideoGenerationRequest.VideoType.EDUCATIONAL_VIDEO),
    ('promo', VideoGenerationRequest.VideoType.PROMOTIONAL_VIDEO),
]


def _is_video(content_type):
    normalized = (content_type or '').lower()
    return any(keyword in normalized for keyword in VIDEO_KEYWORDS)


def _pick_creative_type(item):
    normalized = (item.content_type or '').lower()
    for keyword, creative_type in CREATIVE_TYPE_KEYWORDS:
        if keyword in normalized:
            return creative_type
    if 'linkedin' in item.platforms:
        return GenerationRequest.CreativeType.LINKEDIN_POST
    if 'facebook' in item.platforms:
        return GenerationRequest.CreativeType.FACEBOOK_POST
    return GenerationRequest.CreativeType.INSTAGRAM_POST


def _pick_video_type(item):
    normalized = (item.content_type or '').lower()
    for keyword, video_type in VIDEO_TYPE_KEYWORDS:
        if keyword in normalized:
            return video_type
    if 'linkedin' in item.platforms:
        return VideoGenerationRequest.VideoType.LINKEDIN_VIDEO
    if 'facebook' in item.platforms:
        return VideoGenerationRequest.VideoType.FACEBOOK_REEL
    return VideoGenerationRequest.VideoType.INSTAGRAM_REEL


def _build_prompt_brief(item):
    parts = [item.topic]
    if item.creative_requirements:
        parts.append(item.creative_requirements)
    if item.caption_requirements:
        parts.append(item.caption_requirements)
    if item.cta:
        parts.append(f'Include the CTA "{item.cta}".')
    return ' '.join(parts)


def generate_now(item):
    """Starts generation for a single DRAFT/SCHEDULED calendar item right away - the
    same effect as waiting for `auto_generate_due_content` to pick it up on its
    scheduled_date, used both by that scheduled sweep and by the admin's manual
    "Generate now" button on the calendar queue (Epic 22: Content Automation).
    """
    prompt_brief = _build_prompt_brief(item)
    if _is_video(item.content_type):
        video_request = VideoGenerationRequest.objects.create(
            company=item.company, content_calendar_item=item,
            video_type=_pick_video_type(item), prompt_brief=prompt_brief,
        )
        _enqueue_video(video_request)
    else:
        generation_request = GenerationRequest.objects.create(
            company=item.company, content_calendar_item=item,
            creative_type=_pick_creative_type(item), prompt_brief=prompt_brief,
        )
        _enqueue_creative(generation_request)

    item.status = ContentCalendarItem.Status.GENERATING
    item.save(update_fields=['status', 'updated_at'])
    return item


@shared_task
def auto_generate_due_content():
    """Finds every ContentCalendarItem whose scheduled_date has arrived (today or
    earlier, to also sweep up anything a prior run/outage missed) and still hasn't had
    generation started (status is DRAFT or SCHEDULED), and queues it via generate_now()
    - exactly what clicking "Generate now" does by hand. Each item flips to GENERATING
    immediately, so a slow run can't double-queue it and a manually-generated item is
    never touched here.

    Runs every 15 minutes (see CELERY_BEAT_SCHEDULE) rather than once a day, since a
    scheduled_time on today's date needs to actually be honored - a once-daily run can
    only ever be "close enough", firing hours early or a full day late depending on
    whether an item's time falls before or after that one daily slot.
    """
    now = timezone.localtime()
    candidates = ContentCalendarItem.objects.filter(
        scheduled_date__lte=now.date(),
        status__in=[ContentCalendarItem.Status.DRAFT, ContentCalendarItem.Status.SCHEDULED],
    )
    for item in candidates:
        if item.scheduled_date == now.date() and item.scheduled_time and item.scheduled_time > now.time():
            continue  # scheduled later today - not due yet
        generate_now(item)
