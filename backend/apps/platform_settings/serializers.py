from django.conf import settings
from rest_framework import serializers

from .models import PlatformSettings


class PlatformSettingsSerializer(serializers.ModelSerializer):
    """Live-editable settings plus a read-only snapshot of the .env-controlled
    values (AI provider/model, timezone) so the admin can see the full picture
    in one place, even though changing those still requires editing .env and
    restarting the server.
    """

    environment = serializers.SerializerMethodField()

    class Meta:
        model = PlatformSettings
        fields = [
            'send_notification_emails', 'default_variation_count', 'max_variation_count',
            'daily_generation_limit_per_company', 'max_upload_size_mb', 'updated_at', 'environment',
        ]
        read_only_fields = ['updated_at']

    def get_environment(self, obj):
        return {
            'ai_text_provider': settings.AI_TEXT_PROVIDER,
            'ai_text_model': settings.AI_TEXT_MODEL,
            'ai_image_provider': settings.AI_IMAGE_PROVIDER,
            'ai_image_model': settings.AI_IMAGE_MODEL,
            'ai_video_provider': settings.AI_VIDEO_PROVIDER,
            'ai_video_model': settings.AI_VIDEO_MODEL,
            'time_zone': settings.TIME_ZONE,
        }

    def validate(self, attrs):
        min_v = attrs.get('default_variation_count', getattr(self.instance, 'default_variation_count', 1))
        max_v = attrs.get('max_variation_count', getattr(self.instance, 'max_variation_count', 3))
        if not (1 <= min_v <= 3) or not (1 <= max_v <= 3):
            raise serializers.ValidationError('Variation counts must be between 1 and 3.')
        if min_v > max_v:
            raise serializers.ValidationError('Default variation count cannot exceed the max variation count.')
        return attrs
