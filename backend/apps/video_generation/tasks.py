import random

from celery import shared_task
from django.core.files.base import ContentFile

from apps.ai_strategy.ai_client import get_provider as get_text_provider
from apps.ai_strategy.models import BrandContext
from apps.brand.models import BrandProfile
from apps.content_calendar import services as review_services
from apps.content_calendar.models import ContentCalendarItem
from apps.creative_generation.image_client import get_image_provider
from apps.notifications.models import Notification
from apps.notifications.services import notify_content_ready
from common.ai_errors import AIProviderError

from . import prompts, rendering, subtitles
from .models import BackgroundMusicTrack, VideoGenerationRequest, VideoScene
from .schemas import SCRIPT_SCHEMA
from .video_client import get_video_provider
from .voice_client import get_voice_provider

IMAGE_MIME_EXTENSIONS = {'image/png': 'png', 'image/jpeg': 'jpg', 'image/webp': 'webp'}
AUDIO_MIME_EXTENSIONS = {'audio/mpeg': 'mp3', 'audio/wav': 'wav'}
VIDEO_MIME_EXTENSIONS = {'video/mp4': 'mp4'}


def _fail(request, message):
    request.status = VideoGenerationRequest.Status.FAILED
    request.error_message = message
    request.save(update_fields=['status', 'error_message', 'updated_at'])
    if request.content_calendar_item_id:
        ContentCalendarItem.objects.filter(pk=request.content_calendar_item_id).update(
            status=ContentCalendarItem.Status.FAILED,
        )
        review_services.generation_failed(
            request.content_calendar_item_id, message, kind='video', request_id=request.id,
        )


def _synthesize_voice(request, scenes, voice_provider):
    """Voice-over per scene (gTTS by default - free, no API key). Returns an error
    message, or '' on success."""
    for scene in scenes:
        if not scene.narration.strip():
            continue
        try:
            audio_bytes, mime_type = voice_provider.synthesize_speech(text=scene.narration)
        except AIProviderError as exc:
            return f'Voice-over generation failed on scene {scene.scene_number}: {exc}'
        except Exception as exc:  # noqa: BLE001
            return f'Unexpected error on scene {scene.scene_number} voice-over: {exc}'
        if scene.voice_over_audio:
            scene.voice_over_audio.delete(save=False)
        ext = AUDIO_MIME_EXTENSIONS.get(mime_type, 'mp3')
        scene.voice_over_audio.save(f'scene_{scene.scene_number}.{ext}', ContentFile(audio_bytes), save=False)
        scene.save(update_fields=['voice_over_audio'])
    return ''


def _pick_music(request):
    if not request.music_enabled:
        return None
    if request.music_track and request.music_track.is_active and request.music_track.file:
        return request.music_track
    tracks = list(BackgroundMusicTrack.objects.filter(is_active=True).exclude(file=''))
    return random.choice(tracks) if tracks else None


def _outro_for(request, brand_profile):
    """Brand end card content: brand colour, logo, company name, CTA (or website/phone)."""
    if not request.include_outro:
        return None
    company = request.company
    colors = list(getattr(brand_profile, 'brand_colors', None) or [])
    color = (colors[0] or {}).get('hex') if colors else ''
    item = request.content_calendar_item
    subtitle = (item.cta if item and item.cta else '') or company.website or company.contact_phone
    return {
        'color': color or '#1f1a2e',
        'title': company.name,
        'subtitle': subtitle,
        'logo_path': brand_profile.logo if brand_profile is not None and brand_profile.logo else None,
    }


def _render_and_save(request, scenes, brand_profile):
    """Subtitles + render + save outputs. Returns an error message, or '' on success."""
    srt_text = subtitles.build_srt(scenes) if request.subtitles_enabled else ''
    request.subtitles_srt = srt_text
    request.status = VideoGenerationRequest.Status.RENDERING
    request.save(update_fields=['subtitles_srt', 'status', 'updated_at'])

    logo = brand_profile.logo if request.include_logo and brand_profile is not None and brand_profile.logo else None
    music = _pick_music(request)
    try:
        video_bytes, thumbnail_bytes, duration, resolution = rendering.render_video(
            scenes=scenes, aspect_ratio=request.aspect_ratio, subtitles_srt=srt_text,
            logo_path=logo, include_logo=request.include_logo,
            music_field=music.file if music else None,
            outro=_outro_for(request, brand_profile),
        )
    except AIProviderError as exc:
        return str(exc)
    except Exception as exc:  # noqa: BLE001
        return f'Unexpected error while rendering the video: {exc}'

    for field in (request.video_file, request.thumbnail):
        if field:
            field.delete(save=False)
    request.video_file.save('final.mp4', ContentFile(video_bytes), save=False)
    request.thumbnail.save('thumbnail.jpg', ContentFile(thumbnail_bytes), save=False)
    request.duration_seconds = duration
    request.resolution = resolution
    request.file_size_bytes = len(video_bytes)
    request.usage = {**(request.usage or {}), 'music_track': music.name if music else None,
                     'outro': bool(request.include_outro)}
    return ''


