from django.apps import AppConfig


class PlatformSettingsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.platform_settings'
    label = 'platform_settings'
    verbose_name = 'Admin Settings'
