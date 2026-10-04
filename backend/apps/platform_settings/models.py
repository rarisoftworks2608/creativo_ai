import datetime

from django.db import models


def _default_publish_time():
    return datetime.time(10, 0)


class PlatformSettings(models.Model):
    """Singleton row of platform-wide, live-editable settings (Epic 19: Admin Settings).

    Secrets (API keys, DB credentials) stay in .env - only operational knobs an
    admin should be able to flip without a code deploy live here. Always use
    `PlatformSettings.load()` rather than querying/creating directly.
    """

    class Language(models.TextChoices):
        """Language AI-written copy (captions, scripts, voice-over) is produced in.
        Every code here is also a gTTS voice language, so voice-over follows it too."""
        ENGLISH = 'en', 'English'
        HINDI = 'hi', 'Hindi'
        MARATHI = 'mr', 'Marathi'
        GUJARATI = 'gu', 'Gujarati'
        TAMIL = 'ta', 'Tamil'
        TELUGU = 'te', 'Telugu'
        KANNADA = 'kn', 'Kannada'
        BENGALI = 'bn', 'Bengali'
        MALAYALAM = 'ml', 'Malayalam'
        SPANISH = 'es', 'Spanish'
        FRENCH = 'fr', 'French'
        GERMAN = 'de', 'German'
        ARABIC = 'ar', 'Arabic'

    send_notification_emails = models.BooleanField(
        default=False, help_text='Mirror in-app notifications as emails (Epic 13).',
    )
    default_variation_count = models.PositiveSmallIntegerField(
        default=3, help_text='Default number of AI variations for a new generation request (1-3).',
    )
    max_variation_count = models.PositiveSmallIntegerField(
        default=3, help_text='Hard ceiling on variations an admin can request at once (1-3).',
    )
    daily_generation_limit_per_company = models.PositiveIntegerField(
        default=0,
        help_text='Max combined creative + video generation requests a company can start per day. 0 = unlimited.',
    )
    max_upload_size_mb = models.PositiveIntegerField(
        default=10, help_text='Max file size for brand asset uploads, in MB.',
    )

    # AI provider / model overrides (Epic 19: AI provider settings, Model settings).
    # Blank = use the .env value (AI_TEXT_PROVIDER, AI_IMAGE_MODEL, ...). API keys
    # themselves always stay in .env - only *which* configured provider is used is
    # switchable here, e.g. Cloudflare -> OpenAI once OPENAI_API_KEY is added.
    ai_text_provider = models.CharField(max_length=30, blank=True)
    ai_text_model = models.CharField(max_length=120, blank=True)
    ai_image_provider = models.CharField(max_length=30, blank=True)
    ai_image_model = models.CharField(max_length=120, blank=True)
    ai_video_provider = models.CharField(max_length=30, blank=True)
    ai_video_model = models.CharField(max_length=120, blank=True)

    # Localization (Epic 19: Timezone, Language)
    default_timezone = models.CharField(
        max_length=64, blank=True,
        help_text='IANA timezone (e.g. Asia/Kolkata) used to interpret calendar dates/times when '
                  'scheduling posts. Blank = the server TIME_ZONE.',
    )
    content_language = models.CharField(
        max_length=5, choices=Language.choices, default=Language.ENGLISH,
        help_text='Language AI-generated captions, scripts and voice-overs are written in.',
    )

    # Publishing (Epic 11 / Epic 19: Publishing settings)
    publishing_enabled = models.BooleanField(
        default=True, help_text='Global kill switch - when off, scheduled posts wait instead of publishing.',
    )
    auto_schedule_on_approval = models.BooleanField(
        default=False,
        help_text='When content is approved, automatically schedule it to every connected account for its '
                  'platforms at the calendar item date/time (Epic 22: Publishing automation).',
    )
    default_publish_time = models.TimeField(
        default=_default_publish_time,
        help_text='Publish time used when a calendar item has a date but no time.',
    )
    publish_max_attempts = models.PositiveSmallIntegerField(
        default=3, help_text='How many times a failed publish is attempted before it is marked failed (1-10).',
    )

    # Approval workflow (Epic 09 / Epic 12: Reminder)
    approval_reminder_hours = models.PositiveIntegerField(
        default=24, help_text='Remind clients about content still pending their approval after this many hours. 0 = off.',
    )

    # Analytics (Epic 15: Synchronization)
    analytics_sync_enabled = models.BooleanField(default=True)
    analytics_sync_interval_hours = models.PositiveSmallIntegerField(
        default=6, help_text='How often published-post metrics are refreshed from the platforms (1-48).',
    )

    # Reports (Epic 16: Automation)
    monthly_reports_enabled = models.BooleanField(
        default=True, help_text='Generate every active company\'s monthly report automatically.',
    )
    report_day_of_month = models.PositiveSmallIntegerField(
        default=1, help_text='Day of the month (1-28) the previous month\'s reports are generated.',
    )
    email_reports_to_clients = models.BooleanField(default=True)
    whatsapp_reports_to_clients = models.BooleanField(default=True)

    # Subscriptions (Epic 17: Usage limits)
    enforce_subscription_limits = models.BooleanField(
        default=False,
        help_text='Block generation/publishing once a company exceeds its plan limits or has no active '
                  'subscription. Off = usage is tracked and shown, but never blocks work.',
    )
    subscription_expiry_reminder_days = models.PositiveSmallIntegerField(
        default=7, help_text='Notify admins this many days before a subscription expires.',
    )

    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(
        'authentication.User', null=True, blank=True, on_delete=models.SET_NULL, related_name='+',
    )

    class Meta:
        verbose_name = 'Platform settings'
        verbose_name_plural = 'Platform settings'

    def __str__(self):
        return 'Platform Settings'

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def load(cls):
        """Get-or-create the singleton. On first creation only, seeds
        `send_notification_emails` from the SEND_NOTIFICATION_EMAILS env setting
        so existing deployments (and tests using @override_settings on it) keep
        behaving the same until an admin explicitly changes it here.
        """
        from django.conf import settings as django_settings

        obj, created = cls.objects.get_or_create(
            pk=1, defaults={'send_notification_emails': django_settings.SEND_NOTIFICATION_EMAILS},
        )
        return obj

    @property
    def timezone_name(self):
        from django.conf import settings as django_settings

        return self.default_timezone or django_settings.TIME_ZONE
