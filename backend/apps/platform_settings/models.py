from django.db import models


class PlatformSettings(models.Model):
    """Singleton row of platform-wide, live-editable settings (Epic 19: Admin Settings).

    Secrets (API keys, DB credentials) stay in .env - only operational knobs an
    admin should be able to flip without a code deploy live here. Always use
    `PlatformSettings.load()` rather than querying/creating directly.
    """

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
