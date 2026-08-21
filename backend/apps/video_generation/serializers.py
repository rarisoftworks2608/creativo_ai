from rest_framework import serializers

from .models import VideoGenerationRequest, VideoScene


class VideoSceneSerializer(serializers.ModelSerializer):
    class Meta:
        model = VideoScene
        fields = [
            'id', 'scene_number', 'narration', 'visual_description', 'duration_seconds',
            'image', 'voice_over_audio', 'created_at',
        ]
        read_only_fields = fields


class VideoGenerationRequestSerializer(serializers.ModelSerializer):
    video_type_display = serializers.CharField(source='get_video_type_display', read_only=True)
    scenes = VideoSceneSerializer(many=True, read_only=True)

    class Meta:
        model = VideoGenerationRequest
        fields = [
            'id', 'company', 'content_calendar_item', 'video_type', 'video_type_display',
            'aspect_ratio', 'target_duration_seconds', 'prompt_brief', 'product_info',
            'voice_over_enabled', 'subtitles_enabled', 'include_logo', 'music_enabled',
            'script', 'subtitles_srt', 'status', 'error_message', 'retry_count',
            'model_used', 'usage', 'cost_usd',
            'video_file', 'thumbnail', 'resolution', 'duration_seconds', 'file_size_bytes',
            'created_by', 'created_at', 'updated_at', 'scenes',
        ]
        read_only_fields = fields


class VideoGenerationRequestCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = VideoGenerationRequest
        fields = [
            'id', 'content_calendar_item', 'video_type', 'aspect_ratio', 'target_duration_seconds',
            'prompt_brief', 'product_info', 'voice_over_enabled', 'subtitles_enabled', 'include_logo',
        ]
        read_only_fields = ['id']

    def validate_content_calendar_item(self, item):
        company = self.context['company']
        if item is not None and item.company_id != company.id:
            raise serializers.ValidationError('This content calendar item does not belong to this company.')
        return item

    def validate_target_duration_seconds(self, value):
        if value < 5 or value > 180:
            raise serializers.ValidationError('Target duration must be between 5 and 180 seconds.')
        return value
