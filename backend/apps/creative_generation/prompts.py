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


def _build_festive_image_prompt(
    company, brand_profile, prompt_brief, product_info, variation_number, variation_count,
    platform_guidance, variation_note, extra_guidance,
):
    """The "Festive Design Flow" (project_plan.md, reference image docs/festive-design-flow.jpg):
    plain light background -> ONE festive element in the centre -> greeting -> wish -> logo
    top-right. The image model only supplies the background and the element (and keeps the rest
    empty); compositor._draw_festive_layout adds the greeting, wish and logo afterwards.

    Deliberately written in purely visual, positive terms. The words text / lettering / greeting /
    logo / caption (and the brand or festival name) are kept out of the prompt entirely: image
    models, FLUX especially, tend to paint any such word into the picture - "do not draw text"
    is the surest way to get text. Anything painted there anyway is erased by the compositor.
    """
    from .festive import element_for, parse_festive_details, props_for

    details = parse_festive_details(prompt_brief)
    colors = [c['hex'] for c in (getattr(brand_profile, 'brand_colors', None) or []) if c.get('hex')][:3]
    lines = [
        'A premium, minimal festive composition photographed in a studio, portrait 4:5, on a plain, '
        'light cream-ivory background with a soft warm glow and a barely visible vignette - clean, calm, elegant.',
        f'One single subject, large and prominent, filling about half the width of the frame, at the centre of '
        f'the upper-middle of the frame: {element_for(details, prompt_brief)}{props_for(details, prompt_brief)}.',
        'Photorealistic and razor-sharp, with crisp detail, polished brass and gold, fresh petals, soft natural '
        'studio lighting, warm golden highlights and a gentle soft shadow.',
        'A few soft, out-of-focus golden lights glow far behind the subject, in the upper part of the frame only.',
        'The lowest 40% of the frame is a calm, empty, perfectly plain cream area, and the top-right corner is '
        'empty plain cream as well. Spacious, balanced, uncluttered, premium.',
    ]
    if colors:
        lines.append(f'Colour accents, only on the subject\'s details: {", ".join(colors)}.')
    if product_info:
        lines.append(f'Context: {product_info}')
    if extra_guidance:
        lines += ['ADDITIONAL GUIDANCE (admin-configured):', extra_guidance]
    lines.append(variation_note)
    return '\n'.join(lines)


# What the single hero subject should be for each type, in purely visual terms (no words that
# suggest lettering - see _build_festive_image_prompt for why).
SUBJECT_HINTS = {
    'promotional_creative': 'a single eye-catching hero object that suits the offer',
    'product_creative': 'the product itself, shown whole, clean and in sharp focus',
    'educational_creative': 'one simple, clear visual object or metaphor that illustrates the idea',
    'event_creative': 'one iconic object that evokes the occasion',
    'announcement_creative': 'one polished, symbolic object that suits the news',
    'testimonial_creative': 'a warm, friendly, natural portrait of one smiling person',
}


