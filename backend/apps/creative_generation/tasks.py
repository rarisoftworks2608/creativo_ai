import inspect
import re
from decimal import Decimal

from celery import shared_task
from django.conf import settings
from django.core.files.base import ContentFile

from apps.ai_strategy.ai_client import get_provider as get_text_provider
from apps.ai_strategy.models import BrandContext
from apps.brand.models import BrandProfile
from apps.content_calendar import services as review_services
from apps.content_calendar.models import ContentCalendarItem
from apps.notifications.models import Notification
from apps.notifications.services import notify_content_ready
from apps.prompt_templates.models import PromptTemplate
from apps.prompt_templates.services import get_active_guidance
from common.ai_errors import AIProviderError

from . import prompts
from .art_direction import composition_for
from .compositor import compose_creative
from .creative_types import locked_copy, presets_for, rating_value, spec_for
from .image_client import get_image_provider
from .layouts import layout_for
from .models import GenerationRequest, GenerationVariation
from .schemas import CAROUSEL_SCHEMA, COPY_SCHEMA

MIME_EXTENSIONS = {'image/png': 'png', 'image/jpeg': 'jpg', 'image/webp': 'webp'}
CAROUSEL_MIN_SLIDES, CAROUSEL_MAX_SLIDES = 3, 10


def _fail(request, message):
    request.status = GenerationRequest.Status.FAILED
    request.error_message = message
    request.save(update_fields=['status', 'error_message', 'updated_at'])
    if request.content_calendar_item_id:
        ContentCalendarItem.objects.filter(pk=request.content_calendar_item_id).update(
            status=ContentCalendarItem.Status.FAILED,
        )
        review_services.generation_failed(
            request.content_calendar_item_id, message, kind='creative', request_id=request.id,
        )


def _read(field):
    if not field:
        return None
    try:
        with field.open('rb') as f:
            return f.read()
    except (FileNotFoundError, OSError, ValueError):
        return None


class BrandKit:
    """Everything a creative takes from the company's brand: the profile, the AI brand context and the logo files."""

    def __init__(self, company):
        self.profile = BrandProfile.objects.filter(company=company).first()
        self.context = BrandContext.objects.filter(company=company).first()
        self.logo = _read(self.profile.logo if self.profile is not None else None)
        self.symbol = _read(self.profile.secondary_logo if self.profile is not None else None)


def _draw_picture(image_provider, prompt, aspect, reference=None):
    """The image provider's picture, asking for the creative's shape when the provider can draw at a chosen size,
    and handing it the person's reference image when it accepts one."""
    try:
        parameters = inspect.signature(image_provider.generate_image).parameters
    except (TypeError, ValueError):
        parameters = {}
    kwargs = {'prompt': prompt}
    if 'aspect' in parameters:
        kwargs['aspect'] = aspect
    if reference is not None and 'reference_images' in parameters:
        kwargs['reference_images'] = [reference]
    return image_provider.generate_image(**kwargs)


REFERENCE_PROMPT = (
    'REFERENCE IMAGE: an image is supplied. Use it as the visual starting point - keep its subject, setting, mood and '
    'colour palette - while following the composition above. Do not copy any text or logo from it.'
)


def _reference(request):
    """(bytes, mime) of the person's reference image, or None."""
    data = _read(request.reference_image)
    if not data:
        return None
    name = request.reference_image.name.lower()
    mime = 'image/png' if name.endswith('.png') else 'image/webp' if name.endswith('.webp') else 'image/jpeg'
    return data, mime


def _picture_for(request, image_provider, prompt, aspect, *, may_use_as_base=True):
    """The picture for one image of the creative. With a reference image in 'base' mode the creative is designed on
    that exact image (no AI picture, no image credit); in 'inspire' mode - or for a carousel's later slides, which
    each need their own picture - the AI draws a new one guided by it. Counts the pictures the AI actually drew."""
    reference = _reference(request) if request.reference_image else None
    if reference and request.reference_mode == GenerationRequest.ReferenceMode.BASE and may_use_as_base:
        return reference
    request._ai_pictures = getattr(request, '_ai_pictures', 0) + 1
    if reference:
        return _draw_picture(image_provider, f'{prompt}\n{REFERENCE_PROMPT}', aspect, reference=reference)
    return _draw_picture(image_provider, prompt, aspect)


