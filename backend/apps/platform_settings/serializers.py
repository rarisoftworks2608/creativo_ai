from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django.conf import settings
from rest_framework import serializers

from common.ai_config import DEFAULT_MODELS, PROVIDER_CREDENTIALS, credentials_status, get_model_name, get_provider_name

from .models import PlatformSettings


class PlatformSettingsSerializer(serializers.ModelSerializer):
    """Live-editable settings plus a read-only snapshot of the .env-controlled values
    (which providers have credentials, OAuth/WhatsApp/storage configuration, timezone)
    so the admin sees the full picture in one place. Secrets are never returned - only
    whether each one is set.
    """

    environment = serializers.SerializerMethodField()
    content_language_display = serializers.CharField(source='get_content_language_display', read_only=True)

    class Meta:
        model = PlatformSettings
        fields = [
            'send_notification_emails', 'default_variation_count', 'max_variation_count',
            'daily_generation_limit_per_company', 'max_upload_size_mb',
            'ai_text_provider', 'ai_text_model', 'ai_image_provider', 'ai_image_model',
            'ai_video_provider', 'ai_video_model',
            'default_timezone', 'content_language', 'content_language_display',
            'publishing_enabled', 'auto_schedule_on_approval', 'default_publish_time', 'publish_max_attempts',
            'approval_reminder_hours',
            'analytics_sync_enabled', 'analytics_sync_interval_hours',
            'monthly_reports_enabled', 'report_day_of_month', 'email_reports_to_clients', 'whatsapp_reports_to_clients',
            'enforce_subscription_limits', 'subscription_expiry_reminder_days',
            'updated_at', 'environment',
        ]
        read_only_fields = ['updated_at']

    def get_environment(self, obj):
        from apps.social_accounts.oauth import provider_status
        from apps.whatsapp.providers import get_provider as get_whatsapp_provider

        whatsapp = get_whatsapp_provider()
        return {
            # Effective values (override if set, else .env) - what generation actually uses now.
            'ai_text_provider': get_provider_name('text'),
            'ai_text_model': get_model_name('text'),
            'ai_image_provider': get_provider_name('image'),
            'ai_image_model': get_model_name('image'),
            'ai_video_provider': get_provider_name('video'),
            'ai_video_model': get_model_name('video'),
            'env_defaults': {
                'ai_text_provider': settings.AI_TEXT_PROVIDER, 'ai_text_model': settings.AI_TEXT_MODEL,
                'ai_image_provider': settings.AI_IMAGE_PROVIDER, 'ai_image_model': settings.AI_IMAGE_MODEL,
                'ai_video_provider': settings.AI_VIDEO_PROVIDER, 'ai_video_model': settings.AI_VIDEO_MODEL,
            },
            'provider_options': {kind: sorted(providers) for kind, providers in PROVIDER_CREDENTIALS.items()},
            'default_models': {f'{kind}:{provider}': model for (kind, provider), model in DEFAULT_MODELS.items()},
            'credentials': credentials_status(),
            'time_zone': settings.TIME_ZONE,
            'effective_timezone': obj.timezone_name,
            'social_oauth': provider_status(),
            'whatsapp': {'provider': whatsapp.name, 'configured': whatsapp.is_configured()},
            'storage_backend': 's3' if getattr(settings, 'USE_S3_STORAGE', False) else 'local',
            'public_media_base_url': settings.PUBLIC_MEDIA_BASE_URL,
            'backend_public_url': settings.BACKEND_PUBLIC_URL,
            'email_backend': settings.EMAIL_BACKEND.rsplit('.', 1)[-1],
        }

    def validate(self, attrs):
        min_v = attrs.get('default_variation_count', getattr(self.instance, 'default_variation_count', 1))
        max_v = attrs.get('max_variation_count', getattr(self.instance, 'max_variation_count', 3))
        if not (1 <= min_v <= 3) or not (1 <= max_v <= 3):
            raise serializers.ValidationError('Variation counts must be between 1 and 3.')
        if min_v > max_v:
            raise serializers.ValidationError('Default variation count cannot exceed the max variation count.')

        for kind in ('text', 'image', 'video'):
            provider = attrs.get(f'ai_{kind}_provider')
            if provider and provider not in PROVIDER_CREDENTIALS[kind]:
                raise serializers.ValidationError(
                    {f'ai_{kind}_provider': f'Choose one of: {", ".join(sorted(PROVIDER_CREDENTIALS[kind]))}.'}
                )

        timezone_name = attrs.get('default_timezone')
        if timezone_name:
            try:
                ZoneInfo(timezone_name)
            except (ZoneInfoNotFoundError, ValueError):
                raise serializers.ValidationError({'default_timezone': 'Unknown timezone - use an IANA name like Asia/Kolkata.'})

        ranges = {
            'publish_max_attempts': (1, 10), 'analytics_sync_interval_hours': (1, 48),
            'report_day_of_month': (1, 28), 'approval_reminder_hours': (0, 720),
            'subscription_expiry_reminder_days': (0, 90), 'max_upload_size_mb': (1, 500),
        }
        for field, (low, high) in ranges.items():
            if field in attrs and not low <= attrs[field] <= high:
                raise serializers.ValidationError({field: f'Must be between {low} and {high}.'})
        return attrs