def build_image_prompt(
    company, brand_profile, creative_type, platform, prompt_brief, product_info, variation_number, variation_count=3,
    extra_guidance='', scene_description='',
):
    """Every creative shares one design system (layouts.py): a plain light background, ONE hero
    subject, an empty area where the text will go and an empty top-right corner for the logo. The
    image model supplies only the subject and the background; compositor.compose_creative draws
    the real headline, copy and logo afterwards from the real assets and text.

    The prompts are written in purely visual, positive terms. The words text / lettering / logo /
    caption (and the brand or festival name) are kept out of them: image models, FLUX especially,
    tend to paint any such word into the picture - "do not draw text" is the surest way to get
    text. Anything painted in the text area anyway is smoothed away by the compositor.
    """
    from .festive import describes_scene, is_festive_request
    from .layouts import layout_for

    platform_guidance = PLATFORM_GUIDANCE.get(platform, PLATFORM_GUIDANCE['general'])
    variation_note = (
        f'This is variation {variation_number} of {variation_count} - make it visually distinct from the '
        'other variations while staying on-brand.'
        if variation_count > 1 else
        'Make this the single best possible on-brand variation.'
    )
    if describes_scene(prompt_brief):
        # The admin described the picture: make that picture - for every type, festivals included. Only
        # the text and logo layout stay the same (see layouts.py).
        from .festive import clean_scene_brief

        # `scene_description` is the brief rewritten by the text AI as a clear visual description; the
        # raw brief (often misspelt, full of "create a ... for") is only the fallback.
        return _build_scene_image_prompt(
            brand_profile, layout_for(creative_type, prompt_brief)['placement'],
            (scene_description or '').strip() or clean_scene_brief(prompt_brief), product_info,
            variation_note, extra_guidance,
        )
    if is_festive_request(creative_type, prompt_brief):
        # No description: the festive template (plain background, one festive element, empty area below).
        return _build_festive_image_prompt(
            company, brand_profile, prompt_brief, product_info, variation_number, variation_count,
            platform_guidance, variation_note, extra_guidance,
        )
    return _build_plain_image_prompt(
        company, brand_profile, creative_type, layout_for(creative_type, prompt_brief)['placement'],
        prompt_brief, product_info, variation_note, extra_guidance,
    )


def _build_scene_image_prompt(brand_profile, placement, prompt_brief, product_info, variation_note, extra_guidance):
    """The admin described a scene: follow it. Only the layout needs are added - a calmer area where
    the text goes and a calm top-right corner for the logo - and, as everywhere, no wording about
    lettering (the compositor draws the real text and logo over a soft gradient)."""
    colors = [c['hex'] for c in (getattr(brand_profile, 'brand_colors', None) or []) if c.get('hex')][:3]
    if placement == 'top':
        composition = (
            'The main subject sits in the lower-middle of the frame. The top 40% of the frame is calm, simple and '
            'uncluttered (soft sky, open space or a quiet wall - whatever suits the scene).'
        )
    else:
        composition = (
            'The main subject sits in the upper-middle of the frame. The lowest 40% of the frame is calm, simple and '
            'uncluttered (soft water, sand, sky or a quiet surface - whatever suits the scene), and the top-right '
            'corner is calm and uncluttered too.'
        )
    lines = [
        f'A premium, realistic, professionally photographed scene, portrait 4:5: {prompt_brief.strip()[:700]}.',
        'Photorealistic and razor-sharp, natural light, true-to-life detail and materials, cinematic but believable, '
        'with the main subject large and clear.',
        composition,
    ]
    if (product_info or '').strip():
        lines.append(f'Also: {product_info.strip()[:200]}')
    if colors:
        lines.append(f'Where it feels natural, echo these brand colours: {", ".join(colors)}.')
    if extra_guidance:
        lines += ['ADDITIONAL GUIDANCE (admin-configured):', extra_guidance]
    lines.append(variation_note)
    return '\n'.join(lines)


def _empty_area_sentence(placement):
    if placement == 'top':
        return (
            'The top 40% of the frame is a calm, empty, perfectly plain cream area. '
            'Spacious, balanced, uncluttered, premium.'
        )
    return (
        'The lowest 40% of the frame is a calm, empty, perfectly plain cream area, and the top-right corner is '
        'empty plain cream as well. Spacious, balanced, uncluttered, premium.'
    )