def _overlay_on(request):
    """Whether the copy is set on the image. Some types are nothing without their text (a carousel slide, an
    announcement, a testimonial), so for them it is always on."""
    return request.include_text_overlay or (request.creative_type in ('carousel', 'announcement_creative', 'testimonial_creative'))


def render_variation(variation, brand, background_bytes=None, background_mime='image/png'):
    """Composites the variation's own copy and the brand onto its picture with the layout recorded in
    `render_params`, and saves the result as `variation.image`. Used for a fresh picture, a regenerated one and an
    edit of the copy (which re-renders the kept picture - no AI call)."""
    request = variation.generation_request
    company = request.company
    params = variation.render_params or {}
    if background_bytes is None:
        background_bytes = _read(variation.background)
        if background_bytes is None:
            raise ValueError('This creative was made before its picture was kept, so it cannot be re-rendered.')
    overlay = _overlay_on(request)
    spec = layout_for(request.creative_type, request.aspect_ratio)
    fields = request.brief_fields or {}
    is_testimonial = request.creative_type == 'testimonial_creative'
    framed = params.get('framed', True) and overlay
    layout_info = {}
    image_bytes, mime_type = compose_creative(
        background_bytes, background_mime,
        eyebrow=variation.eyebrow if overlay else '',
        headline=variation.headline if overlay else '',
        description=variation.description if overlay else '',
        cta=variation.cta if overlay else '',
        logo_bytes=brand.logo, symbol_bytes=brand.symbol, brand_profile=brand.profile,
        placement=spec['placement'], aspect=spec['aspect'], creative_type=request.creative_type,
        # Varies the layout and typography between generations and between the variations of one request.
        variation_seed=params.get('seed'), composition=params.get('composition'),
        output_width=settings.CREATIVE_OUTPUT_WIDTH,
        # The poster furniture of a business creative: the services strip and the footer (see compositor).
        highlights=(params.get('highlights') or []) if framed else [],
        tagline=params.get('tagline', '') if framed else '',
        brand_name=company.name if framed else '',
        website=company.website if framed else '',
        exact_aspect=bool(params.get('exact')),
        safe_top=spec['safe_top'], safe_bottom=spec['safe_bottom'],
        style_presets=presets_for(request.creative_type, request.design_style) or None,
        style_seed=params.get('style_seed'), headline_scale=params.get('headline_scale', 1.0),
        rating=rating_value(fields) if is_testimonial and overlay else None,
        portrait_bytes=_read(request.customer_photo) if is_testimonial and overlay else None,
        # Where the logo went is kept, so an edit of the copy re-renders around the same logo position and every
        # slide of a carousel carries it in the same place.
        logo_anchor=params.get('logo_anchor'), layout_info=layout_info, logo_slots=params.get('logo_slots'),
    )
    if layout_info.get('logo_anchor') and not params.get('logo_anchor'):
        variation.render_params = {**params, 'logo_anchor': layout_info['logo_anchor']}
    ext = MIME_EXTENSIONS.get(mime_type, 'png')
    variation.image.save(f'variation_{variation.variation_number}.{ext}', ContentFile(image_bytes), save=False)


def _save_variation(request, brand, *, number, copy, picture, render_params, slide_role='', visual_scene=''):
    image_bytes, mime_type = picture
    variation = GenerationVariation(
        generation_request=request,
        variation_number=number,
        caption=copy.get('caption', ''),
        eyebrow=copy.get('eyebrow', ''),
        headline=copy.get('headline', ''),
        description=copy.get('description', ''),
        cta=copy.get('cta', ''),
        hashtags=copy.get('hashtags', []),
        keywords=copy.get('keywords', []),
        slide_role=slide_role,
        visual_scene=visual_scene,
        render_params=render_params,
    )
    ext = MIME_EXTENSIONS.get(mime_type, 'png')
    # The picture before the text: kept so a copy edit re-renders without another AI call.
    variation.background.save(f'background_{number}.{ext}', ContentFile(image_bytes), save=False)
    render_variation(variation, brand, image_bytes, mime_type)
    variation.save()
    return variation


