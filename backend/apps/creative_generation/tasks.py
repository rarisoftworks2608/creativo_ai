from decimal import Decimal

from celery import shared_task
from django.conf import settings
from django.core.files.base import ContentFile

from apps.ai_strategy.ai_client import get_provider as get_text_provider
from apps.ai_strategy.models import BrandContext
from apps.brand.models import BrandProfile
from apps.content_calendar.models import ContentCalendarItem
from apps.notifications.models import Notification
from apps.notifications.services import notify_content_ready
from common.ai_errors import AIProviderError

from . import prompts
from .compositor import compose_creative
from .image_client import get_image_provider
from .models import GenerationRequest, GenerationVariation
from .schemas import COPY_SCHEMA

MIME_EXTENSIONS = {'image/png': 'png', 'image/jpeg': 'jpg', 'image/webp': 'webp'}

VARIATIONS_PER_REQUEST = 3


def _fail(request, message):
    request.status = GenerationRequest.Status.FAILED
    request.error_message = message
    request.save(update_fields=['status', 'error_message', 'updated_at'])
    if request.content_calendar_item_id:
        ContentCalendarItem.objects.filter(pk=request.content_calendar_item_id).update(
            status=ContentCalendarItem.Status.FAILED,
        )


@shared_task(bind=True)
def generate_creative_variations(self, generation_request_id):
    """Generates 3 image + copy variations for a GenerationRequest (Epic 06: Generation Management)."""
    try:
        request = GenerationRequest.objects.select_related('company', 'content_calendar_item').get(
            pk=generation_request_id,
        )
    except GenerationRequest.DoesNotExist:
        return

    request.status = GenerationRequest.Status.PROCESSING
    request.celery_task_id = self.request.id or ''
    request.save(update_fields=['status', 'celery_task_id', 'updated_at'])
    if request.content_calendar_item_id:
        ContentCalendarItem.objects.filter(pk=request.content_calendar_item_id).update(
            status=ContentCalendarItem.Status.GENERATING,
        )

    company = request.company
    brand_profile = BrandProfile.objects.filter(company=company).first()
    brand_context = BrandContext.objects.filter(company=company).first()

    def _read(field):
        if not field:
            return None
        try:
            with field.open('rb') as f:
                return f.read()
        except (FileNotFoundError, OSError):
            return None

    logo_bytes = _read(brand_profile.logo if brand_profile is not None else None)
    symbol_bytes = _read(brand_profile.secondary_logo if brand_profile is not None else None)

    try:
        image_provider = get_image_provider()
        text_provider = get_text_provider()
    except AIProviderError as exc:
        _fail(request, str(exc))
        return

    request.variations.all().delete()

    image_count = 0
    for variation_number in range(1, VARIATIONS_PER_REQUEST + 1):
        image_prompt = prompts.build_image_prompt(
            company, brand_profile, request.creative_type, request.platform, request.prompt_brief,
            request.product_info, variation_number,
        )
        copy_prompt = prompts.build_copy_prompt(
            company, brand_profile, brand_context, request.creative_type, request.platform,
            request.prompt_brief, request.product_info,
        )

        try:
            image_bytes, mime_type = image_provider.generate_image(prompt=image_prompt)
            copy_data = text_provider.generate_json(
                system=prompts.COPY_SYSTEM_PROMPT, prompt=copy_prompt, json_schema=COPY_SCHEMA,
            )
        except AIProviderError as exc:
            _fail(request, f'Failed on variation {variation_number}: {exc}')
            return
        except Exception as exc:  # noqa: BLE001 - guarantee the request never gets stuck "processing"
            _fail(request, f'Unexpected error on variation {variation_number}: {exc}')
            return

        image_bytes, mime_type = compose_creative(
            image_bytes, mime_type,
            headline=copy_data.get('headline', ''), cta=copy_data.get('cta', ''),
            logo_bytes=logo_bytes, symbol_bytes=symbol_bytes, brand_profile=brand_profile,
        )
        ext = MIME_EXTENSIONS.get(mime_type, 'png')
        variation = GenerationVariation(
            generation_request=request,
            variation_number=variation_number,
            caption=copy_data.get('caption', ''),
            headline=copy_data.get('headline', ''),
            description=copy_data.get('description', ''),
            cta=copy_data.get('cta', ''),
            hashtags=copy_data.get('hashtags', []),
            keywords=copy_data.get('keywords', []),
        )
        variation.image.save(f'variation_{variation_number}.{ext}', ContentFile(image_bytes), save=False)
        variation.save()
        image_count += 1

    request.status = GenerationRequest.Status.SUCCEEDED
    request.error_message = ''
    request.model_used = f'{getattr(image_provider, "model", "")} + {getattr(text_provider, "model", "")}'
    request.usage = {'images_generated': image_count}

    if settings.AI_IMAGE_COST_PER_IMAGE_USD:
        try:
            request.cost_usd = Decimal(str(settings.AI_IMAGE_COST_PER_IMAGE_USD)) * image_count
        except (ValueError, ArithmeticError):
            pass

    request.save(update_fields=['status', 'error_message', 'model_used', 'usage', 'cost_usd', 'updated_at'])
    if request.content_calendar_item_id:
        ContentCalendarItem.objects.filter(pk=request.content_calendar_item_id).update(
            status=ContentCalendarItem.Status.PENDING_APPROVAL,
        )

    is_regeneration = request.retry_count > 0
    notify_content_ready(
        company=company,
        created_by=request.created_by,
        notification_type=(
            Notification.NotificationType.CONTENT_REGENERATED if is_regeneration
            else Notification.NotificationType.CONTENT_GENERATED
        ),
        title=f'{request.get_creative_type_display()} {"regenerated" if is_regeneration else "ready"}',
        message=f'{image_count} variation(s) generated for {company.name}.',
        url=f'/companies/{company.id}/creative-generation',
    )
