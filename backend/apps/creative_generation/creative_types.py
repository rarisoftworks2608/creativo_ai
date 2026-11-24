"""The six creative types as six distinct creative systems.

Every creative goes through the same pipeline (copy -> picture -> composited text and logo, see tasks.py), but each
type brings its own purpose, inputs, copy rules, picture direction, default size and typography. This module is
the single place that knows those differences, so prompts.py, tasks.py, the compositor and the API all read from it
instead of sprinkling `if creative_type == ...` around.

Text the person typed (a headline, a testimonial quote, an announcement title, a date) is never rewritten by the
AI: `locked_copy` puts it on the creative exactly as written, and the AI only writes the fields left blank.
Nothing that identifies a real person or a real fact (a customer name, a rating, a date) is ever invented.
"""

from dataclasses import dataclass, field

# --------------------------------------------------------------------------- sizes

# height / width of each supported aspect ratio, and its pixel size at 1080 wide.
ASPECT_RATIOS = {
    '1:1': {'label': 'Square 1:1', 'aspect': 1.0, 'size': (1080, 1080)},
    '4:5': {'label': 'Portrait 4:5', 'aspect': 1.25, 'size': (1080, 1350)},
    '1.91:1': {'label': 'Landscape 1.91:1', 'aspect': 1 / 1.91, 'size': (1080, 566)},
    '9:16': {'label': 'Vertical 9:16', 'aspect': 16 / 9, 'size': (1080, 1920)},
}


def aspect_value(ratio):
    """height / width for an aspect ratio key ('4:5' when unknown)."""
    return ASPECT_RATIOS.get(ratio, ASPECT_RATIOS['4:5'])['aspect']


def orientation(ratio):
    aspect = aspect_value(ratio)
    if aspect > 1.4:
        return 'vertical'
    if aspect > 1.05:
        return 'portrait'
    if aspect < 0.95:
        return 'landscape'
    return 'square'


# --------------------------------------------------------------------------- design styles

@dataclass(frozen=True)
class DesignStyle:
    label: str
    image: str            # photographic direction for the picture
    look: str | None      # 'dark' / 'light' picture grade, or None to keep the type's default
    presets: tuple        # typography presets (art_direction.STYLE_PRESETS) that express the style


DESIGN_STYLES = {
    'premium': DesignStyle(
        'Premium', 'refined premium art direction: considered composition, rich true-to-life materials, '
        'controlled soft key light', None, ('web_editorial', 'quiet_luxury', 'editorial_serif'),
    ),
    'minimal': DesignStyle(
        'Minimal', 'minimal art direction: one subject, generous calm negative space, few props, clean '
        'surfaces, soft even daylight', 'light', ('modern_caps', 'quiet_luxury'),
    ),
    'luxury': DesignStyle(
        'Luxury', 'luxury art direction: opulent materials (marble, brass, velvet, glass), glossy highlights, '
        'deep shadows and a sumptuous finish', 'dark', ('gold_serif', 'quiet_luxury', 'editorial_serif'),
    ),
    'corporate': DesignStyle(
        'Corporate', 'corporate art direction: modern architecture, glass and steel, orderly composition, '
        'confident professional people, crisp daylight', None, ('modern_caps', 'serif_caps', 'web_editorial'),
    ),
    'modern': DesignStyle(
        'Modern', 'contemporary art direction: clean geometry, bold simple shapes in the scene, fresh light, '
        'a current design-led setting', None, ('modern_caps', 'web_editorial'),
    ),
    'bold': DesignStyle(
        'Bold', 'bold art direction: strong saturated brand colour, high contrast, a big confident focal '
        'subject filling the frame, punchy light', None, ('bold_sans', 'modern_caps'),
    ),
    'editorial': DesignStyle(
        'Editorial', 'magazine editorial art direction: a story-telling photograph, natural light, '
        'considered styling, the feel of a premium print feature', None, ('web_editorial', 'editorial_serif'),
    ),
    'cinematic': DesignStyle(
        'Cinematic', 'cinematic art direction: a wide film-still composition, dramatic directional light, '
        'atmospheric haze and depth, a filmic colour grade', 'dark', ('serif_caps', 'web_editorial'),
    ),
    'playful': DesignStyle(
        'Playful', 'playful art direction: bright cheerful colour, lively candid moments, a fun, warm '
        'and energetic scene', 'light', ('bold_sans', 'modern_caps'),
    ),
    'festive': DesignStyle(
        'Festive', 'festive art direction: celebratory decor, warm glowing lights, rich textures and a joyful '
        'occasion mood', 'light', ('gold_serif', 'editorial_serif', 'web_editorial'),
    ),
    'elegant': DesignStyle(
        'Elegant', 'elegant art direction: graceful composition, soft natural light, delicate details and a '
        'restrained, sophisticated palette', 'light', ('quiet_luxury', 'editorial_serif', 'web_editorial'),
    ),
}


