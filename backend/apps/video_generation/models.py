from django.conf import settings
from django.db import models

from apps.companies.models import Company
from apps.content_calendar.models import ContentCalendarItem
from common.models import TimeStampedModel


def video_upload_path(instance, filename):
    return f'video_generation/{instance.company_id}/{instance.id}/{filename}'


def scene_image_upload_path(instance, filename):
    request = instance.video_request
    return f'video_generation/{request.company_id}/{request.id}/scenes/{filename}'


def scene_audio_upload_path(instance, filename):
    request = instance.video_request
    return f'video_generation/{request.company_id}/{request.id}/audio/{filename}'


def scene_video_clip_upload_path(instance, filename):
    request = instance.video_request
    return f'video_generation/{request.company_id}/{request.id}/clips/{filename}'


class VideoGenerationRequest(TimeStampedModel):
    """A single request to generate an AI video (Epic 07: AI Video Generation).

    Unlike image creative generation (Epic 06), which produces 3 selectable
    variations, one request here produces exactly one final rendered video -
    per-scene AI visuals, voice-over and rendering are all too costly/slow
    to triple, so a user unhappy with the result retries instead.
    """

    class VideoType(models.TextChoices):
        INSTAGRAM_REEL = 'instagram_reel', 'Instagram Reel'
        FACEBOOK_REEL = 'facebook_reel', 'Facebook Reel'
        LINKEDIN_VIDEO = 'linkedin_video', 'LinkedIn Video'
        SHORT_VIDEO = 'short_video', 'Short Video'
        PROMOTIONAL_VIDEO = 'promotional_video', 'Promotional Video'
        PRODUCT_VIDEO = 'product_video', 'Product Video'
        EDUCATIONAL_VIDEO = 'educational_video', 'Educational Video'

    class AspectRatio(models.TextChoices):
        VERTICAL = '9:16', 'Vertical (9:16)'
        SQUARE = '1:1', 'Square (1:1)'
        LANDSCAPE = '16:9', 'Landscape (16:9)'

    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        QUEUED = 'queued', 'Queued'
        PROCESSING = 'processing', 'Processing'
        RENDERING = 'rendering', 'Rendering'
        SUCCEEDED = 'succeeded', 'Succeeded'
        FAILED = 'failed', 'Failed'

    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='video_generation_requests')
    content_calendar_item = models.ForeignKey(
        ContentCalendarItem, null=True, blank=True, on_delete=models.SET_NULL,
        related_name='video_generation_requests',
    )

    video_type = models.CharField(max_length=30, choices=VideoType.choices)
    aspect_ratio = models.CharField(max_length=10, choices=AspectRatio.choices, default=AspectRatio.VERTICAL)
    target_duration_seconds = models.PositiveIntegerField(default=30)

    prompt_brief = models.TextField(blank=True, help_text='What the video should be about.')
    product_info = models.TextField(blank=True, help_text='Product information to ground the script.')

    voice_over_enabled = models.BooleanField(default=True)
    subtitles_enabled = models.BooleanField(default=True)
    include_logo = models.BooleanField(default=True)
    music_enabled = models.BooleanField(
        default=False,
        help_text='Background music mixing has no configured provider yet - left off by default.',
    )
    ai_motion_enabled = models.BooleanField(
        default=True,
        help_text=(
            'Animate each scene image into a short AI-generated video clip instead of a '
            'static zoom/pan. Falls back to zoom/pan automatically if no video provider '
            'is configured (REPLICATE_API_TOKEN unset).'
        ),
    )

    script = models.TextField(blank=True, help_text='Full narration script, assembled from all scenes.')
    subtitles_srt = models.TextField(blank=True)

    status = models.CharField(max_length=15, choices=Status.choices, default=Status.PENDING)
    error_message = models.TextField(blank=True)
    retry_count = models.PositiveIntegerField(default=0)
    celery_task_id = models.CharField(max_length=255, blank=True)

    model_used = models.CharField(max_length=100, blank=True)
    usage = models.JSONField(default=dict, blank=True)
    cost_usd = models.DecimalField(max_digits=10, decimal_places=4, null=True, blank=True)

    video_file = models.FileField(upload_to=video_upload_path, blank=True, null=True)
    thumbnail = models.ImageField(upload_to=video_upload_path, blank=True, null=True)
    resolution = models.CharField(max_length=20, blank=True, help_text='e.g. "1080x1920".')
    duration_seconds = models.FloatField(null=True, blank=True)
    file_size_bytes = models.PositiveBigIntegerField(null=True, blank=True)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='+',
    )

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.get_video_type_display()} for {self.company.name} ({self.status})'


class VideoScene(TimeStampedModel):
    """One scene/shot in a video's storyboard (Epic 07: Video Components)."""

    video_request = models.ForeignKey(VideoGenerationRequest, on_delete=models.CASCADE, related_name='scenes')
    scene_number = models.PositiveSmallIntegerField()

    narration = models.TextField(blank=True, help_text='The voice-over line for this scene.')
    visual_description = models.TextField(blank=True, help_text='What should be shown on screen.')
    duration_seconds = models.FloatField(default=4.0)

    image = models.ImageField(upload_to=scene_image_upload_path, blank=True, null=True)
    voice_over_audio = models.FileField(upload_to=scene_audio_upload_path, blank=True, null=True)
    video_clip = models.FileField(
        upload_to=scene_video_clip_upload_path, blank=True, null=True,
        help_text='AI-animated version of `image`, if AI motion was enabled and available.',
    )

    class Meta:
        ordering = ['scene_number']
        unique_together = [['video_request', 'scene_number']]

    def __str__(self):
        return f'Scene {self.scene_number} of request {self.video_request_id}'