def _finish(request, scenes, *, is_rerender=False):
    request.status = VideoGenerationRequest.Status.SUCCEEDED
    request.error_message = ''
    request.save(update_fields=[
        'video_file', 'thumbnail', 'duration_seconds', 'resolution', 'file_size_bytes',
        'status', 'error_message', 'model_used', 'usage', 'updated_at',
    ])

    calendar_item = None
    if request.content_calendar_item_id:
        ContentCalendarItem.objects.filter(pk=request.content_calendar_item_id).update(
            status=ContentCalendarItem.Status.PENDING_APPROVAL,
        )
        calendar_item = ContentCalendarItem.objects.filter(pk=request.content_calendar_item_id).first()

    is_regeneration = is_rerender or request.retry_count > 0 or bool(calendar_item and calendar_item.regeneration_count > 0)
    if calendar_item is not None:
        review_services.submitted_for_review(
            calendar_item.id, is_regeneration=is_regeneration, kind='video', request_id=request.id,
        )

    notify_content_ready(
        company=request.company,
        created_by=request.created_by,
        notification_type=(
            Notification.NotificationType.CONTENT_REGENERATED if is_regeneration
            else Notification.NotificationType.CONTENT_GENERATED
        ),
        title=f'{request.get_video_type_display()} {"regenerated" if is_regeneration else "ready"}',
        message=f'A {round(request.duration_seconds or 0)}s video was rendered for {request.company.name}.',
        url=f'/companies/{request.company_id}/video-generation',
    )


@shared_task(bind=True)
def generate_video(self, video_request_id):
    """Generates a script, per-scene visuals, voice-over, subtitles, and a rendered
    video for a VideoGenerationRequest (Epic 07: AI Video Generation)."""
    try:
        request = VideoGenerationRequest.objects.select_related('company', 'content_calendar_item', 'music_track').get(
            pk=video_request_id,
        )
    except VideoGenerationRequest.DoesNotExist:
        return

    request.status = VideoGenerationRequest.Status.PROCESSING
    request.celery_task_id = self.request.id or ''
    request.save(update_fields=['status', 'celery_task_id', 'updated_at'])
    if request.content_calendar_item_id:
        ContentCalendarItem.objects.filter(pk=request.content_calendar_item_id).update(
            status=ContentCalendarItem.Status.GENERATING,
        )

    company = request.company
    brand_profile = BrandProfile.objects.filter(company=company).first()
    brand_context = BrandContext.objects.filter(company=company).first()

    # Resolve every provider this request will need up front, so a missing
    # API key fails fast instead of burning calls on earlier stages first.
    try:
        text_provider = get_text_provider()
        image_provider = get_image_provider()
        voice_provider = get_voice_provider() if request.voice_over_enabled else None
    except AIProviderError as exc:
        _fail(request, str(exc))
        return

    # 1. Script + scene breakdown
    script_prompt = prompts.build_script_prompt(
        company, brand_profile, brand_context, request.video_type,
        request.prompt_brief, request.product_info, request.target_duration_seconds,
    )
    try:
        script_data = text_provider.generate_json(
            system=prompts.SCRIPT_SYSTEM_PROMPT, prompt=script_prompt, json_schema=SCRIPT_SCHEMA,
        )
    except AIProviderError as exc:
        _fail(request, f'Script generation failed: {exc}')
        return
    except Exception as exc:  # noqa: BLE001 - guarantee the request never gets stuck "processing"
        _fail(request, f'Unexpected error generating the script: {exc}')
        return

    scene_data = script_data.get('scenes') or []
    if not scene_data:
        _fail(request, 'The AI provider returned no scenes for this script.')
        return

    request.scenes.all().delete()
    request.script = '\n\n'.join(s.get('narration', '') for s in scene_data)
    request.save(update_fields=['script', 'updated_at'])

    scenes = []
    for index, scene_info in enumerate(scene_data, start=1):
        try:
            duration = max(float(scene_info.get('duration_seconds') or 4.0), 1.0)
        except (TypeError, ValueError):
            duration = 4.0
        scenes.append(VideoScene.objects.create(
            video_request=request,
            scene_number=index,
            narration=scene_info.get('narration', ''),
            visual_description=scene_info.get('visual_description', ''),
            duration_seconds=duration,
        ))

    # 2. Per-scene AI visuals, then (optionally) AI motion animating each still into a clip
    video_provider = get_video_provider() if request.ai_motion_enabled else None
    ai_motion_available = video_provider is not None

    for scene in scenes:
        image_prompt = prompts.build_scene_image_prompt(
            company, brand_profile, request.video_type, scene.visual_description,
        )
        try:
            image_bytes, mime_type = image_provider.generate_image(prompt=image_prompt)
        except AIProviderError as exc:
            _fail(request, f'Visual generation failed on scene {scene.scene_number}: {exc}')
            return
        except Exception as exc:  # noqa: BLE001
            _fail(request, f'Unexpected error on scene {scene.scene_number} visual: {exc}')
            return
        ext = IMAGE_MIME_EXTENSIONS.get(mime_type, 'png')
        scene.image.save(f'scene_{scene.scene_number}.{ext}', ContentFile(image_bytes), save=False)
        scene.save(update_fields=['image'])

        if ai_motion_available:
            motion_prompt = prompts.build_scene_motion_prompt(request.video_type, scene.visual_description)
            try:
                clip_bytes, clip_mime = video_provider.generate_video_clip(
                    image_bytes=image_bytes, mime_type=mime_type, prompt=motion_prompt,
                )
            except AIProviderError:
                # Not configured, rate-limited, free-tier credit exhausted, ... - AI
                # motion is an enhancement layer on top of the still image, not
                # something the video needs to exist at all, so any provider failure
                # just falls back to the zoom/pan animation for this and every
                # remaining scene instead of failing the whole request.
                ai_motion_available = False
            except Exception as exc:  # noqa: BLE001
                _fail(request, f'Unexpected error on scene {scene.scene_number} motion: {exc}')
                return
            else:
                clip_ext = VIDEO_MIME_EXTENSIONS.get(clip_mime, 'mp4')
                scene.video_clip.save(f'scene_{scene.scene_number}_clip.{clip_ext}', ContentFile(clip_bytes), save=False)
                scene.save(update_fields=['video_clip'])

    # 3. Voice-over per scene
    if voice_provider is not None:
        error = _synthesize_voice(request, scenes, voice_provider)
        if error:
            _fail(request, error)
            return

    # 4-5. Subtitles (pure local, from the scene timeline) + render
    error = _render_and_save(request, scenes, brand_profile)
    if error:
        _fail(request, error)
        return

    model_parts = [getattr(text_provider, 'model', ''), getattr(image_provider, 'model', ''), 'gTTS']
    if ai_motion_available:
        model_parts.append(getattr(video_provider, 'model', ''))
    request.model_used = ' + '.join(p for p in model_parts if p)
    request.usage = {**(request.usage or {}), 'scenes_generated': len(scenes), 'ai_motion_used': ai_motion_available}
    _finish(request, scenes)