# --------------------------------------------------------------------------- options per type

STORY_OBJECTIVES = {
    'promotional': ('Promotional', 'a promotional story: one bold offer-led message', 'an energetic, eye-catching scene that sells the offer'),
    'service_highlight': ('Service highlight', 'a story that spotlights one service and its single biggest benefit', 'the service being delivered or its result, shown in a real setting'),
    'lead_generation': ('Lead generation', 'a story that invites viewers to get in touch, book or sign up', 'an inviting, human scene that makes reaching out feel easy'),
    'poll_question': ('Poll / question', 'a story that asks the audience one short, engaging question', 'a simple, uncluttered scene with a large calm middle area where a poll sticker can sit'),
    'event_reminder': ('Event reminder', 'a story reminding viewers of an upcoming event', 'the atmosphere of the event venue or occasion'),
    'offer': ('Offer', 'a story announcing a limited-time offer', 'the product or service as the hero, crisp and desirable'),
    'brand_awareness': ('Brand awareness', 'a story that expresses what the brand stands for', 'an aspirational lifestyle scene that captures the brand world'),
    'countdown': ('Countdown / launch', 'a story building anticipation for something coming soon', 'a dramatic, suspenseful reveal scene with a strong focal point'),
}

ANNOUNCEMENT_CATEGORIES = {
    'product_launch': ('New product launch', 'NEW PRODUCT', 'the new product as the hero subject, beautifully lit in a real setting that suits it'),
    'service_launch': ('New service launch', 'NEW SERVICE', 'the new service being delivered, or its outcome, in a real professional setting'),
    'milestone': ('Company milestone', 'MILESTONE', 'a celebratory, accomplished scene: the team or workplace at a proud moment'),
    'expansion': ('Business expansion', 'WE ARE GROWING', 'a forward-looking scene of growth: new premises, a skyline, a busy modern workplace'),
    'opening': ('New branch / opening', 'NOW OPEN', 'the new location itself: a welcoming storefront, entrance or interior ready for opening day'),
    'event': ('Event announcement', 'SAVE THE DATE', 'the atmosphere of the event: the venue, stage or gathering'),
    'partnership': ('Partnership announcement', 'PARTNERSHIP', 'a collaboration-oriented composition: two teams meeting, a handshake in a modern office'),
    'achievement': ('Achievement / award', 'ACHIEVEMENT', 'a milestone and accomplishment scene: an award moment, a proud team, a summit at golden hour'),
    'hiring': ('Recruitment / hiring', 'WE ARE HIRING', 'the workplace and the people who would be teammates, in a bright modern office'),
    'offer': ('Offer / discount', 'SPECIAL OFFER', 'the product or service on offer as the hero, desirable and inviting'),
    'update': ('Important update', 'IMPORTANT UPDATE', 'a calm, trustworthy scene that suits the business'),
    'custom': ('Custom announcement', 'ANNOUNCEMENT', 'a polished, confident scene that suits the news'),
}