def _build_plain_image_prompt(
    company, brand_profile, creative_type, placement, prompt_brief, product_info, variation_note, extra_guidance,
):
    colors = [c['hex'] for c in (getattr(brand_profile, 'brand_colors', None) or []) if c.get('hex')][:3]
    subject_parts = [
        SUBJECT_HINTS.get(creative_type, ''),
        f'inspired by this description: {(prompt_brief or "").strip()[:600]}' if (prompt_brief or '').strip() else '',
        (product_info or '').strip()[:300] or ', '.join(str(p) for p in (company.products or [])[:3]),
    ]
    subject = '; '.join(part for part in subject_parts if part) or 'one single, beautifully crafted object that suits the brand'
    position = 'lower-middle' if placement == 'top' else 'upper-middle'
    lines = [
        'A premium, minimal composition photographed in a studio, portrait 4:5, on a plain, light cream-ivory '
        'background with a soft warm glow and a barely visible vignette - clean, calm, elegant.',
        f'One single hero subject, large and prominent, filling about half the width of the frame, at the centre of '
        f'the {position} of the frame: {subject}.',
        'Photorealistic and razor-sharp, with crisp detail, true-to-life materials, soft natural studio lighting, '
        'warm highlights and a gentle soft shadow. Keep it to that one subject - simplify any bigger scene to its '
        'single most important element.',
        _empty_area_sentence(placement),
    ]
    if colors:
        lines.append(f'Colour accents, only on the subject\'s details: {", ".join(colors)}.')
    if extra_guidance:
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
    from .festive import describes_scene, is_festive_request

    if is_festive_request(creative_type, prompt_brief):
        role_lines = [
            'This copy fills a fixed festive greeting layout (festive element, then greeting, then a wish) - '
            'write each field for its exact role:',
            '- eyebrow: the small greeting word(s) that come BEFORE the festival name, e.g. "Happy", '
            '"Wishing you a", "Warm wishes on" (1-3 words). Use an empty string if the greeting is a single '
            'phrase such as "Eid Mubarak".',
            '- headline: the festival name or greeting itself in 1-3 words, e.g. "Diwali", "Christmas", '
            '"Eid Mubarak". Never include the year.',
            '- description: one short, warm, meaningful festive wish of at most 18 words, e.g. '
            '"May this Diwali bring light, joy and new beginnings." No offers, prices or company name.',
            '- cta: return an empty string - festive greetings have no call to action.',
        ]
        from .festive import parse_festive_details

        provided = parse_festive_details(prompt_brief)
        if provided.get('greeting') or provided.get('wish'):
            role_lines.append(
                'The admin has already written part of this wording and it is used exactly as written, so do not '
                'rewrite it: ' + '; '.join(
                    f'{name} = "{provided[key]}"' for key, name in (('greeting', 'greeting'), ('wish', 'wish'))
                    if provided.get(key)
                ) + '. Only write the fields they did not provide.'
            )
    else:
        role_lines = [
            # Matches the fixed layout system's typography hierarchy (see compositor) - each
            # field has a distinct, non-overlapping job.
            'This copy fills a premium editorial layout with a strict typographic hierarchy - write '
            'each field to match its exact role, not just a variation of the same sentence:',
            '- eyebrow: a very short (1-4 word) small-caps kicker/label above the headline, e.g. "THE" '
            'or a short category/campaign label.',
            '- headline: the single large, high-impact statement - short, punchy, the main hook.',
            '- description: 1-2 short sentences of supporting copy beneath the headline.',
            '- cta: a short, understated call to action (2-4 words).',
        ]
    if describes_scene(prompt_brief):
        role_lines.append(
            '- visual_scene: rewrite the creative brief as ONE clear, concrete English description of the picture an '
            'image model should draw (20-60 words): the main subject, the setting, what is happening, the light. Fix '
            'any spelling, and spell out place, festival and insider references as what they look like - for example '
            '"Ganesh visarjan in the sea like Lalbaugcha Raja" becomes "a very large, grand Ganesha idol with a tall '
            'golden crown, decorated with marigold garlands, being immersed into the open sea, waves rising around '
            'it, devotees in the shallow water, golden evening light". Describe only what is visible: no instructions, '
            'no festival or brand names, no mention of text or logos.'
        )
    else:
        role_lines.append('- visual_scene: return an empty string.')
    lines = [
        f'Write the copy for {format_guidance} for "{company.name}".',
        platform_guidance,
        *role_lines,
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
