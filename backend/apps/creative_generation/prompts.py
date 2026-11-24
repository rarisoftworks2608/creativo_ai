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

from .creative_types import (
    ANNOUNCEMENT_CATEGORIES, DESIGN_STYLES, FESTIVALS, SPECS, STORY_OBJECTIVES, festival_name, orientation, picture_look,
)

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


# Greetings and testimonials are warm and bright; every other creative gets the dark, rich luxury look of a premium
# tech or business poster (deep tones, luminous accent light), unless the brand's own style asks for light.
LIGHT_LOOK_TYPES = ('festival_creative', 'testimonial_creative')
# Only a style that is itself described as light-filled counts: "bright orange" or "soft tones" are accents, not a mood.
LIGHT_STYLE_WORDS = ('airy', 'pastel', 'high-key', 'light-filled', 'light and bright', 'bright and light', 'bright and airy')
LOOKS = {
    'dark': {
        'light': 'luminous accent light and deep soft shadows',
        'finish': 'a dark, rich, low-key luxury grade - deep near-black and the brand\'s darkest tone lit by luminous '
                  'accent light, glowing edges and glossy reflections, dramatic yet refined, with calm dark areas',
        'copy': 'rich, low-key light - a deep, dark luxury grade lit by luminous accent light and glowing reflections',
    },
    'light': {
        'light': 'warm golden light with long soft shadows',
        'finish': 'bright, airy and never dark or moody',
        'copy': 'warm, bright, airy light (never dark or moody)',
    },
}


def look_for(creative_type, brand_profile=None):
    """'dark' or 'light': the look of the picture. Business creatives are dark and rich, like a premium poster;
    greetings and testimonials, and brands whose own visual style asks for a bright one, are light."""
    if creative_type in LIGHT_LOOK_TYPES:
        return 'light'
    style = str(getattr(brand_profile, 'visual_style', '') or '').lower()
    return 'light' if any(word in style for word in LIGHT_STYLE_WORDS) else 'dark'


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


