"""Prompt assembly for Epic 06 (AI Creative Generation).

Brand-Aware Generation: every prompt below is grounded in the company's
brand profile (Epic 03) and, when available, the synthesized brand context
(Epic 05) - colors, logo, tone, typography, visual style and product
information all flow into both the image prompt and the copy prompt.

Every creative is a full, richly detailed scene built from the calendar entry's instructions (the
brief) and the brand guidelines - never a plain backdrop with one object on it. The brand alignment
template (layouts.py) only decides which part of the scene is kept calm for the text and the logo.
"""

import re

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

# The mood and styling each type calls for, in purely visual terms (no words that suggest
# lettering - see build_image_prompt for why).
TYPE_MOOD = {
    'festival_creative': 'a warm, celebratory mood dressed with the occasion\'s traditional decor, symbols and lighting',
    'promotional_creative': 'bold, energetic and eye-catching, with a clear focal subject that suits the offer',
    'product_creative': 'the product shown whole and in sharp focus, in an appealing real-world setting',
    'educational_creative': 'clear, simple and approachable, with a visual metaphor that illustrates the idea',
    'event_creative': 'exciting and inviting, evoking the atmosphere of the occasion',
    'announcement_creative': 'polished and confident, with a symbolic subject that suits the news',
    'testimonial_creative': 'warm, friendly and trustworthy, with natural, smiling people',
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


# Fallback for when the text AI did not supply a visual description: the calendar brief itself, minus
# the "create a ... for" instruction at the start and the CTA sentence (a CTA is wording, not a picture).
_INSTRUCTION_RE = re.compile(
    r'^\s*(please\s+)?(create|make|generate|design|prepare)\s+(me\s+)?(a\s+|an\s+|the\s+)?'
    r'((realistic|premium|beautiful|stunning|high[- ]quality|real)\s+)*'
    r'(creative|post|image|picture|poster|banner|visual|photo)\s+(for|of|about|on|with)\s+',
    re.IGNORECASE,
)
_CTA_SENTENCE_RE = re.compile(r'Include the CTA\s+"[^"]*"\.?', re.IGNORECASE)


def _scene_from_brief(brief):
    text = _INSTRUCTION_RE.sub('', (brief or '').strip(), count=1)
    text = _CTA_SENTENCE_RE.sub('', text)
    return re.sub(r'\s+', ' ', text).strip(' .,')


def _composition_sentence(placement):
    if placement == 'top':
        return (
            'Composition: the main subject sits in the lower-middle of the frame, and the top 40% of the frame eases '
            'into a calm, softly lit, uncluttered part of the same scene (open sky, a quiet wall or an out-of-focus '
            'backdrop - whatever suits it).'
        )
    return (
        'Composition: the main subject sits in the upper-middle of the frame, and the lowest 35% of the frame eases '
        'into a calm, softly lit, uncluttered part of the same scene (soft ground, water, sky or an out-of-focus '
        'backdrop - whatever suits it); the top-right corner is calm and uncluttered too.'
    )


def _brand_style_lines(brand_profile):
    """The brand guidelines as the image model should honour them: palette, visual style, tone, do's and
    don'ts - each capped so the whole prompt stays within the smallest provider limit (Cloudflare FLUX, 2048)."""
    if brand_profile is None:
        return []
    lines = []
    colors = [c['hex'] for c in (getattr(brand_profile, 'brand_colors', None) or []) if c.get('hex')][:4]
    if colors:
        lines.append(
            f'Brand palette: {", ".join(colors)} - let it guide the colour grade, lighting, props and surfaces so the '
            'whole picture feels on-brand.'
        )
    if (brand_profile.visual_style or '').strip():
        lines.append(f'Brand visual style: {brand_profile.visual_style.strip()[:250]}.')
    if (brand_profile.tone or '').strip():
        lines.append(f'Brand mood: {brand_profile.tone.strip()[:120]}.')
    dos = [d for d in (brand_profile.dos or []) if d][:4]
    donts = [d for d in (brand_profile.donts or []) if d][:4]
    if dos:
        lines.append(f'Brand do\'s: {"; ".join(str(d)[:80] for d in dos)}.')
    if donts:
        lines.append(f'Brand don\'ts: {"; ".join(str(d)[:80] for d in donts)}.')
    return lines


def build_image_prompt(
    company, brand_profile, creative_type, platform, prompt_brief, product_info, variation_number, variation_count=3,
    extra_guidance='', scene_description='',
):
    """A full, richly detailed scene for the calendar entry, in the brand's palette and visual style.

    `scene_description` is the brief rewritten by the text AI as a clear visual description (see
    build_copy_prompt); the raw brief - often misspelt and full of "create a ... for" - is only the
    fallback. The brand alignment template (layouts.py) adds one composition rule: the part of the
    frame where the text goes, and the top-right corner where the logo goes, stay calm.

    The prompt is written in purely visual, positive terms. The words text / lettering / logo /
    caption are kept out of it: image models, FLUX especially, tend to paint any such word into the
    picture - "do not draw text" is the surest way to get text. The compositor draws the real text
    and logo afterwards.
    """
    from .layouts import layout_for

    scene = (scene_description or '').strip() or _scene_from_brief(prompt_brief)
    mood = TYPE_MOOD.get(creative_type, '')
    variation_note = (
        f'This is variation {variation_number} of {variation_count} - make it visually distinct from the '
        'other variations while staying on-brand.'
        if variation_count > 1 else
        'Make this the single best possible on-brand variation.'
    )
    context = (product_info or '').strip()[:200]
    if not context and creative_type == 'product_creative':
        context = ', '.join(str(p) for p in (company.products or [])[:3])

    lines = [
        f'A premium, professionally photographed scene, portrait 4:5: {scene[:700].rstrip(" .")}.' if scene else
        'A premium, professionally photographed scene, portrait 4:5, that suits the brand and its audience.',
        'A complete, richly detailed environment fills the whole frame edge to edge, with depth, layered foreground and '
        'background, true-to-life materials and natural cinematic light. Photorealistic and razor-sharp, with the main '
        'subject large and clear.',
    ]
    if mood:
        lines.append(f'Mood and styling: {mood}.')
    # The layout needs come before the brand lines: a provider with a short prompt limit (Cloudflare
    # FLUX, 2048) cuts from the end, and the calm areas for the text and logo matter most after the scene.
    lines.append(_composition_sentence(layout_for(creative_type)['placement']))
    lines += _brand_style_lines(brand_profile)
    if context:
        lines.append(f'Also: {context}')
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


def _calendar_lines(calendar_item):
    """The planning details of the content calendar entry this creative is for (objective, campaign,
    theme, date) - the instruction the creative has to follow. Nothing for an ad-hoc generation, whose
    only "entry" is the brief itself."""
    from apps.content_calendar.models import ContentCalendarItem

    if calendar_item is None or calendar_item.source == ContentCalendarItem.Source.AD_HOC:
        return []
    details = [
        ('Category', calendar_item.category),
        ('Weekly theme', calendar_item.weekly_theme),
        ('Objective', calendar_item.objective),
        ('Campaign', calendar_item.campaign),
        ('Scheduled for', f'{calendar_item.scheduled_date:%d %B %Y}'),
    ]
    return ['Content calendar entry (follow it closely):', *(f'- {name}: {value}' for name, value in details if value)]


def build_copy_prompt(
    company, brand_profile, brand_context, creative_type, platform, prompt_brief, product_info, extra_guidance='',
    calendar_item=None,
):
    format_guidance = CREATIVE_TYPE_GUIDANCE.get(creative_type, 'a social media creative')
    platform_guidance = PLATFORM_GUIDANCE.get(platform, PLATFORM_GUIDANCE['general'])
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
        '- visual_scene: ONE clear, concrete English description (30-70 words) of the finished picture an image '
        'model should draw for this brief - a full, richly detailed scene: the main subject, the setting and '
        'background, props, what is happening, the light and the mood, in the brand\'s visual style and colour '
        'palette. Follow the creative brief and the calendar entry exactly, fix any spelling, and spell out place, '
        'festival and insider references as what they look like - for example "Ganesh visarjan in the sea like '
        'Lalbaugcha Raja" becomes "a very large, grand Ganesha idol with a tall golden crown, decorated with '
        'marigold garlands, being immersed into the open sea, waves rising around it, devotees in the shallow '
        'water, golden evening light". Describe only what is visible: no instructions, no festival or brand '
        'names, no mention of text, letters or logos.',
    ]
    lines = [
        f'Write the copy for {format_guidance} for "{company.name}".',
        platform_guidance,
        *role_lines,
        f'Creative brief: {prompt_brief or "Use your best judgement."}',
        *_calendar_lines(calendar_item),
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