# Occasion -> (display name, the imagery that belongs to it). Respectful, accurate symbolism only.
FESTIVALS = {
    'diwali': ('Diwali', 'elegant lit clay diyas, warm golden light, a subtle rangoli, marigold accents and premium festive decor with rich textures'),
    'holi': ('Holi', 'clouds of vibrant colour powder (gulal) in motion, joyful celebration, bright daylight'),
    'ganesh_chaturthi': ('Ganesh Chaturthi', 'a beautifully adorned Lord Ganesha idol with marigold and hibiscus flowers, traditional decoration and a devotional, reverent atmosphere'),
    'navratri': ('Navratri', 'colourful garba and dandiya celebration, traditional dress, festive lights and rich textiles'),
    'dussehra': ('Dussehra', 'the triumph of good over evil: a festive evening, warm firelight and traditional celebration'),
    'eid': ('Eid', 'a crescent moon in an elegant night sky, glowing lanterns and warm festive lighting'),
    'christmas': ('Christmas', 'a decorated Christmas tree, ornaments and warm fairy lights, with snow only where it suits the setting'),
    'new_year': ('New Year', 'a sparkling midnight celebration: fireworks over a skyline, warm glowing lights and festive cheer'),
    'independence_day': ('Independence Day', 'the Indian tricolour in saffron, white and green, respectful patriotic imagery and a proud, uplifting mood'),
    'republic_day': ('Republic Day', 'the Indian tricolour, respectful national symbolism and a dignified, proud mood'),
    'raksha_bandhan': ('Raksha Bandhan', 'an ornate rakhi, sweets and a warm moment between siblings'),
    'makar_sankranti': ('Makar Sankranti', 'colourful kites against a bright winter sky and festive warmth'),
    'pongal': ('Pongal', 'a decorated clay pot overflowing with pongal, sugarcane, kolam and harvest festivity'),
    'onam': ('Onam', 'an intricate pookalam flower carpet, a traditional sadya and festive Kerala decor'),
    'janmashtami': ('Janmashtami', 'a flute, peacock feathers, butter pots (matki) and devotional festive decor'),
    'gudi_padwa': ('Gudi Padwa', 'a decorated gudi with silk cloth, neem leaves and flowers against a bright morning sky'),
    'easter': ('Easter', 'spring flowers, painted eggs and soft morning light'),
}

TESTIMONIAL_LABEL = 'What our clients say'


# --------------------------------------------------------------------------- the types

@dataclass(frozen=True)
class CreativeTypeSpec:
    key: str
    label: str
    purpose: str                    # what the creative is for, for the copy prompt
    copy_rules: tuple               # extra lines for the copy prompt
    picture: str                    # picture direction for the image prompt
    default_aspect: str = '4:5'
    aspects: tuple = ('1:1', '4:5', '1.91:1')
    fields: tuple = ()              # brief_fields keys this type accepts
    required: tuple = ()            # brief_fields keys this type needs
    look: str | None = None         # default picture grade, before a design style
    presets: tuple = ()             # default typography presets
    framed: bool = True             # may carry the services strip / footer of a business poster
    force_overlay: bool = False     # the text is the creative: always composited
    hierarchy: tuple = field(default_factory=tuple)