def _composition_sentence(composition='bottom'):
    """Which part of the frame is left calm for the text and the logo: 'bottom' (the default), 'top', 'left' or
    'right'. The creative's layout then follows the picture (art_direction.py), so each variation is composed
    differently, not poured into one template. The top-right corner always stays calm - the logo sits there.

    The calm areas are real surfaces of the scene (a sunlit wall, soft drapes, a polished floor), never an empty
    gradient: an instruction to leave space "clear" makes image models draw one object on a blank backdrop. The
    8% margin is because the portrait picture is centre-cropped to 4:5."""
    if composition == 'top':
        return (
            'Composition: the main subject and all of its decor sit in the lower 60% of the frame, within the '
            'centre 8-92% of its height. The top 40% is only a calm, evenly lit wall, sky or soft background with '
            'gentle light and shadow, with nothing hanging into it, the top-right corner included.'
        )
    if composition in ('left', 'right'):
        subject_side, calm_side = ('right', 'left') if composition == 'left' else ('left', 'right')
        corner = 'The top-right corner is part of this calm area. ' if calm_side == 'right' else 'The top-right corner stays calm too. '
        return (
            f'Composition: the main subject and all of its decor sit in the {subject_side} 55% of the frame, within the '
            f'centre 8-92% of its height. The {calm_side} 45% of the frame is calm: a softly lit wall, soft drapes or an '
            f'out-of-focus background with gentle light and shadow, with nothing standing in it. {corner}'.rstrip()
        )
    return (
        'Composition: the main subject and all of its decor sit in the upper 60% of the frame, within the centre '
        '8-92% of its height. The lowest 40% shows only the smooth, softly lit floor or ground in front of the scene, '
        'with gentle reflections and nothing standing on it; the top-right corner stays calm, a softly lit part of '
        'the background wall or sky.'
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
            f'Brand palette: {", ".join(colors)} - these are the dominant colours of the picture (walls, surfaces, '
            'decor, light); no strong colours outside it.'
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
    extra_guidance='', scene_description='', composition='bottom', brief_fields=None, design_style='', aspect_ratio='',
    series_look='', slide_label='',
):
    """A full, richly detailed scene for the calendar entry, in the brand's palette and visual style.

    `scene_description` is the brief rewritten by the text AI as a clear visual description (see
    build_copy_prompt); the raw brief - often misspelt and full of "create a ... for" - is only the
    fallback. `composition` adds one rule: which part of the frame (bottom, top, left or right) stays calm for
    the text, with the top-right corner, where the logo goes, calm too.

    The prompt is written in purely visual, positive terms. The words text / lettering / logo /
    caption are kept out of it: image models, FLUX especially, tend to paint any such word into the
    picture - "do not draw text" is the surest way to get text. The compositor draws the real text
    and logo afterwards.
    """
    scene = (scene_description or '').strip() or _scene_from_brief(prompt_brief)
    # The image model paints any name it is given onto a screen, a notebook or a sign (and misspells it): the brand's
    # name never goes into the picture prompt - the real logo is composited afterwards.
    name = (getattr(company, 'name', '') or '').strip()
    if name:
        scene = re.sub(re.escape(name), '', scene, flags=re.IGNORECASE)
        scene = re.sub(r'\s{2,}', ' ', scene).strip(' ,')
    look = LOOKS[picture_look(creative_type, design_style) or look_for(creative_type, brand_profile)]
    mood = TYPE_MOOD.get(creative_type, '') if creative_type != 'testimonial_creative' else ''
    frame = _frame_phrase(aspect_ratio)
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
        f'A premium editorial advertising photograph, {frame}: {scene[:600].rstrip(" .")}.' if scene else
        f'A premium editorial advertising photograph, {frame}, that suits the brand and its audience.',
        'A complete, richly detailed environment fills the whole frame edge to edge, never one object on an empty '
        'backdrop: a real place with depth - a framing element in the foreground (architecture, foliage or decor), a '
        f'clear focal subject in the middle ground, and a distant background with atmosphere (a skyline, a landscape or '
        f'interior depth) under {look["light"]}. Wide cinematic composition, photorealistic, '
        'ultra-high-resolution full-frame 50mm photograph with crisp fine detail and natural deep focus (nothing '
        f'smeared into bokeh), true-to-life materials, a refined luxurious finish, {look["finish"]}.',
    ]
    if mood:
        lines.append(f'Mood and styling: {mood}.')
    # The layout needs come before the brand lines: a provider with a short prompt limit (Cloudflare
    # FLUX, 2048) cuts from the end, and the calm areas for the text and logo matter most after the scene.
    lines.append(_composition_sentence(composition))
    crop_line = _crop_safety_sentence(aspect_ratio)
    if crop_line:
        lines.append(crop_line)
    brand_lines = _brand_style_lines(brand_profile)
    # The palette first, then this creative type's own direction and the design style, then the rest of the brand:
    # a provider that cuts long prompts keeps the most important lines.
    lines += brand_lines[:1]
    if series_look:
        lines.append(f'{slide_label or "This slide"} of one carousel series - every slide shares this look: '
                     f'{series_look.strip()[:350]}.')
    lines += type_picture_lines(creative_type, brief_fields)
    style_line = _style_line(design_style)
    if style_line:
        lines.append(style_line)
    lines += brand_lines[1:]
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
    calendar_item=None, brief_fields=None, design_style='', aspect_ratio='',
):
    format_guidance = CREATIVE_TYPE_GUIDANCE.get(creative_type, 'a social media creative')
    platform_guidance = PLATFORM_GUIDANCE.get(platform, PLATFORM_GUIDANCE['general'])
    look_phrase = LOOKS[picture_look(creative_type, design_style) or look_for(creative_type, brand_profile)]['copy']
    role_lines = [
        # Matches the fixed layout system's typography hierarchy (see compositor) - each
        # field has a distinct, non-overlapping job.
        'This copy fills a premium editorial layout with a strict typographic hierarchy - write '
        'each field to match its exact role, not just a variation of the same sentence:',
        '- eyebrow: a very short kicker above the headline - a category or campaign label of 1-4 words, or up to '
        'three keywords separated by " / " (for example "Strategy / Technology / Growth").',
        '- headline: the single large, high-impact statement - short and punchy, at most 8 words, as one line or as '
        'two short parallel sentences ("Ideas Into Innovation. Technology Into Growth."). The word that closes the '
        'headline - and each of its sentences - is set in emphasis, so end each on the word that carries the idea '
        '("Building Tomorrow\'s Businesses, Today").',
        '- description: ONE short sentence (at most 12 words) of supporting copy beneath the headline, set in small '
        'widely spaced capitals like a sub-line ("Modern solutions for a smarter tomorrow.").',
        '- cta: a short, understated call to action (2-4 words).',
        '- highlights: for a business, product, event or announcement creative, 3 or 4 of the company\'s services or '
        'strengths as labels of 1-3 words each, taken from the company services listed below ("Web Development", '
        '"ERP Solutions", "AI & Automation"); an empty array for a greeting or a testimonial.',
        '- tagline: a 2-5 word sign-off for the company shown in the footer ("Your Technology Partner"); an empty '
        'string for a greeting or a testimonial.',
        'If the brief or calendar entry is a greeting for a festival or occasion, write a greeting, not a sales '
        'pitch: the eyebrow a short greeting word ("Happy", "Wishing you a"), the headline the occasion\'s name, the '
        'description one warm line in the brand voice, and cta an empty string.',
        '- visual_scene: ONE clear, concrete English description (40-80 words) of the finished picture an image '
        'model should draw for this brief - a cinematic, location-based, richly detailed scene built in layers: a '
        'real place with a clear focal subject (a person seen naturally from behind, a building, a product in '
        f'context), a framing element in the foreground and real depth behind, with {look_phrase}, in the brand\'s '
        'visual style and colour palette. Never a lone object on an empty or '
        'gradient background and never a tabletop still life of small objects. Set it in a world that suits the '
        'business and its audience (for a property brand, a refined modern entrance or living space with real wood, '
        'stone and glass, dressed with the occasion\'s decor and warm sun falling across a wall; for a corporate or '
        'events brand, a real venue such as a skyline terrace, a grand hall or an architectural lobby at golden '
        'hour; for a software, digital or marketing brand, a dark polished stone podium ringed by a thin glowing line '
        'of light carrying a laptop with an abstract dashboard on its screen, translucent glass panels of abstract '
        'charts and simple glyph icons floating around it, in front of floor-to-ceiling windows over a city '
        'skyline at dusk; for a food brand, a beautifully laid table) so the picture feels made for this brand, not '
        'generic. Every screen, panel, book and object in the scene shows only abstract charts and shapes, never '
        'any writing, numbers or brand marks. '
        'Follow the creative brief and the calendar entry exactly, fix any spelling, and ignore anything in the '
        'brief about layout, typography, text, logos, alignment or website design - describe only the photograph. '
        'Spell out place, festival and insider references as what they look like - for example "Ganesh visarjan in '
        'the sea like Lalbaugcha Raja" becomes "a very large, grand Ganesha idol with a tall golden crown, decorated '
        'with marigold garlands, being immersed into the open sea, waves rising around it, devotees in the shallow '
        'water, golden evening light". Describe only what is visible: no instructions, no festival or brand '
        'names, no mention of text, letters or logos.',
    ]
    lines = [
        f'Write the copy for {format_guidance} for "{company.name}"'
        + (f' (industry: {company.industry}).' if company.industry else '.'),
        platform_guidance,
        *role_lines,
        f'Creative brief: {prompt_brief or "Use your best judgement."}',
        *_calendar_lines(calendar_item),
        *type_copy_lines(creative_type, brief_fields, design_style),
        f'Product information: {product_info or _joined(company.products, empty="not specified")}',
    ]
    services = [str(s)[:60] for s in (company.services or [])[:8] if s]
    if services:
        lines.append(f'Company services: {"; ".join(services)}')
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