@shared_task(bind=True)
def rerender_video(self, video_request_id):
    """Re-renders an existing video from its (possibly edited) scenes without
    regenerating the script or visuals (Epic 07: Script/Scenes editing) - voice-over is
    re-synthesized so edited narration is spoken, then subtitles + render run again."""
    request = VideoGenerationRequest.objects.select_related('company', 'content_calendar_item', 'music_track').filter(
        pk=video_request_id,
    ).first()
    if request is None:
        return
    request.status = VideoGenerationRequest.Status.PROCESSING
    request.celery_task_id = self.request.id or ''
    request.error_message = ''
    request.save(update_fields=['status', 'celery_task_id', 'error_message', 'updated_at'])

    scenes = list(request.scenes.order_by('scene_number'))
    if not scenes or not all(scene.image or scene.video_clip for scene in scenes):
        _fail(request, 'Every scene needs a visual before the video can be re-rendered.')
        return
    request.script = '\n\n'.join(scene.narration for scene in scenes)
    request.save(update_fields=['script', 'updated_at'])

    if request.voice_over_enabled:
        try:
            voice_provider = get_voice_provider()
        except AIProviderError as exc:
            _fail(request, str(exc))
            return
        error = _synthesize_voice(request, scenes, voice_provider)
        if error:
            _fail(request, error)
            return
    else:
        for scene in scenes:
            if scene.voice_over_audio:
                scene.voice_over_audio.delete(save=False)
                scene.save(update_fields=['voice_over_audio'])

    brand_profile = BrandProfile.objects.filter(company=request.company).first()
    error = _render_and_save(request, scenes, brand_profile)
    if error:
        _fail(request, error)
        return
    request.usage = {**(request.usage or {}), 'rerendered': True}
    _finish(request, scenes, is_rerender=True)


@shared_task
def regenerate_scene_image(scene_id):
    """Generates a fresh visual for one scene (e.g. after its description was edited).
    The AI motion clip is dropped, since it animated the old image."""
    scene = VideoScene.objects.select_related('video_request__company').filter(pk=scene_id).first()
    if scene is None:
        return None
    request = scene.video_request
    brand_profile = BrandProfile.objects.filter(company=request.company).first()
    image_provider = get_image_provider()
    prompt = prompts.build_scene_image_prompt(request.company, brand_profile, request.video_type, scene.visual_description)
    image_bytes, mime_type = image_provider.generate_image(prompt=prompt)
    for field in (scene.image, scene.video_clip):
        if field:
            field.delete(save=False)
    ext = IMAGE_MIME_EXTENSIONS.get(mime_type, 'png')
    scene.image.save(f'scene_{scene.scene_number}_v2.{ext}', ContentFile(image_bytes), save=False)
    scene.video_clip = None
    scene.save(update_fields=['image', 'video_clip'])
    return scene.id
