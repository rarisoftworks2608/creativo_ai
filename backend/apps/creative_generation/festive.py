"""Festival creatives (the "Festive Design Flow" in project_plan.md): reading what the admin wrote.

The admin may fill in the plan's template inside the brief:

    Festival: Diwali
    Main Greeting: Happy Diwali
    Wish/Quote: May this Diwali bring light, joy and new beginnings.
    Festive Element: Elegant golden diya

Whatever is provided there is used exactly as written - the words drawn on the creative are the
admin's own, never an AI rewrite - and only the parts that are missing are filled in by the
copy AI (and, for the element, by the mapping below).
"""

import re

LABELS = (
    'main greeting', 'greeting', 'wish/quote', 'wish / quote', 'wish or quote', 'wish', 'quote',
    'festive element', 'element', 'festival', 'brand logo',
)
LABEL_RE = re.compile(
    r'(?<![A-Za-z])(' + '|'.join(re.escape(label).replace(r'\ ', r'\s+') for label in LABELS) + r')\s*:\s*',
    re.IGNORECASE,
)

FIELD_FOR_LABEL = {
    'main greeting': 'greeting', 'greeting': 'greeting',
    'wish/quote': 'wish', 'wish / quote': 'wish', 'wish or quote': 'wish', 'wish': 'wish', 'quote': 'wish',
    'festive element': 'element', 'element': 'element', 'festival': 'festival',
}

# Words that open a greeting and belong in the small line above the festival name.
GREETING_LEADS = (
    'wishing you a very', 'wishing you a', 'wishing you', 'warm wishes on', 'best wishes on', 'happy', 'merry',
    'joyous', 'blessed', 'shubh',
)

# What to draw as the single central element when the admin did not name one. Described purely
# visually - no festival name and no words that suggest lettering - so the image model has nothing
# to paint as text.
FESTIVAL_ELEMENTS = (
    (r'laxmi|lakshmi|dhanteras', 'a small handcrafted brass idol of Goddess Lakshmi seated on a fresh pink lotus, with gold coins and lotus petals at its base and a softly glowing diya beside it, arranged together as one compact still life'),
    (r'diwali|deepavali|dipavali', 'an elegant golden brass diya with a softly glowing flame, resting on a few fresh white jasmine flowers'),
    (r'ganesh\w*|ganpati|ganapati|vinayak\w*|chaturthi|chaturdashi|visarjan|visrajan|bappa', 'a handcrafted Lord Ganesha idol with a gold crown and a fresh marigold garland'),
    (r'holi', 'a brass plate heaped with vivid saffron, magenta and green gulal powder and fresh marigold petals'),
    (r'eid|ramadan|ramzan', 'a golden crescent moon and star lantern glowing with warm light'),
    (r'christmas|xmas', 'a single elegant gold and deep-red Christmas bauble beside a sprig of fresh pine'),
    (r'navratri|durga|dussehra|dasara', 'a decorated brass kalash with a coconut, mango leaves and fresh marigolds'),
    (r'raksha\s*bandhan|rakhi', 'an ornate rakhi with gold thread resting on a small brass plate with flower petals'),
    (r'janmashtami|krishna', 'a polished brass flute with a peacock feather and a small clay pot'),
    (r'pongal|sankranti|lohri|baisakhi', 'a traditional clay pot with fresh sugarcane stalks and marigolds'),
    (r'onam', 'a circular arrangement of fresh flower petals in concentric rings, in marigold, white and red'),
    (r'independence|republic', 'a tasteful arrangement of saffron, white and green fresh flowers'),
)


# Quiet supporting details added around an element the admin named themselves, so the picture
# still reads as the right festival (a bare diya could be any Diwali post). Not added to the
# built-in elements above, which already include theirs.
FESTIVAL_PROPS = (
    (r'laxmi|lakshmi|dhanteras', 'a few gold coins and fresh pink lotus petals resting softly around its base'),
    (r'diwali|deepavali|dipavali', 'a few fresh marigold petals resting softly at its base'),
)


