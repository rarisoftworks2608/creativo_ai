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
    'instagram': 'For Instagram.',
    'facebook': 'For Facebook.',
    'linkedin': 'For LinkedIn - a more professional tone than the other platforms, same layout system.',
    'general': 'Suitable for posting across multiple platforms.',
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


def build_image_prompt(
    company, brand_profile, creative_type, platform, prompt_brief, product_info, variation_number, variation_count=3,
):
    """Structured as labeled sections (COMPOSITION / VISUAL STYLE / BACKGROUND /
    BRAND SAFETY) rather than one flat paragraph - explicit section headers
    measurably improve instruction-following on faster/distilled image models, the
    same way a real creative brief separates concerns instead of burying them in
    prose. The compositional target - RIGHT 55-60% hero subject, LEFT 40-45% calm
    zone, TOP-RIGHT logo-safe corner, vertical 4:5 - is the platform's fixed
    creative layout system (see project_plan.md's "creative plan" section) and
    matches exactly what compose_creative draws afterward - see
    compositor.py's _draw_left_content_zone/_place_logo_top_right - so the
    reserved space and the real overlay always agree.
    """
    format_guidance = CREATIVE_TYPE_GUIDANCE.get(creative_type, 'A social media creative.')
    platform_guidance = PLATFORM_GUIDANCE.get(platform, PLATFORM_GUIDANCE['general'])
    variation_note = (
        f'This is variation {variation_number} of {variation_count} - make it visually distinct from the '
        'other variations while staying on-brand.'
        if variation_count > 1 else
        'Make this the single best possible on-brand variation.'
    )
    lines = [
        f'Generate a premium marketing creative background image for "{company.name}" '
        f'({company.industry or "general business"}), in a sophisticated editorial advertising style - '
        'art-directed and intentional, not a generic AI-generated stock photo.',

        'COMPOSITION (fixed layout system - follow exactly):',
        f'- {format_guidance} {platform_guidance}',
        '- Vertical 4:5 portrait canvas.',
        '- RIGHT 55-60% of the frame: the main subject/hero visual, the clear photographic focal point, '
        'composed with intent rather than centered by default. Preserve the subject clearly and let it '
        'extend naturally toward the right and bottom edges of the canvas.',
        '- LEFT 40-45% of the frame: keep this a calm, spacious, visually quiet zone - soft environmental '
        'texture, a gradient, blur, open sky, or shadow only, with no important visual detail. A headline '
        'and supporting copy are composited there afterward and must never have to fight busy detail for '
        'attention.',
        '- TOP-RIGHT corner: keep clean and uncluttered too - the real brand logo is placed there '
        'afterward, and important detail directly behind it will get covered.',
        '- The composition should feel spacious and premium, with generous breathing room - do not fill '
        'every available area.',

        'VISUAL STYLE:',
        '- Photorealistic, shot on a professional camera - natural skin texture, realistic fabric, '
        'materials and reflections, shallow depth of field, cinematic but believable lighting.',
        '- No illustration, cartoon, painterly, or 3D-render look. No fantasy/surreal elements unless the '
        'brief explicitly calls for them. Avoid excessive HDR, oversaturation, or artificial glow.',

        'BACKGROUND:',
        '- Keep the environment soft and uncluttered, especially behind the LEFT calm zone and the '
        'TOP-RIGHT logo-safe corner - simplify rather than fill the frame with detail.',
        '- A real event/street photo is often covered in signage; deliberately avoid reproducing that '
        'here - use a plain wall, open sky, soft bokeh crowd, or plain fabric/decoration backdrop instead '
        'of a busy, sign-covered backdrop.',

        'BRAND SAFETY (critical):',
        '- Do not render any words, letters, numbers, logos, watermarks, brand marks, emblems, or badges '
        'anywhere in the image, in any language or script - this includes background/environmental text '
        '(banners, hoardings, posters, shop signs, street signs, flags, writing on clothing), not just '
        'foreground branding, even blurred or far in the background.',
        '- Do not invent a fake company logo or name anywhere in the scene.',
        '- The real headline, CTA text, and real brand logo are composited on afterward from '
        'separately-generated, guaranteed-accurate assets - anything rendered here would only ever be '
        'redundant or, worse, misspelled/fake.',

        f'Creative brief: {prompt_brief or "Use your best judgement based on the brand context below."}',
        f'Product information: {product_info or _joined(company.products, empty="not specified")}',
        *_brand_lines(brand_profile),
        variation_note,
    ]
    return '\n'.join(lines)


COPY_SYSTEM_PROMPT = (
    'You are a senior copywriter for a premium editorial advertising agency. '
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
        # Matches the fixed layout system's typography hierarchy (see build_image_prompt) -
        # eyebrow/headline/description/cta are composited top-to-bottom in the LEFT content
        # zone, in exactly this order, so each one has a distinct, non-overlapping job.
        'This copy fills a premium editorial layout with a strict typographic hierarchy - write '
        'each field to match its exact role, not just a variation of the same sentence:',
        '- eyebrow: a very short (1-4 word) small-caps kicker/label above the headline, e.g. "THE" '
        'or a short category/campaign label.',
        '- headline: the single large, high-impact statement - short, punchy, the main hook.',
        '- description: 1-2 short sentences of supporting copy beneath the headline.',
        '- cta: a short, understated call to action (2-4 words).',
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