SPECS = {
    'post': CreativeTypeSpec(
        key='post', label='Post',
        purpose='a single standalone social media post that communicates ONE clear message',
        copy_rules=(
            'One central idea only. headline: the single message (at most 8 words). description: one supporting '
            'line (at most 14 words). cta: optional, 2-4 words. Minimal text: the picture carries the post.',
        ),
        picture='a single, scroll-stopping hero photograph with one clear focal subject - never a collage, grid, '
                'split screen, multiple panels or a mockup sheet',
        fields=('topic', 'headline', 'supporting_text', 'cta'),
        hierarchy=('headline', 'main visual', 'supporting text', 'CTA', 'branding'),
    ),
    'carousel': CreativeTypeSpec(
        key='carousel', label='Carousel',
        purpose='a multi-slide carousel that tells a story or teaches a topic progressively, one idea per slide',
        copy_rules=(
            'Slide 1 is the cover/hook: the strongest headline and a short subtitle. The middle slides carry one '
            'specific idea each (a problem, tip, benefit, step, feature or example) - a short headline and at most '
            'one short sentence. The last slide is the conclusion and call to action.',
        ),
        picture='one slide of a consistent carousel series',
        aspects=('1:1', '4:5'),
        fields=('topic', 'objective', 'outline', 'cta', 'tone'),
        required=('topic',),
        force_overlay=True,
    ),
    'story': CreativeTypeSpec(
        key='story', label='Story',
        purpose='a vertical, mobile-first Instagram/Facebook Story with ONE message readable at a glance',
        copy_rules=(
            'headline: very short (at most 6 words), readable in one second. description: at most 10 words. '
            'cta: an obvious action of 2-3 words, may end with an arrow. No paragraphs, no lists.',
        ),
        picture='a vertical 9:16 story photograph composed for a tall phone screen: the focal subject in the middle '
                'band, calm areas at the very top and bottom where the app interface sits',
        default_aspect='9:16', aspects=('9:16',),
        fields=('objective', 'headline', 'supporting_text', 'cta'),
        presets=('modern_caps', 'bold_sans', 'web_editorial'),
        framed=False,
    ),
    'festival_creative': CreativeTypeSpec(
        key='festival_creative', label='Festival Creative',
        purpose='a festival / special-occasion greeting where the occasion is the hero and the brand complements it',
        copy_rules=(
            'Write a greeting, not a sales pitch. eyebrow: the greeting line (e.g. "Happy Diwali"). headline: a '
            'short, warm greeting statement (at most 7 words). description: one warm wish in the brand voice. '
            'cta: an empty string. highlights and tagline: empty.',
        ),
        picture='a festival scene where the occasion is the primary visual context',
        fields=('festival', 'festival_name', 'headline', 'message', 'year', 'audience'),
        required=('festival',),
        look='light',
        framed=False,
    ),
    'announcement_creative': CreativeTypeSpec(
        key='announcement_creative', label='Announcement Creative',
        purpose='an official, clear announcement of business news where the announcement headline dominates',
        copy_rules=(
            'The announcement title is the headline and the most prominent element. description: the key details '
            'in one or two short sentences. Never invent facts, dates, prices or names that were not supplied.',
        ),
        picture='a polished, professional scene that directly illustrates the announcement',
        fields=('category', 'label', 'title', 'description', 'date', 'cta'),
        required=('category', 'title'),
        presets=('modern_caps', 'serif_caps', 'web_editorial'),
        force_overlay=True,
    ),
    'testimonial_creative': CreativeTypeSpec(
        key='testimonial_creative', label='Testimonial Creative',
        purpose='a credible, premium testimonial creative where the client quote is the hero',
        copy_rules=(
            'The client quote is supplied and is the headline - never invent or alter a quote, a name, a company, '
            'a designation or a rating. Write only the social caption around it.',
        ),
        picture='a soft, subtle, uncluttered background that keeps every word of a quote readable: a calm, '
                'softly lit interior or texture with gentle light, no people and no busy detail',
        fields=('quote', 'customer_name', 'company', 'designation', 'rating', 'allow_shorten'),
        required=('quote',),
        look='light',
        presets=('testimonial_quote',),
        framed=False,
        force_overlay=True,
    ),
}

# Types the calendar still produces automatically (keyword matching in content_calendar.tasks) but which are no
# longer offered in the creative form: they keep the generic behaviour of a post.
LEGACY_TYPES = (
    'instagram_post', 'facebook_post', 'linkedin_post', 'promotional_creative', 'product_creative',
    'educational_creative', 'event_creative',
)


def spec_for(creative_type):
    return SPECS.get(creative_type) or SPECS['post']


def default_aspect_ratio(creative_type):
    return spec_for(creative_type).default_aspect


def resolve_aspect_ratio(creative_type, requested):
    """The ratio a creative is made at: the requested one when this type allows it, else the type's default."""
    spec = spec_for(creative_type)
    return requested if requested in spec.aspects else spec.default_aspect


def clean_brief_fields(creative_type, data):
    """Only this type's own fields, trimmed; empty values dropped."""
    spec = spec_for(creative_type)
    cleaned = {}
    for key in spec.fields:
        value = (data or {}).get(key)
        if isinstance(value, str):
            value = value.strip()
        if value in (None, '', [], {}):
            continue
        cleaned[key] = value
    return cleaned


def missing_required(creative_type, fields):
    return [key for key in spec_for(creative_type).required if not fields.get(key)]


def festival_name(fields):
    """The occasion's display name: a known festival's name or the custom one typed in."""
    key = fields.get('festival', '')
    if key in FESTIVALS:
        return FESTIVALS[key][0]
    return (fields.get('festival_name') or key or '').strip()