# --------------------------------------------------------------------------- the creative-type systems

FRAME_PHRASES = {
    '1:1': 'square 1:1', '4:5': 'portrait 4:5', '1.91:1': 'wide landscape 1.91:1', '9:16': 'tall vertical 9:16',
}


def _frame_phrase(aspect_ratio):
    return FRAME_PHRASES.get(aspect_ratio or '4:5', 'portrait 4:5')


def _crop_safety_sentence(aspect_ratio):
    """Some image providers can only draw one size: the picture is then centre-cropped to the creative's frame, so
    the subject must sit where that crop keeps it."""
    shape = orientation(aspect_ratio) if aspect_ratio else 'portrait'
    if shape == 'vertical':
        return ('Frame: a tall vertical phone-screen composition; keep the main subject within the centre 56% of the '
                'frame width, with calm sky, wall or floor above and below it.')
    if shape == 'landscape':
        return ('Frame: a wide landscape composition; keep the main subject within the centre 50% of the frame height, '
                'with room to the side of it.')
    if shape == 'square':
        return 'Frame: a square composition; keep the main subject within the centre 80% of the frame.'
    return ''


def _festival_lines(fields):
    key = fields.get('festival', '')
    name = festival_name(fields)
    if key in FESTIVALS:
        imagery = FESTIVALS[key][1]
    elif name:
        imagery = (f'the traditional imagery, symbols, colours and lighting of {name}, depicted accurately and '
                   'respectfully')
    else:
        imagery = "the occasion's traditional decor, symbols and lighting"
    return [
        f'Occasion imagery: {imagery}.',
        'The occasion is the primary visual context; the brand colours appear only as subtle accents. No unrelated '
        'decorations and no excess of festive elements; cultural and religious symbols are accurate and respectful.',
    ]