def _new_style(request):
    """Every new creative is made at its exact platform size (a 4:5 post is 4:5), whether it was started from the
    creative form or from the content calendar ("Generate now" / the automatic sweep). Creatives made before this
    keep their stored layout when they are re-rendered (their `render_params['exact']`)."""
    return True


def _apply_locked(request, copy):
    """The person's own text replaces the AI's for the same roles (creative_types.locked_copy)."""
    if not request.brief_fields:
        return copy
    return {**copy, **locked_copy(request.creative_type, request.brief_fields)}


def _generate_single(request, brand, image_provider, text_provider, image_guidance, copy_guidance):
    """`variation_count` variations of one creative, each composed differently (art_direction.py)."""
    company = request.company
    spec = layout_for(request.creative_type, request.aspect_ratio)
    type_spec = spec_for(request.creative_type)
    count = 0
    for variation_number in range(1, request.variation_count + 1):
        # Each variation is composed differently: the picture is asked to leave calm space at the bottom, left,
        # right or top, and the layout and typography then follow that picture (art_direction.py).
        composition = composition_for(request.id, variation_number)
        copy_prompt = prompts.build_copy_prompt(
            company, brand.profile, brand.context, request.creative_type, request.platform,
            request.prompt_brief, request.product_info, extra_guidance=copy_guidance,
            calendar_item=request.content_calendar_item, brief_fields=request.brief_fields,
            design_style=request.design_style, aspect_ratio=spec['ratio'] if _new_style(request) else '',
        )
        # The copy comes first because it also rewrites the brief as a clear visual description (visual_scene)
        # that the image model is then given - same single request.
        copy_data = _apply_locked(request, text_provider.generate_json(
            system=prompts.COPY_SYSTEM_PROMPT, prompt=copy_prompt, json_schema=COPY_SCHEMA,
        ))
        image_prompt = prompts.build_image_prompt(
            company, brand.profile, request.creative_type, request.platform, request.prompt_brief,
            request.product_info, variation_number, request.variation_count, extra_guidance=image_guidance,
            scene_description=copy_data.get('visual_scene', ''), composition=composition,
            brief_fields=request.brief_fields, design_style=request.design_style,
            aspect_ratio=spec['ratio'] if _new_style(request) else '',
        )
        picture = _picture_for(request, image_provider, image_prompt, spec['aspect'])
        _save_variation(
            request, brand, number=variation_number, copy=copy_data, picture=picture,
            visual_scene=copy_data.get('visual_scene', ''),
            render_params={
                'composition': composition,
                'seed': request.id * 7 + variation_number,
                'exact': _new_style(request),
                'framed': type_spec.framed,
                'highlights': copy_data.get('highlights') or [],
                'tagline': copy_data.get('tagline', ''),
            },
        )
        count += 1
    return count


_INSTRUCTION_START = re.compile(
    r'^(please\s+)?(create|make|generate|design|write|produce|prepare|build|show|showcase|include|add|use|highlight|'
    r'feature|focus|mention|explain|talk about|cover)\b', re.IGNORECASE,
)
_INSTRUCTION_WORDS = re.compile(
    r'\b(carousel|instagram|facebook|linkedin|slides?|caption|hashtags?|creative|post)\b', re.IGNORECASE,
)


def looks_like_instruction(line):
    """True for an outline line written as a direction to the AI ("Create a premium real estate carousel showcasing
    ...") rather than as the words for a slide - such a line guides the AI but is never put on a slide verbatim."""
    return bool(_INSTRUCTION_START.search(line) or _INSTRUCTION_WORDS.search(line))


def _outline_lines(fields):
    """The person's outline as (headline, body) pairs: 'Headline | supporting text' or a bare headline per line.
    Lines that read as instructions are left out (they still reach the AI through the prompt)."""
    pairs = []
    for line in (fields.get('outline') or '').splitlines():
        line = line.strip().lstrip('-*0123456789.) ').strip()
        if not line or looks_like_instruction(line):
            continue
        headline, _, body = line.partition('|')
        pairs.append((headline.strip(), body.strip()))
    return pairs


