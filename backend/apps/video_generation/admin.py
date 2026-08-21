from django.contrib import admin

from .models import VideoGenerationRequest, VideoScene


class VideoSceneInline(admin.TabularInline):
    model = VideoScene
    extra = 0
    readonly_fields = [
        'scene_number', 'narration', 'visual_description', 'duration_seconds',
        'image', 'voice_over_audio', 'created_at',
    ]


@admin.register(VideoGenerationRequest)
class VideoGenerationRequestAdmin(admin.ModelAdmin):
    list_display = ['company', 'video_type', 'status', 'retry_count', 'duration_seconds', 'model_used', 'created_at']
    list_filter = ['status', 'video_type', 'aspect_ratio']
    search_fields = ['company__name']
    autocomplete_fields = ['company', 'content_calendar_item']
    readonly_fields = ['created_at', 'updated_at', 'celery_task_id']
    inlines = [VideoSceneInline]
