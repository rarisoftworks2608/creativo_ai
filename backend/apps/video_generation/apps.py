from django.apps import AppConfig


class VideoGenerationConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.video_generation'
    label = 'video_generation'
    verbose_name = 'AI Video Generation'
