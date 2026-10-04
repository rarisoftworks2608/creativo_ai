from rest_framework import serializers

from .models import ContentCalendarItem, ContentReviewEvent


class ContentCalendarItemSerializer(serializers.ModelSerializer):
    """`latest_generation_request`/`latest_video_request` let the client dashboard
    render the actual generated creative/video for a pending item in the same
    request that lists it (Epic 09), instead of a separate lookup per item.
    Imported locally to avoid a circular import: creative_generation and
    video_generation both import ContentCalendarItem themselves.
    """

    latest_generation_request = serializers.SerializerMethodField()
    latest_video_request = serializers.SerializerMethodField()
    publish_jobs = serializers.SerializerMethodField()
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = ContentCalendarItem
        fields = [
            'id', 'company', 'topic', 'category', 'weekly_theme', 'content_type', 'platforms',
            'objective', 'campaign', 'scheduled_date', 'scheduled_time',
            'caption_requirements', 'creative_requirements', 'cta', 'hashtags', 'source_notes',
            'status', 'status_display', 'source', 'client_feedback', 'regeneration_count',
            'created_by', 'created_at', 'updated_at',
            'latest_generation_request', 'latest_video_request', 'publish_jobs',
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

    def get_publish_jobs(self, obj) -> list:
        """Compact per-platform publishing status (Epic 11: client can view publishing
        status) - the full job lives in the publishing app's own endpoints."""
        return [
            {
                'id': job.id, 'platform': job.platform, 'status': job.status,
                'scheduled_at': job.scheduled_at, 'published_at': job.published_at,
                'external_url': job.external_url,
            }
            for job in obj.publish_jobs.all()
        ]

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


class ContentReviewEventSerializer(serializers.ModelSerializer):
    action_display = serializers.CharField(source='get_action_display', read_only=True)
    actor_name = serializers.SerializerMethodField()

    class Meta:
        model = ContentReviewEvent
        fields = ['id', 'action', 'action_display', 'actor', 'actor_name', 'actor_role', 'feedback', 'metadata', 'created_at']
        read_only_fields = fields

    def get_actor_name(self, obj) -> str:
        return obj.actor.get_full_name() if obj.actor else 'System'


class ApprovalQueueItemSerializer(ContentCalendarItemSerializer):
    """A calendar item as shown in the admin's cross-company approval queue."""

    company_name = serializers.CharField(source='company.name', read_only=True)
    pending_since = serializers.SerializerMethodField()

    class Meta(ContentCalendarItemSerializer.Meta):
        fields = [*ContentCalendarItemSerializer.Meta.fields, 'company_name', 'pending_since']

    def get_pending_since(self, obj) -> str | None:
        from .services import pending_since

        return pending_since(obj)
