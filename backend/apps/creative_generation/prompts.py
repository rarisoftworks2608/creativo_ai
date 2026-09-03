"""Prompt assembly for Epic 06 (AI Creative Generation).

Brand-Aware Generation: every prompt below is grounded in the company's
brand profile (Epic 03) and, when available, the synthesized brand context
(Epic 05) - colors, logo, tone, typography, visual style and product
information all flow into both the image prompt and the copy prompt.
"""

CREATIVE_TYPE_GUIDANCE = {
    # Legacy - these three bundled a platform into the format; still resolved for
    # old rows (retry, display of history) but no longer offered in the UI.
    'instagram_post': 'A square (1:1) Instagram feed post.',
    'facebook_post': 'A landscape (1.91:1) Facebook feed post.',
    'linkedin_post': 'A professional, landscape LinkedIn feed post.',
    'post': 'A standard single-image feed post.',
    'carousel': 'The first slide of a multi-slide carousel.',
    'story': 'A vertical (9:16) Story.',
    'promotional_creative': 'A promotional/sale creative.',
    'festival_creative': 'A festival/seasonal greeting creative.',
    'product_creative': 'A product-focused creative showcasing the product clearly.',
    'educational_creative': 'An educational/informative creative that teaches or explains something.',
    'event_creative': 'An event promotion creative (webinar, launch, in-person event) with clear date/time framing.',
    'announcement_creative': 'A company announcement or news creative.',
    'testimonial_creative': 'A customer testimonial/review highlight creative.',
}

PLATFORM_GUIDANCE = {
    'instagram': 'For Instagram: square (1:1) aspect ratio unless the format above dictates otherwise.',
    'facebook': 'For Facebook: landscape (1.91:1) aspect ratio unless the format above dictates otherwise.',
    'linkedin': 'For LinkedIn: a professional tone, landscape aspect ratio unless the format above dictates otherwise.',
    'general': 'Square (1:1) aspect ratio, suitable for posting across multiple platforms.',
}


def _joined(values, empty='not specified'):
    return ', '.join(v for v in values if v) or empty


def _brand_lines(brand_profile):
    if brand_profile is None:
        return ['Brand guidelines: not specified.']
    colors = ', '.join(f'{c.get("name", "")} {c.get("hex", "")}'.strip() for c in brand_profile.brand_colors) or 'not specified'
    return [
        f'Brand colors: {colors}',
        f'Brand tone: {brand_profile.tone or "not specified"}',
        f'Visual style: {brand_profile.visual_style or "not specified"}',
        f'Typography notes: {brand_profile.typography_notes or "not specified"}',
        f"Do's: {_joined(brand_profile.dos)}",
        f"Don'ts: {_joined(brand_profile.donts)}",
    ]


def build_image_prompt(company, brand_profile, creative_type, platform, prompt_brief, product_info, variation_number):
    format_guidance = CREATIVE_TYPE_GUIDANCE.get(creative_type, 'A social media creative.')
    platform_guidance = PLATFORM_GUIDANCE.get(platform, PLATFORM_GUIDANCE['general'])
    lines = [
        f'Create a polished, on-brand marketing creative for "{company.name}" ({company.industry or "general business"}).',
        # Stated early (models weight earlier instructions more heavily, especially
        # faster/distilled ones with weaker instruction-following) and worded
        # concretely rather than abstractly ("no words/letters/numbers" rather than
        # just "no typography") - this is the single highest-value line in the whole
        # prompt for suppressing hallucinated logos/watermarks/brand text, which is
        # otherwise the most common failure mode of cheaper image models.
        'CRITICAL: Do not render any words, letters, numbers, logos, watermarks, brand marks, '
        'emblems, or badges anywhere in the image - no signage, no packaging text, no clothing '
        'text, no invented company names, in any language or script. Produce a clean photographic '
        'visual only. The real headline, CTA text, and real brand logo are composited on '
        'afterward from separately-generated, guaranteed-accurate assets, so anything you render '
        'yourself here would only ever be redundant or, worse, misspelled/fake.',
        format_guidance,
        platform_guidance,
        f'Creative brief: {prompt_brief or "Use your best judgement based on the brand context below."}',
        f'Product information: {product_info or _joined(company.products, empty="not specified")}',
        *_brand_lines(brand_profile),
        f'This is variation {variation_number} of 3 - make it visually distinct from the other variations '
        'while staying on-brand.',
        'Photorealistic, shot on a professional camera - natural skin texture, realistic fabric '
        'and lighting, shallow depth of field, no illustration/cartoon/painterly/3D-render look.',
        'Compose the shot so the bottom of the frame (roughly the lower third) is naturally '
        'darker, softly blurred, or otherwise visually calm - like a shaded background, an '
        'out-of-focus foreground element, or open ground/sky - so a headline can be overlaid '
        'there afterward without fighting for attention against busy detail. The main subject '
        'should stay in the upper two-thirds of the frame.',
    ]
    return '\n'.join(lines)


COPY_SYSTEM_PROMPT = (
    'You are a senior social media copywriter for a digital marketing agency. '
    'Write copy that matches the brand voice/tone exactly and never uses restricted words. '
    'Always respond with only the requested JSON output - never ask clarifying questions or add '
    'commentary. Where the brief or brand details are sparse, make reasonable, on-brand assumptions '
    'and proceed rather than asking for more information.'
)


def build_copy_prompt(company, brand_profile, brand_context, creative_type, platform, prompt_brief, product_info):
    format_guidance = CREATIVE_TYPE_GUIDANCE.get(creative_type, 'a social media creative')
    platform_guidance = PLATFORM_GUIDANCE.get(platform, PLATFORM_GUIDANCE['general'])
    lines = [
        f'Write the copy for {format_guidance} for "{company.name}".',
        platform_guidance,
        f'Creative brief: {prompt_brief or "Use your best judgement."}',
        f'Product information: {product_info or _joined(company.products, empty="not specified")}',
    ]
    if brand_context is not None and brand_context.summary:
        lines += ['', 'Brand context:', brand_context.summary]
    elif brand_profile is not None:
        lines += ['', *_brand_lines(brand_profile)]
    if brand_profile is not None and brand_profile.restricted_words:
        lines.append(f'Restricted words - never use these: {_joined(brand_profile.restricted_words)}')
    return '\n'.join(lines)
