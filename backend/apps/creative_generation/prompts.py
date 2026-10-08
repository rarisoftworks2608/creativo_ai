"""Prompt assembly for Epic 06 (AI Creative Generation).

Brand-Aware Generation: every prompt below is grounded in the company's
brand profile (Epic 03) and, when available, the synthesized brand context
(Epic 05) - colors, logo, tone, typography, visual style and product
information all flow into both the image prompt and the copy prompt.
"""

from common.ai_config import content_language_instruction

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
        'Color direction: build the scene\'s color grade, lighting, props and background tones around the '
        'brand colors above so the creative looks on-brand - the overlay text and logo use the same palette.',
        f'Brand tone: {brand_profile.tone or "not specified"}',
        f'Visual style: {brand_profile.visual_style or "not specified"}',
        f'Typography notes: {brand_profile.typography_notes or "not specified"}',
        f"Do's: {_joined(brand_profile.dos)}",
        f"Don'ts: {_joined(brand_profile.donts)}",
    ]


def build_image_prompt(
    company, brand_profile, creative_type, platform, prompt_brief, product_info, variation_number, variation_count=3,
    extra_guidance='',
):
    """The creative brief leads and is followed as written - a detailed brief (a full scene,
    named props, people, lighting) must come out as that scene, not be squeezed into a fixed
    layout. Brand context follows as guidance, and the safety section keeps text/logos out of
    the picture: the real headline, CTA and logo are drawn on afterwards by
    compositor.compose_creative from the real assets and copy, so anything the image model
    rendered there would only ever be redundant or misspelled.
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
        # The company name / industry are deliberately not quoted here: image models tend to
        # paint any name they are given into the picture as a faint caption or watermark.
        'Create a marketing image for a brand. Its name, tagline and industry must not appear in the image.',
        f'Format: {format_guidance} {platform_guidance}',

        'CREATIVE BRIEF - this is the primary instruction. Follow it faithfully: the scene, subjects, '
        'setting, props, people, lighting, mood and level of detail it describes. Never write any of '
        "the brief's own words - the occasion name, a slogan, the year - into the image as text:",
        prompt_brief or 'Use your best judgement based on the brand context below.',
        f'Product information: {product_info or _joined(company.products, empty="not specified")}',

        'PHOTOGRAPHIC QUALITY:',
        '- Photorealistic, like a real professional photograph (editorial / commercial campaign '
        'photography): realistic light, true-to-life materials and textures, natural skin and fabric, '
        'believable depth of field.',
        '- Show the complete scene the brief describes - environment, supporting details, atmosphere - '
        'rather than a tight close-up of one subject, unless the brief asks for a close-up.',
        '- Keep every subject fully in frame, composed naturally edge to edge. No distorted anatomy, '
        'extra limbs or malformed faces and hands; no illustration, cartoon, plastic/CGI look, '
        'oversaturation or artificial glow.',
        '- Keep faces and the main focal point out of the bottom 20% of the frame, and let the scene simply '
        'continue there (floor, surface, flowers, soft shadow) - plain and uncluttered, with no panel, banner, '
        'caption, label or any text.',

        'BRAND (guidance - apply naturally without overpowering the brief):',
        *_brand_lines(brand_profile),

        'BRAND SAFETY (critical):',
        '- Do not render any words, letters, numbers, logos, watermarks, brand marks or emblems anywhere '
        'in the image, in any language or script - including background text such as banners, posters, '
        'signs, packaging and writing on clothing.',
        '- Do not write the brand name, a tagline, a caption or a watermark anywhere, even faintly or '
        'blurred. The real logo and headline are added afterwards.',
    ]
    if extra_guidance:
        # Admin-configured guidance (Epic 21: Prompt & Template Management) - appended
        # rather than replacing anything above, so the brand safety rules always still
        # apply regardless of what an admin writes here.
        lines += ['ADDITIONAL GUIDANCE (admin-configured):', extra_guidance]
    lines.append(variation_note)
    return '\n'.join(lines)


COPY_SYSTEM_PROMPT = (
    'You are a senior copywriter for a premium editorial advertising agency. '
    'Write copy that matches the brand voice/tone exactly and never uses restricted words. '
    'Always respond with only the requested JSON output - never ask clarifying questions or add '
    'commentary. Where the brief or brand details are sparse, make reasonable, on-brand assumptions '
    'and proceed rather than asking for more information.'
)


def build_copy_prompt(
    company, brand_profile, brand_context, creative_type, platform, prompt_brief, product_info, extra_guidance='',
):
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
    if extra_guidance:
        lines += ['', 'ADDITIONAL GUIDANCE (admin-configured):', extra_guidance]
    language_line = content_language_instruction()
    if language_line:
        lines += ['', language_line]
    return '\n'.join(lines)