def type_picture_lines(creative_type, fields=None):
    """What this creative type's picture has to be, in visual terms - the image prompt's type direction."""
    fields = fields or {}
    spec = SPECS.get(creative_type)
    if spec is None:
        return []
    lines = [f'This picture is {spec.picture}.'] if creative_type != 'carousel' else []
    if creative_type == 'story':
        objective = STORY_OBJECTIVES.get(fields.get('objective', ''))
        if objective:
            lines.append(f'Scene for this story: {objective[2]}.')
    elif creative_type == 'festival_creative':
        lines += _festival_lines(fields)
    elif creative_type == 'announcement_creative':
        category = ANNOUNCEMENT_CATEGORIES.get(fields.get('category', ''), ANNOUNCEMENT_CATEGORIES['custom'])
        lines.append(f'Visual direction for this announcement: {category[2]}.')
    return lines


def _style_line(design_style):
    style = DESIGN_STYLES.get(design_style)
    return f'Design style: {style.image}.' if style else ''


def _supplied_lines(creative_type, fields):
    """The person's own inputs for this creative, labelled - the copy must follow them exactly."""
    labels = {
        'topic': 'Topic', 'headline': 'Headline (use exactly as written)',
        'supporting_text': 'Supporting text (use exactly as written)', 'cta': 'Call to action (use exactly as written)',
        'objective': 'Content objective', 'outline': 'Content outline', 'tone': 'Tone',
        'message': 'Greeting message (use exactly as written)', 'year': 'Year', 'audience': 'Target audience',
        'label': 'Announcement label (use exactly as written)', 'title': 'Announcement title (use exactly as written)',
        'description': 'Announcement details (use exactly as written)', 'date': 'Date / time (use exactly as written)',
    }
    lines = []
    for key in SPECS[creative_type].fields:
        value = fields.get(key)
        if not value or key in ('festival', 'festival_name', 'category', 'quote', 'customer_name', 'company',
                                'designation', 'rating', 'allow_shorten'):
            continue
        if creative_type == 'story' and key == 'objective':
            value = STORY_OBJECTIVES.get(value, (value,))[0]
        lines.append(f'- {labels.get(key, key)}: {value}')
    return lines


