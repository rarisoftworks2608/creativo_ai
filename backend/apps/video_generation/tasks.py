from celery import shared_task
from django.core.files.base import ContentFile

from apps.ai_strategy.ai_client import get_provider as get_text_provider
from apps.ai_strategy.models import BrandContext
from apps.brand.models import BrandProfile
from apps.content_calendar.models import ContentCalendarItem
from apps.creative_generation.image_client import get_image_provider
from apps.notifications.models import Notification
from apps.notifications.services import notify_content_ready
from common.ai_errors import AIProviderError

from . import prompts, rendering, subtitles
from .models import VideoGenerationRequest, VideoScene
from .schemas import SCRIPT_SCHEMA
from .voice_client import get_voice_provider

IMAGE_MIME_EXTENSIONS = {'image/png': 'png', 'image/jpeg': 'jpg', 'image/webp': 'webp'}
AUDIO_MIME_EXTENSIONS = {'audio/mpeg': 'mp3', 'audio/wav': 'wav'}


def _fail(request, message):
    request.status = VideoGenerationRequest.Status.FAILED
    request.error_message = message
    request.save(update_fields=['status', 'error_message', 'updated_at'])
    if request.content_calendar_item_id:
        ContentCalendarItem.objects.filter(pk=request.content_calendar_item_id).update(
            status=ContentCalendarItem.Status.FAILED,
        )


@shared_task(bind=True)
def generate_video(self, video_request_id):
    """Generates a script, per-scene visuals, voice-over, subtitles, and a rendered
    video for a VideoGenerationRequest (Epic 07: AI Video Generation)."""
    try:
        request = VideoGenerationRequest.objects.select_related('company', 'content_calendar_item').get(
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

    # 2. Per-scene AI visuals
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

    # 3. Voice-over per scene (gTTS by default - free, no API key required)
    if voice_provider is not None:
        for scene in scenes:
            if not scene.narration.strip():
                continue
            try:
                audio_bytes, mime_type = voice_provider.synthesize_speech(text=scene.narration)
            except AIProviderError as exc:
                _fail(request, f'Voice-over generation failed on scene {scene.scene_number}: {exc}')
                return
            except Exception as exc:  # noqa: BLE001
                _fail(request, f'Unexpected error on scene {scene.scene_number} voice-over: {exc}')
                return
            ext = AUDIO_MIME_EXTENSIONS.get(mime_type, 'mp3')
            scene.voice_over_audio.save(f'scene_{scene.scene_number}.{ext}', ContentFile(audio_bytes), save=False)
            scene.save(update_fields=['voice_over_audio'])

    # 4. Subtitles - pure local generation from the scene timeline, no AI needed
    srt_text = subtitles.build_srt(scenes) if request.subtitles_enabled else ''
    request.subtitles_srt = srt_text
    request.save(update_fields=['subtitles_srt', 'updated_at'])

    # 5. Render
    request.status = VideoGenerationRequest.Status.RENDERING
    request.save(update_fields=['status', 'updated_at'])

    logo_path = None
    if request.include_logo and brand_profile is not None and brand_profile.logo:
        try:
            logo_path = brand_profile.logo.path
        except (ValueError, NotImplementedError):
            logo_path = None

    try:
        video_bytes, thumbnail_bytes, duration, resolution = rendering.render_video(
            scenes=scenes, aspect_ratio=request.aspect_ratio, subtitles_srt=srt_text,
            logo_path=logo_path, include_logo=request.include_logo,
        )
    except AIProviderError as exc:
        _fail(request, str(exc))
        return
    except Exception as exc:  # noqa: BLE001
        _fail(request, f'Unexpected error while rendering the video: {exc}')
        return

    request.video_file.save('final.mp4', ContentFile(video_bytes), save=False)
    request.thumbnail.save('thumbnail.jpg', ContentFile(thumbnail_bytes), save=False)
    request.duration_seconds = duration
    request.resolution = resolution
    request.file_size_bytes = len(video_bytes)
    request.status = VideoGenerationRequest.Status.SUCCEEDED
    request.error_message = ''
    request.model_used = f'{getattr(text_provider, "model", "")} + {getattr(image_provider, "model", "")} + gTTS'
    request.usage = {'scenes_generated': len(scenes)}
    request.save(update_fields=[
        'video_file', 'thumbnail', 'duration_seconds', 'resolution', 'file_size_bytes',
        'status', 'error_message', 'model_used', 'usage', 'updated_at',
    ])
    if request.content_calendar_item_id:
        ContentCalendarItem.objects.filter(pk=request.content_calendar_item_id).update(
            status=ContentCalendarItem.Status.PENDING_APPROVAL,
        )

    is_regeneration = request.retry_count > 0
    notify_content_ready(
        company=company,
        created_by=request.created_by,
        notification_type=(
            Notification.NotificationType.CONTENT_REGENERATED if is_regeneration
            else Notification.NotificationType.CONTENT_GENERATED
        ),
        title=f'{request.get_video_type_display()} {"regenerated" if is_regeneration else "ready"}',
        message=f'A {round(duration)}s video was rendered for {company.name}.',
        url=f'/companies/{company.id}/video-generation',
    )
