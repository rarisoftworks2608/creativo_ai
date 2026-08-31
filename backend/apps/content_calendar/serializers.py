from rest_framework import serializers

from .models import ContentCalendarItem


class ContentCalendarItemSerializer(serializers.ModelSerializer):
    """`latest_generation_request`/`latest_video_request` let the client dashboard
    render the actual generated creative/video for a pending item in the same
    request that lists it (Epic 09), instead of a separate lookup per item.
    Imported locally to avoid a circular import: creative_generation and
    video_generation both import ContentCalendarItem themselves.
    """

    latest_generation_request = serializers.SerializerMethodField()
    latest_video_request = serializers.SerializerMethodField()

    class Meta:
        model = ContentCalendarItem
        fields = [
            'id', 'company', 'topic', 'category', 'weekly_theme', 'content_type', 'platforms',
            'objective', 'campaign', 'scheduled_date', 'scheduled_time',
            'caption_requirements', 'creative_requirements', 'cta', 'hashtags', 'source_notes',
            'status', 'source', 'client_feedback', 'regeneration_count', 'created_by', 'created_at', 'updated_at',
            'latest_generation_request', 'latest_video_request',
        ]
        read_only_fields = [
            'id', 'company', 'source', 'client_feedback', 'regeneration_count', 'created_by', 'created_at', 'updated_at',
        ]

    def get_latest_generation_request(self, obj):
        from apps.creative_generation.serializers import GenerationRequestSerializer

        generation_request = obj.generation_requests.order_by('-created_at').first()
        if not generation_request:
            return None
        return GenerationRequestSerializer(generation_request, context=self.context).data

    def get_latest_video_request(self, obj):
        from apps.video_generation.serializers import VideoGenerationRequestSerializer

        video_request = obj.video_generation_requests.order_by('-created_at').first()
        if not video_request:
            return None
        return VideoGenerationRequestSerializer(video_request, context=self.context).data

    def validate_platforms(self, value):
        valid = {choice for choice, _label in ContentCalendarItem.Platform.choices}
        if not isinstance(value, list) or not value:
            raise serializers.ValidationError('Select at least one platform.')
        invalid = [v for v in value if v not in valid]
        if invalid:
            raise serializers.ValidationError(f'Invalid platform(s): {", ".join(invalid)}')
        return value

    def validate_hashtags(self, value):
        if value in (None, ''):
            return []
        if not isinstance(value, list):
            raise serializers.ValidationError('Hashtags must be a list of strings.')
        return value


class ExcelUploadSerializer(serializers.Serializer):
    file = serializers.FileField()
