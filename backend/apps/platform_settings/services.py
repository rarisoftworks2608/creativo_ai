from django.utils import timezone
from rest_framework.exceptions import Throttled

from .models import PlatformSettings


def check_daily_generation_limit(company):
    """Raises if `company` has already hit its daily creative+video generation
    cap (Epic 19: Generation limits). A limit of 0 means unlimited - the default,
    so this is a no-op until an admin actually sets one.
    """
    limit = PlatformSettings.load().daily_generation_limit_per_company
    if not limit:
        return

    from apps.creative_generation.models import GenerationRequest
    from apps.video_generation.models import VideoGenerationRequest

    # Local midnight (TIME_ZONE), so the daily limit resets at the start of the business day.
    today_start = timezone.localtime().replace(hour=0, minute=0, second=0, microsecond=0)
    creative_count = GenerationRequest.objects.filter(company=company, created_at__gte=today_start).count()
    video_count = VideoGenerationRequest.objects.filter(company=company, created_at__gte=today_start).count()

    if creative_count + video_count >= limit:
        raise Throttled(detail=f'This company has reached its daily generation limit of {limit}.')