def carousel_slides(copy_data, fields, slide_count):
    """The slides to render, in order, each {'role', 'headline', 'body', 'cta', 'visual_scene'}: the AI's plan, with the
    person's outline and CTA taking precedence over the AI's wording."""
    slides = [dict(slide) for slide in (copy_data.get('slides') or []) if isinstance(slide, dict)][:slide_count]
    if not slides:
        slides = [{
            'role': 'cover', 'headline': copy_data.get('headline', ''), 'body': copy_data.get('description', ''),
            'cta': copy_data.get('cta', ''), 'visual_scene': copy_data.get('visual_scene', ''),
        }]
    outline = _outline_lines(fields)
    targets = None
    if len(outline) == len(slides):
        targets = slides
    elif len(outline) == len(slides) - 2:
        targets = slides[1:-1]
    for slide, (headline, body) in zip(targets or [], outline):
        slide['headline'] = headline or slide.get('headline', '')
        slide['body'] = body or slide.get('body', '')
    for index, slide in enumerate(slides):
        slide['role'] = 'cover' if index == 0 else ('cta' if index == len(slides) - 1 and len(slides) > 1 else 'content')
        if slide['role'] != 'cta':
            slide['cta'] = ''
    if fields:
        # What the person typed is what the series shows: the topic is the cover (on its own - no AI line under
        # it), and the closing slide carries their CTA or none. The middle slides need words, so they come from
        # the person's outline when given, otherwise from the AI's plan.
        topic = (fields.get('headline') or fields.get('topic') or '').strip()
        if topic and targets is not slides:
            slides[0]['headline'] = topic
            slides[0]['body'] = ''
        if len(slides) > 1:
            slides[-1]['cta'] = fields.get('cta', '')
    return slides


CAROUSEL_LOGO_SLOTS = ('top_center', 'top_right')


def slide_render_params(request, index, total, role, *, highlights=(), tagline=''):
    """One slide's layout inputs: every slide shares the series' typography seed; each slide gets its own picture
    composition and layout seed. The cover's headline is the largest; the last slide may carry the poster footer."""
    return {
        'composition': composition_for(request.id, index),
        'seed': request.id * 7 + index,
        'style_seed': request.id * 13,
        'headline_scale': 1.0 if role == 'cover' else 0.8,
        'exact': True,
        'framed': role == 'cta',
        'highlights': list(highlights) if role == 'cta' else [],
        'tagline': tagline if role == 'cta' else '',
        # One logo place for the whole series: the cover chooses it from the places that suit every slide's layout
        # (the closing slide's header row has its kicker on the left), and the other slides keep it.
        'logo_slots': list(CAROUSEL_LOGO_SLOTS),
    }


def _slide_copy(slide, index, total, carousel_copy):
    counter = f'{index:02d} / {total:02d}'
    return {
        'caption': carousel_copy.get('caption', ''),
        'hashtags': carousel_copy.get('hashtags', []),
        'keywords': carousel_copy.get('keywords', []),
        'eyebrow': '' if slide['role'] == 'cover' else counter,
        'headline': slide.get('headline', ''),
        'description': slide.get('body', ''),
        'cta': slide.get('cta', ''),
    }