def props_for(details, brief=''):
    """', with <props>' when the admin chose the element and the festival has typical props, else ''."""
    if not details.get('element'):
        return ''
    haystack = ' '.join([details.get('festival', ''), details.get('greeting', ''), brief or ''])
    for pattern, props in FESTIVAL_PROPS:
        if re.search(r'\b(' + pattern + r')\b', haystack, re.IGNORECASE):
            return f', with {props}'
    return ''


# Labels that mark a brief as the festive template. Deliberately stricter than the parser: a bare
# "Quote:" or "Element:" can appear in an ordinary post brief and must not switch the layout.
FESTIVE_TEMPLATE_RE = re.compile(
    r'(?<![A-Za-z])(main\s+greeting|festive\s+element|festival|wish\s*/\s*quote)\s*:', re.IGNORECASE,
)


def is_festive_request(creative_type, brief):
    """A festival creative - picked as the type, or recognised from the template labels in the
    brief (so a brief written with them is festive even if the form was left on "Post")."""
    return creative_type == 'festival_creative' or bool(FESTIVE_TEMPLATE_RE.search(brief or ''))


# Festival / occasion names recognised in free text (a brief with no template labels). The element
# patterns above plus the names that have no built-in element.
FESTIVAL_NAME_RE = re.compile(
    r'\b(' + '|'.join(pattern for pattern, _element in FESTIVAL_ELEMENTS) + r'|chaturthi|chaturdashi|ganpati|vinayak|'
    r'visarjan|visrajan|shivratri|navaratri|vishu|bihu|gurpurab|guru\s+nanak|mahavir|buddha\s+purnima|easter|'
    r'good\s+friday|thanksgiving|new\s+year|valentine|halloween|muharram|mothers?.?s?\s+day|womens?.?s?\s+day|'
    r'teachers?.?s?\s+day|childrens?.?s?\s+day)\b',
    re.IGNORECASE,
)


def names_a_festival(text):
    return bool(FESTIVAL_NAME_RE.search(text or ''))


# Words that carry no picture content: grammar, "make me a ..." phrasing, the kind of creative, and
# generic festive wording. What is left after removing these AND the festival's own name is what the
# admin actually described.
SCENE_FILLER = frozenset('''
    a an the and or of to in on at by for with from into onto over under like as is are be this that these
    those it its our your their my we you i please want need give using use
    create creates created make made generate design creative creatives post posts image images picture
    pictures photo photos poster banner visual
    realistic real premium beautiful nice good best new high quality
    wish wishes wishing greeting greetings festival festive celebration celebrate happy
    social media instagram facebook linkedin whatsapp followers customers audience clients
'''.split())
SCENE_MIN_CONTENT_WORDS = 4


def describes_scene(brief):
    """True when the brief describes what the picture should show, e.g. "create realistic creative for
    anant chaturdashi with lord ganesh murti visarjan in sea like lalbaugcha raja". Counts the words that
    are left once the festival's own name and filler ("create", "realistic", "post", "wishes"...) are
    removed: 4+ means a real description. Such a brief is followed as the scene itself instead of being
    reduced to the plain template design. A short topic ("Diwali greeting for our followers") or a brief
    written with the template labels (Festival:, Festive Element: ...) is not a scene - the template's
    own free text only repeats the layout rules."""
    text = (brief or '').strip()
    if not text or FESTIVE_TEMPLATE_RE.search(text) or parse_festive_details(text):
        return False
    words = re.findall(r'\w+', FESTIVAL_NAME_RE.sub(' ', text).lower())
    return len([word for word in words if word not in SCENE_FILLER]) >= SCENE_MIN_CONTENT_WORDS