def rating_value(fields):
    """A 1-5 star rating when one was actually supplied, else None (stars are never invented)."""
    try:
        value = int(fields.get('rating') or 0)
    except (TypeError, ValueError):
        return None
    return value if 1 <= value <= 5 else None


def attribution(fields):
    """'Name, Designation, Company' from only the parts that were supplied (plain ASCII separators: the compositor
    drops characters its fonts may not have)."""
    role = ', '.join(part for part in (fields.get('designation', ''), fields.get('company', '')) if part)
    name = fields.get('customer_name', '')
    return ', '.join(part for part in (name, role) if part)


def locked_copy(creative_type, fields):
    """The copy fields the person typed, mapped onto the creative's text roles. These replace whatever the AI
    wrote for the same roles, so the creative shows them exactly as entered."""
    locked = {}
    if creative_type in ('post', 'story'):
        for source, target in (('headline', 'headline'), ('supporting_text', 'description'), ('cta', 'cta')):
            if fields.get(source):
                locked[target] = fields[source]
    elif creative_type == 'festival_creative':
        name = festival_name(fields)
        if name:
            year = fields.get('year', '')
            locked['eyebrow'] = f'Happy {name}{f" {year}" if year else ""}'
        if fields.get('headline'):
            locked['headline'] = fields['headline']
        if fields.get('message'):
            locked['description'] = fields['message']
        locked['cta'] = ''
    elif creative_type == 'announcement_creative':
        category = ANNOUNCEMENT_CATEGORIES.get(fields.get('category', ''), ANNOUNCEMENT_CATEGORIES['custom'])
        label = (fields.get('label') or category[1]).strip()
        date = fields.get('date', '')
        locked['eyebrow'] = f'{label} / {date}' if date else label
        if fields.get('title'):
            locked['headline'] = fields['title']
        if fields.get('description'):
            locked['description'] = fields['description']
        if fields.get('cta'):
            locked['cta'] = fields['cta']
    elif creative_type == 'testimonial_creative':
        locked['eyebrow'] = TESTIMONIAL_LABEL
        if fields.get('quote') and not fields.get('allow_shorten'):
            locked['headline'] = fields['quote']
        locked['description'] = attribution(fields)
        locked['cta'] = ''
        locked['highlights'] = []
        locked['tagline'] = ''
    return locked


def presets_for(creative_type, design_style=''):
    """Typography presets for the type, narrowed by the chosen design style; empty = art_direction's own pools."""
    spec = spec_for(creative_type)
    if creative_type == 'testimonial_creative':
        return spec.presets
    style = DESIGN_STYLES.get(design_style)
    if style is not None:
        return style.presets
    return spec.presets


def picture_look(creative_type, design_style=''):
    """'dark' / 'light' / None (None: prompts.look_for decides from the brand)."""
    style = DESIGN_STYLES.get(design_style)
    if style is not None and style.look and creative_type != 'testimonial_creative':
        return style.look
    return spec_for(creative_type).look


def options_payload():
    """Everything the creative form needs to render each type's inputs - served by the API so the frontend and
    backend never disagree on the options."""
    return {
        'aspect_ratios': [{'value': key, 'label': value['label'], 'size': value['size']} for key, value in ASPECT_RATIOS.items()],
        'design_styles': [{'value': key, 'label': style.label} for key, style in DESIGN_STYLES.items()],
        'story_objectives': [{'value': key, 'label': value[0]} for key, value in STORY_OBJECTIVES.items()],
        'announcement_categories': [{'value': key, 'label': value[0], 'default_label': value[1]} for key, value in ANNOUNCEMENT_CATEGORIES.items()],
        'festivals': [{'value': key, 'label': value[0]} for key, value in FESTIVALS.items()],
        'types': [
            {
                'value': spec.key, 'label': spec.label, 'default_aspect': spec.default_aspect,
                'aspects': list(spec.aspects), 'fields': list(spec.fields), 'required': list(spec.required),
                'force_overlay': spec.force_overlay,
            }
            for spec in SPECS.values()
        ],
        'carousel_slides': {'min': 3, 'max': 10, 'default': 5},
    }
