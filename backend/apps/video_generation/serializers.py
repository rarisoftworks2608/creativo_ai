from rest_framework import serializers

from .models import BackgroundMusicTrack, VideoGenerationRequest, VideoScene


class VideoSceneSerializer(serializers.ModelSerializer):
    class Meta:
        model = VideoScene
        fields = [
            'id', 'scene_number', 'narration', 'visual_description', 'duration_seconds',
            'image', 'voice_over_audio', 'video_clip', 'created_at',
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
            'voice_over_enabled', 'subtitles_enabled', 'include_logo', 'music_enabled', 'music_track',
            'include_outro', 'ai_motion_enabled',
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
            'ai_motion_enabled', 'music_enabled', 'music_track', 'include_outro',
        ]
        read_only_fields = ['id']

    def validate_music_track(self, track):
        if track is not None and not track.is_active:
            raise serializers.ValidationError('That music track is inactive.')
        return track

    def validate_content_calendar_item(self, item):
        company = self.context['company']
        if item is not None and item.company_id != company.id:
            raise serializers.ValidationError('This content calendar item does not belong to this company.')
        return item

    def validate_target_duration_seconds(self, value):
        if value < 5 or value > 180:
            raise serializers.ValidationError('Target duration must be between 5 and 180 seconds.')
        return value


class VideoSceneUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = VideoScene
        fields = ['narration', 'visual_description', 'duration_seconds']

    def validate_duration_seconds(self, value):
        if not 1 <= value <= 30:
            raise serializers.ValidationError('A scene must be between 1 and 30 seconds.')
        return value


class BackgroundMusicTrackSerializer(serializers.ModelSerializer):
    mood_display = serializers.CharField(source='get_mood_display', read_only=True)

    class Meta:
        model = BackgroundMusicTrack
        fields = ['id', 'name', 'file', 'mood', 'mood_display', 'license_note', 'is_active', 'created_at']
        read_only_fields = ['id', 'created_at']

    def validate_file(self, value):
        name = (value.name or '').lower()
        if not name.endswith(('.mp3', '.m4a', '.aac', '.wav', '.ogg')):
            raise serializers.ValidationError('Upload an MP3, M4A, AAC, WAV or OGG audio file.')
        if value.size > 25 * 1024 * 1024:
            raise serializers.ValidationError('Music files are limited to 25 MB.')
        return value