# Fallback for when the text AI did not supply a visual description: strip the "create a ... for" instruction
# at the start and spell out the few terms an image model cannot guess (misspelt or insider names).
_INSTRUCTION_RE = re.compile(
    r'^\s*(please\s+)?(create|make|generate|design|prepare)\s+(me\s+)?(a\s+|an\s+|the\s+)?'
    r'((realistic|premium|beautiful|stunning|high[- ]quality|real)\s+)*'
    r'(creative|post|image|picture|poster|banner|visual|photo)\s+(for|of|about|on|with)\s+',
    re.IGNORECASE,
)
_SCENE_TERMS = (
    # festival names are context for the admin, not something to draw: models paint them as lettering
    (r'\b(anant\s+)?chatur(th|d)\w*(\s+dar?shi)?\b', ''),
    (r'lal\s*baug\w*\s*(cha|ka|ke)?\s*raja', 'a very large, grand Ganesha idol with a tall golden crown, like the famous Lalbaugcha Raja of Mumbai'),
    (r'\b(visarjan|visrajan|visarjana|immersion)\b', 'being immersed (lowered into the water)'),
    (r'\bmurti\b', 'idol'),
    (r'\bin\s+(the\s+)?sea\b', 'in the open sea with waves and a horizon'),
)


def clean_scene_brief(brief):
    text = _INSTRUCTION_RE.sub('', (brief or '').strip(), count=1)
    for pattern, replacement in _SCENE_TERMS:
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
    text = re.sub(r'\s+', ' ', text).strip(' .,')
    return re.sub(r'^(with|and|for|of)\s+', '', text, flags=re.IGNORECASE)


def _clean(value):
    value = re.sub(r'[*_`]+', '', value).strip().strip('"\'“”‘’').strip()
    value = re.sub(r'\s+', ' ', value)
    if not value or (value.startswith('[') and value.endswith(']')):  # unfilled template placeholder
        return ''
    return value


def parse_festive_details(brief):
    """{'festival', 'greeting', 'wish', 'element'} - each only if the brief provides it."""
    brief = brief or ''
    matches = list(LABEL_RE.finditer(brief))
    details = {}
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(brief)
        value = _clean(brief[match.end():end].split('\n', 1)[0])  # a value runs to the end of its line
        field = FIELD_FOR_LABEL.get(re.sub(r'\s+', ' ', match.group(1).lower()).replace(' / ', '/'))
        if field and value and field not in details:
            details[field] = value
    return details


def split_greeting(greeting):
    """'Happy Diwali' -> ('Happy', 'Diwali'); 'Eid Mubarak' -> ('', 'Eid Mubarak')."""
    greeting = (greeting or '').strip()
    lowered = greeting.lower()
    for lead in sorted(GREETING_LEADS, key=len, reverse=True):
        if lowered.startswith(lead + ' '):
            rest = greeting[len(lead):].strip()
            if rest:
                return greeting[:len(lead)].strip().capitalize(), rest
    return '', greeting


def element_for(details, brief=''):
    """What the image should show: the admin's own words if given, else a visual description
    for the festival, else a generic instruction."""
    if details.get('element'):
        return details['element']
    haystack = ' '.join([details.get('festival', ''), details.get('greeting', ''), brief or ''])
    for pattern, element in FESTIVAL_ELEMENTS:
        if re.search(r'\b(' + pattern + r')\b', haystack, re.IGNORECASE):
            return element
    festival = details.get('festival') or details.get('greeting')
    if festival:
        return f'one single, beautifully crafted, iconic object that symbolises {festival}'
    return 'one single, beautifully crafted, iconic festive object suited to the occasion'


def apply_provided_wording(copy_data, details, brief=''):
    """What goes on the festive picture: the admin's own words, exactly. The copy AI's greeting
    and wish are used only to fill a gap when the brief at least identifies the festival - by a
    template label, or by naming it in the text. If the brief gives no wording and no festival at all,
    nothing is invented and no words are drawn."""
    copy_data = dict(copy_data)
    copy_data['cta'] = ''  # festive creatives have no call to action
    named_something = any(details.get(key) for key in ('festival', 'greeting', 'wish')) or names_a_festival(brief)
    if details.get('greeting'):
        copy_data['eyebrow'], copy_data['headline'] = split_greeting(details['greeting'])
    elif not named_something:
        copy_data['eyebrow'] = copy_data['headline'] = ''
    if details.get('wish'):
        copy_data['description'] = details['wish']
    elif not named_something:
        copy_data['description'] = ''
    return copy_data
