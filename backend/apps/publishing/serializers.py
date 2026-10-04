from rest_framework import serializers

from apps.content_calendar.models import ContentCalendarItem

from . import media as media_utils
from .models import PublishJob


class PublishJobSerializer(serializers.ModelSerializer):
    platform_display = serializers.CharField(source='get_platform_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    post_type_display = serializers.CharField(source='get_post_type_display', read_only=True)
    account_name = serializers.SerializerMethodField()
    topic = serializers.SerializerMethodField()
    company_name = serializers.CharField(source='company.name', read_only=True)
    media_preview = serializers.SerializerMethodField()
    can_cancel = serializers.SerializerMethodField()
    can_retry = serializers.SerializerMethodField()

    class Meta:
        model = PublishJob
        fields = [
            'id', 'company', 'company_name', 'content_calendar_item', 'topic', 'social_account', 'account_name',
            'platform', 'platform_display', 'post_type', 'post_type_display', 'caption', 'media', 'media_preview',
            'scheduled_at', 'status', 'status_display', 'attempts', 'max_attempts', 'last_error', 'error_log',
            'external_post_id', 'external_url', 'published_at', 'can_cancel', 'can_retry',
            'created_by', 'created_at', 'updated_at',
        ]
        read_only_fields = fields

    def get_account_name(self, obj) -> str:
        return obj.social_account.account_name if obj.social_account else '(removed account)'

    def get_topic(self, obj) -> str:
        return obj.content_calendar_item.topic if obj.content_calendar_item else ''

    def get_media_preview(self, obj) -> list:
        return media_utils.media_preview(obj.media, self.context.get('request'))

    def get_can_cancel(self, obj) -> bool:
        return obj.status in (PublishJob.Status.SCHEDULED, PublishJob.Status.QUEUED)

    def get_can_retry(self, obj) -> bool:
        return obj.status in (PublishJob.Status.FAILED, PublishJob.Status.CANCELLED)


class PublishJobCreateSerializer(serializers.Serializer):
    content_calendar_item = serializers.PrimaryKeyRelatedField(queryset=ContentCalendarItem.objects.all())
    social_account_ids = serializers.ListField(child=serializers.IntegerField(), allow_empty=False)
    scheduled_at = serializers.DateTimeField(required=False, allow_null=True)
    caption = serializers.CharField(required=False, allow_blank=True)
    post_type = serializers.ChoiceField(choices=PublishJob.PostType.choices, required=False, allow_null=True)


class PublishJobUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = PublishJob
        fields = ['scheduled_at', 'caption']