def _generate_carousel(request, brand, image_provider, text_provider, image_guidance, copy_guidance):
    """One text request plans the whole series (its shared look and each slide's role, copy and picture); then
    each slide is drawn and composited on its own, as an individual image."""
    company = request.company
    spec = layout_for(request.creative_type, request.aspect_ratio)
    fields = request.brief_fields or {}
    slide_count = request.slide_count or max(CAROUSEL_MIN_SLIDES, request.variation_count)
    slide_count = max(CAROUSEL_MIN_SLIDES, min(CAROUSEL_MAX_SLIDES, slide_count))
    carousel_prompt = prompts.build_carousel_prompt(
        company, brand.profile, brand.context, request.platform, request.prompt_brief, request.product_info,
        brief_fields=fields, slide_count=slide_count, design_style=request.design_style,
        extra_guidance=copy_guidance, calendar_item=request.content_calendar_item,
    )
    carousel_copy = text_provider.generate_json(
        system=prompts.COPY_SYSTEM_PROMPT, prompt=carousel_prompt, json_schema=CAROUSEL_SCHEMA,
    )
    slides = carousel_slides(carousel_copy, fields, slide_count)
    series_look = (carousel_copy.get('series_look') or '').strip()
    request.generation_context = {**(request.generation_context or {}), 'series_look': series_look}
    request.save(update_fields=['generation_context', 'updated_at'])

    total = len(slides)
    logo_anchor = None
    for index, slide in enumerate(slides, start=1):
        params = slide_render_params(request, index, total, slide['role'])
        if logo_anchor:
            params['logo_anchor'] = logo_anchor  # the cover's logo place, on every slide
        image_prompt = prompts.build_image_prompt(
            company, brand.profile, request.creative_type, request.platform, request.prompt_brief,
            request.product_info, index, total, extra_guidance=image_guidance,
            scene_description=slide.get('visual_scene', ''), composition=params['composition'],
            brief_fields=fields, design_style=request.design_style, aspect_ratio=spec['ratio'],
            series_look=series_look, slide_label=f'Slide {index} of {total}',
        )
        # The person's image is the cover; every other slide gets its own picture, guided by it.
        picture = _picture_for(request, image_provider, image_prompt, spec['aspect'], may_use_as_base=index == 1)
        saved = _save_variation(
            request, brand, number=index, copy=_slide_copy(slide, index, total, carousel_copy), picture=picture,
            render_params=params, slide_role=slide['role'], visual_scene=slide.get('visual_scene', ''),
        )
        logo_anchor = logo_anchor or (saved.render_params or {}).get('logo_anchor')
    return total


@shared_task(bind=True)
def generate_creative_variations(self, generation_request_id):
    """Generates a GenerationRequest's creative: `variation_count` variations (1-3, admin-selectable to save AI
    credits while testing) for most types, or one image per slide for a carousel (Epic 06: Generation Management).
    Each creative type follows its own system (creative_types.py)."""
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
    brand = BrandKit(company)

    try:
        image_provider = get_image_provider()
        text_provider = get_text_provider()
    except AIProviderError as exc:
        _fail(request, str(exc))
        return

    request.variations.all().delete()

    image_guidance = get_active_guidance(
        PromptTemplate.Category.IMAGE, platform=request.platform, creative_type=request.creative_type,
    )
    copy_guidance = get_active_guidance(
        PromptTemplate.Category.CAPTION, platform=request.platform, creative_type=request.creative_type,
    )

    generate = _generate_carousel if request.creative_type == GenerationRequest.CreativeType.CAROUSEL else _generate_single
    request._ai_pictures = 0  # pictures the image AI actually draws (none when designed on the person's image)
    try:
        image_count = generate(request, brand, image_provider, text_provider, image_guidance, copy_guidance)
    except AIProviderError as exc:
        done = request.variations.count()
        _fail(request, f'Failed on image {done + 1}: {exc}')
        return
    except Exception as exc:  # noqa: BLE001 - guarantee the request never gets stuck "processing"
        done = request.variations.count()
        _fail(request, f'Unexpected error on image {done + 1}: {exc}')
        return

    request.status = GenerationRequest.Status.SUCCEEDED
    request.error_message = ''
    request.model_used = f'{getattr(image_provider, "model", "")} + {getattr(text_provider, "model", "")}'
    ai_pictures = request._ai_pictures
    request.usage = {'images_generated': ai_pictures}
    if ai_pictures != image_count:
        request.usage['images_from_reference'] = image_count - ai_pictures

    if settings.AI_IMAGE_COST_PER_IMAGE_USD:
        try:
            request.cost_usd = Decimal(str(settings.AI_IMAGE_COST_PER_IMAGE_USD)) * ai_pictures
        except (ValueError, ArithmeticError):
            pass

    request.save(update_fields=['status', 'error_message', 'model_used', 'usage', 'cost_usd', 'updated_at'])
    calendar_item = None
    if request.content_calendar_item_id:
        ContentCalendarItem.objects.filter(pk=request.content_calendar_item_id).update(
            status=ContentCalendarItem.Status.PENDING_APPROVAL,
        )
        calendar_item = ContentCalendarItem.objects.filter(pk=request.content_calendar_item_id).first()

    # A regeneration after a client rejection is a brand new request (retry_count 0) on an
    # item whose regeneration_count was bumped by ContentCalendarRejectView.
    is_regeneration = request.retry_count > 0 or bool(calendar_item and calendar_item.regeneration_count > 0)
    if calendar_item is not None:
        review_services.submitted_for_review(
            calendar_item.id, is_regeneration=is_regeneration, kind='creative', request_id=request.id,
        )
    is_carousel = request.creative_type == GenerationRequest.CreativeType.CAROUSEL
    notify_content_ready(
        company=company,
        created_by=request.created_by,
        notification_type=(
            Notification.NotificationType.CONTENT_REGENERATED if is_regeneration
            else Notification.NotificationType.CONTENT_GENERATED
        ),
        title=f'{request.get_creative_type_display()} {"regenerated" if is_regeneration else "ready"}',
        message=f'{image_count} {"slide" if is_carousel else "variation"}(s) generated for {company.name}.',
        url=f'/companies/{company.id}/creative-generation',
    )