def type_copy_lines(creative_type, fields=None, design_style=''):
    """The type's own copy rules and the person's inputs - added to the copy prompt for the six creative types."""
    fields = fields or {}
    spec = SPECS.get(creative_type)
    if spec is None:
        return []
    lines = ['', f'CREATIVE TYPE: {spec.label} - {spec.purpose}.', *spec.copy_rules]
    if spec.hierarchy:
        lines.append(f'Visual hierarchy of the finished creative: {" > ".join(spec.hierarchy)}.')
    if creative_type == 'story':
        objective = STORY_OBJECTIVES.get(fields.get('objective', ''))
        if objective:
            lines.append(f'This is {objective[1]}.')
    elif creative_type == 'festival_creative':
        name = festival_name(fields)
        if name:
            year = f' {fields["year"]}' if fields.get('year') else ''
            lines.append(f'Occasion: {name}{year}. Greet the audience for {name}; the brand complements the occasion '
                         'and never overpowers it.')
    elif creative_type == 'announcement_creative':
        category = ANNOUNCEMENT_CATEGORIES.get(fields.get('category', ''), ANNOUNCEMENT_CATEGORIES['custom'])
        lines.append(f'Announcement category: {category[0]}. Only the details supplied below are facts - do not '
                     'add dates, prices, places or names.')
    elif creative_type == 'testimonial_creative':
        lines.append(f'Client quote (verbatim): "{fields.get("quote", "")}"')
        if fields.get('allow_shorten'):
            lines.append('headline: the quote, shortened to at most 30 words ONLY by removing words - keep its exact '
                         'meaning and the client\'s own wording, add nothing.')
        else:
            lines.append('headline: the quote exactly as supplied.')
        lines.append('eyebrow, description and cta are set by the system - return them as empty strings. The '
                     'caption may introduce the review but must not invent details about the client.')
    supplied = _supplied_lines(creative_type, fields)
    if supplied:
        lines += ['Supplied content (follow it; text marked "use exactly as written" goes into its field unchanged):',
                  *supplied]
    lines.append(f'For the visual_scene: the picture must be {spec.picture if creative_type != "carousel" else "one slide of a consistent series"}.')
    for line in type_picture_lines(creative_type, fields)[1:]:
        lines.append(f'For the visual_scene: {line}')
    style_line = _style_line(design_style)
    if style_line:
        lines.append(f'{style_line} Let it shape the copy\'s tone too.')
    return lines


def build_carousel_prompt(
    company, brand_profile, brand_context, platform, prompt_brief, product_info, *, brief_fields, slide_count,
    design_style='', extra_guidance='', calendar_item=None,
):
    """One request for the whole carousel: the series look shared by every slide and, per slide, its role, copy and
    picture - so the slides read as one story and one visual system."""
    fields = brief_fields or {}
    base = build_copy_prompt(
        company, brand_profile, brand_context, 'carousel', platform, prompt_brief, product_info,
        extra_guidance=extra_guidance, calendar_item=calendar_item, brief_fields=fields, design_style=design_style,
    )
    outline = [line.strip() for line in (fields.get('outline') or '').splitlines() if line.strip()]
    cta_note = f' (use exactly: {fields["cta"]})' if fields.get('cta') else ''
    lines = [
        base,
        '',
        f'CAROUSEL PLAN: write exactly {slide_count} slides in "slides", in order.',
        '- Slide 1 role "cover": the hook - the strongest headline of the series (at most 8 words) and a short '
        'subtitle in "body" (at most 8 words).',
        f'- Slides 2 to {slide_count - 1} role "content": each ONE specific idea (a problem, tip, benefit, step, '
        'feature or example), a short headline (at most 7 words) and at most one short sentence in "body". No two '
        'slides make the same point.',
        f'- Slide {slide_count} role "cta": the conclusion or summary as the headline and the call to action in "cta"'
        f'{cta_note}.',
        '- series_look: ONE description (30-60 words) of the visual world every slide shares - the setting, palette '
        'from the brand colours, lighting, lens and grade - so the slides look like one photographed series.',
        '- per slide visual_scene: what THIS slide shows inside that shared world (30-60 words), varied from slide to '
        'slide in subject and framing so no two slides look alike. Describe only the photograph: no text, letters, '
        'logos, numbers or screens with writing.',
        '- caption, hashtags and keywords are for the whole carousel post.',
    ]
    if outline:
        lines.append('Use this outline for the slides\' content. Lines written as slide text keep their wording for '
                     'the headlines and body; lines written as instructions ("create...", "show...") are direction '
                     'only - never copy an instruction onto a slide:')
        lines += [f'  {index}. {line}' for index, line in enumerate(outline, start=1)]
    return '\n'.join(lines)