@shared_task(bind=True)
def regenerate_variation(self, variation_id):
    """Draws a new picture for ONE variation (a single carousel slide, or one variation of a creative) and
    composites the same copy onto it - the rest of the creative is untouched. One image credit."""
    variation = (
        GenerationVariation.objects.select_related('generation_request__company', 'generation_request__content_calendar_item')
        .filter(pk=variation_id).first()
    )
    if variation is None:
        return
    request = variation.generation_request
    company = request.company
    brand = BrandKit(company)
    spec = layout_for(request.creative_type, request.aspect_ratio)
    params = dict(variation.render_params or {})
    attempt = int(params.get('attempt', 0)) + 1
    # A new seed and the next composition, so the new picture and its layout differ from the last one.
    params.update({'attempt': attempt, 'seed': request.id * 7 + variation.variation_number + 997 * attempt})
    params['composition'] = composition_for(request.id + attempt, variation.variation_number)
    if request.creative_type != GenerationRequest.CreativeType.CAROUSEL:
        params.pop('logo_anchor', None)  # a new picture: the logo finds its place in it again

    try:
        image_provider = get_image_provider()
        image_guidance = get_active_guidance(
            PromptTemplate.Category.IMAGE, platform=request.platform, creative_type=request.creative_type,
        )
        is_carousel = request.creative_type == GenerationRequest.CreativeType.CAROUSEL
        total = request.variations.count()
        image_prompt = prompts.build_image_prompt(
            company, brand.profile, request.creative_type, request.platform, request.prompt_brief,
            request.product_info, variation.variation_number, max(total, 1), extra_guidance=image_guidance,
            scene_description=variation.visual_scene, composition=params['composition'],
            brief_fields=request.brief_fields, design_style=request.design_style,
            aspect_ratio=spec['ratio'] if _new_style(request) or is_carousel else '',
            series_look=(request.generation_context or {}).get('series_look', '') if is_carousel else '',
            slide_label=f'Slide {variation.variation_number} of {total}' if is_carousel else '',
        )
        image_bytes, mime_type = _picture_for(
            request, image_provider, image_prompt, spec['aspect'],
            may_use_as_base=not is_carousel or variation.variation_number == 1,
        )
        variation.render_params = params
        ext = MIME_EXTENSIONS.get(mime_type, 'png')
        variation.background.save(f'background_{variation.variation_number}_{attempt}.{ext}', ContentFile(image_bytes), save=False)
        render_variation(variation, brand, image_bytes, mime_type)
    except Exception as exc:  # noqa: BLE001 - the slide must never stay "processing"
        variation.status = GenerationVariation.Status.FAILED
        variation.error_message = str(exc)[:500]
        variation.save(update_fields=['status', 'error_message', 'updated_at'])
        return

    variation.status = GenerationVariation.Status.READY
    variation.error_message = ''
    variation.save()
    if not getattr(request, '_ai_pictures', 0):
        return  # re-laid out on the person's own image: no AI picture, nothing to count
    usage = dict(request.usage or {})
    usage['images_generated'] = int(usage.get('images_generated', 0)) + 1
    request.usage = usage
    if settings.AI_IMAGE_COST_PER_IMAGE_USD:
        try:
            request.add_cost(Decimal(str(settings.AI_IMAGE_COST_PER_IMAGE_USD)))
        except (ValueError, ArithmeticError):
            pass
    request.save(update_fields=['usage', 'cost_usd', 'updated_at'])
