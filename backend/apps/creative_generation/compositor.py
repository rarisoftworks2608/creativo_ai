"""Applies the brand layer onto an AI-generated creative (Epic 06: AI Creative Generation).

Diffusion image models are unreliable at rendering legible text and can never reproduce a
real logo - even top-tier ones misspell headlines and invent marks. So the image model is
asked for the full scene only (see prompts.build_image_prompt) and everything brand-specific is
drawn on top here with Pillow, from the real assets and the real copy.

Every creative is art-directed for its own picture (art_direction.py): the text stack (kicker, headline,
body, optional CTA in the brand fonts and colours) goes where that picture is calm - left, right, in a
narrow editorial column or, only when nothing else fits, centred - in a typography preset that suits the
creative type and the brand. The original logo file is always top-right, never redrawn or recoloured.
Text is always set here from the real copy, so spelling is exact, and at the final (HD) size. The scene is
never stretched or smoothed.
"""

import io
import re
import unicodedata
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont, ImageStat

from .art_direction import STYLE_PRESETS, UNFRAMED_TYPES, EnergyMap, choose_style, logo_corners, plan_layout, seeded

FONT_DIR = Path(__file__).resolve().parent / 'fonts'

# BrandProfile.fonts only stores a family name (e.g. "Poppins") - there's no uploaded font
# file - so brand font selection is a name match against this bundled, open-license set
# rather than truly arbitrary fonts. "variable" fonts carry every weight in one file,
# selected at render time via set_variation_by_name(); "bold"/"semibold" are separate
# static files for families that don't ship a variable version.
BRAND_FONT_LIBRARY = {
    'poppins': {
        'bold': FONT_DIR / 'Poppins-Bold.ttf', 'semibold': FONT_DIR / 'Poppins-SemiBold.ttf',
        'regular': FONT_DIR / 'Poppins-Regular.ttf',
    },
    'montserrat': {'variable': FONT_DIR / 'Montserrat-Variable.ttf'},
    'roboto': {'variable': FONT_DIR / 'Roboto-Variable.ttf'},
    'inter': {'variable': FONT_DIR / 'Inter-Variable.ttf'},
    'playfair display': {'variable': FONT_DIR / 'PlayfairDisplay-Variable.ttf'},
    'open sans': {'variable': FONT_DIR / 'OpenSans-Variable.ttf'},
    'lato': {'bold': FONT_DIR / 'Lato-Bold.ttf', 'semibold': FONT_DIR / 'Lato-SemiBold.ttf'},
}
DEFAULT_FONT_FAMILY = 'poppins'
HEADLINE_FONT_FAMILY = 'playfair display'
# The italic cut of the headline serif (same open-license family): the headline's last word is set in it, the
# way a premium editorial heading emphasises the word that carries the idea.
HEADLINE_ITALIC_SPEC = {'variable': FONT_DIR / 'PlayfairDisplay-Italic-Variable.ttf', 'italic': True}

# The bundled Latin fonts have no Devanagari glyphs, so Hindi / Marathi text (a festival greeting
# such as "शुभ लक्ष्मी पूजन") is set in Noto instead - serif for headlines, sans for body copy. Proper
# letter shaping (matras, conjuncts) needs Pillow's raqm layout engine, which the Docker image has.
DEVANAGARI_FONTS = {
    'serif': {'variable': FONT_DIR / 'NotoSerifDevanagari-Variable.ttf'},
    'sans': {'variable': FONT_DIR / 'NotoSansDevanagari-Variable.ttf'},
}
DEVANAGARI_RE = re.compile('[\u0900-\u097F\uA8E0-\uA8FF]')

DEFAULT_BANNER_COLOR = '#1A1A1A'  # "ink" - headline/body text color
DEFAULT_ACCENT_COLOR = '#D4A017'  # eyebrow/CTA accent
WHITE = '#FFFFFF'

_CHAR_REPLACEMENTS = {
    '–': '-', '—': '-',       # en dash, em dash
    '‘': "'", '’': "'",       # curly single quotes
    '“': '"', '”': '"',       # curly double quotes
    '…': '...',                    # ellipsis
    '•': '-',                      # bullet
    '‐': '-', '‑': '-', '‒': '-', '−': '-',  # hyphen variants (U+2010/2011/2012) and minus sign
    ' ': ' ',                      # non-breaking space
}


def _has_devanagari(text):
    return bool(DEVANAGARI_RE.search(text or ''))


def _sanitize_text(text):
    """Replaces "smart" typographic characters the text AI commonly generates (en/em
    dashes, curly quotes, ...) with visible plain-ASCII equivalents, then strips anything
    else outside ASCII and Devanagari via NFKD decomposition as a final safety net. Not every
    bundled font is guaranteed to have a glyph for an arbitrary character, and an unsupported
    one renders as a visible tofu box instead of failing loudly - better to lose an accent or
    an unanticipated symbol than to render a broken-looking box in a client-facing creative.
    Devanagari (and the joiners used inside its conjuncts) is kept: Noto Devanagari covers it.
    """
    for bad, good in _CHAR_REPLACEMENTS.items():
        text = text.replace(bad, good)
    kept = []
    for char in text:
        if ord(char) < 128 or char in '\u200c\u200d' or DEVANAGARI_RE.match(char):
            kept.append(char)
        else:
            kept.append(unicodedata.normalize('NFKD', char).encode('ascii', 'ignore').decode('ascii'))
    return ''.join(kept)


def _typographic(text):
    """Straight quotes and apostrophes as the curly ones a designer would set ("Tomorrow's" -> "Tomorrow\u2019s").
    _sanitize_text flattens every curly quote to ASCII so that nothing can render as a missing-glyph box; this
    puts them back at draw time, for Latin text only - every bundled Latin font has these four glyphs."""
    if not text or _has_devanagari(text):
        return text
    text = re.sub(r"(?<=\w)'(?=\w)", '\u2019', text)                      # an apostrophe inside a word
    text = re.sub(r"(^|[\s(\[{-])'", '\\1\u2018', text).replace("'", '\u2019')  # opening, then closing, single
    text = re.sub(r'(^|[\s(\[{-])"', '\\1\u201c', text).replace('"', '\u201d')  # opening, then closing, double
    return text


def _brand_font(brand_profile, weight, size, text=''):
    """Resolves (family, weight) to a loaded, correctly-weighted ImageFont, matching
    BrandProfile.fonts[0].name against BRAND_FONT_LIBRARY (case-insensitive), falling
    back to Poppins if unset or unrecognized. Used for the eyebrow/description/CTA -
    the brand's own configured font is right for body/UI-style text. Text containing
    Devanagari uses Noto Sans Devanagari instead, as no brand font here covers that script.
    """
    if _has_devanagari(text):
        return _load_font(DEVANAGARI_FONTS['sans'], weight, size)
    fonts = list(getattr(brand_profile, 'fonts', None) or [])
    family_name = (fonts[0].get('name') or '').strip().lower() if fonts else ''
    spec = BRAND_FONT_LIBRARY.get(family_name) or BRAND_FONT_LIBRARY[DEFAULT_FONT_FAMILY]
    return _load_font(spec, weight, size)


def _headline_font(weight, size, text=''):
    """The headline always uses the bundled premium editorial serif regardless of the
    brand's own configured font - a deliberate design-system choice (project_plan.md's
    "creative plan": "elegant high-contrast serif ... for major headlines", brand's own
    font reserved for supporting copy), not a brand-matching lookup like _brand_font.
    Text containing Devanagari uses Noto Serif Devanagari.
    """
    if _has_devanagari(text):
        return _load_font(DEVANAGARI_FONTS['serif'], weight, size)
    return _load_font(BRAND_FONT_LIBRARY[HEADLINE_FONT_FAMILY], weight, size)


def _italic_headline_font(weight, size):
    return _load_font(HEADLINE_ITALIC_SPEC, weight, size)


def _load_font(spec, weight, size):
    """`weight` is 'bold', 'semibold' or 'regular'. Families shipped as static files only have
    bold/semibold, so 'regular' falls back to semibold for them."""
    if 'variable' in spec:
        font = ImageFont.truetype(str(spec['variable']), size)
        if spec.get('italic'):
            font.set_variation_by_name({'bold': 'Bold Italic', 'regular': 'Italic'}.get(weight, 'SemiBold Italic'))
        else:
            font.set_variation_by_name({'bold': 'Bold', 'regular': 'Regular'}.get(weight, 'SemiBold'))
        return font
    return ImageFont.truetype(str(spec.get(weight) or spec['semibold']), size)


def _brand_colors(brand_profile):
    colors = list(getattr(brand_profile, 'brand_colors', None) or [])
    primary = next((c.get('hex') for c in colors if 'primary' in (c.get('name') or '').lower() and c.get('hex')), None)
    accent = next(
        (c.get('hex') for c in colors if c.get('hex') and (c.get('name') or '').lower() not in ('primary', '')),
        None,
    )
    return _valid_hex(primary, DEFAULT_BANNER_COLOR), _valid_hex(accent, DEFAULT_ACCENT_COLOR)


def _valid_hex(value, fallback):
    if value and value.startswith('#') and len(value.lstrip('#')) in (3, 6):
        return value
    return fallback


def _rgb(hex_color):
    hex_color = hex_color.lstrip('#')
    if len(hex_color) == 3:
        hex_color = ''.join(c * 2 for c in hex_color)
    return tuple(int(hex_color[i:i + 2], 16) for i in (0, 2, 4))


def _wrapped_lines(draw, text, font, max_width, max_lines):
    """Greedy word wrap. If the text needs more than max_lines, the last line is cut at a
    word boundary and ends with "..." instead of silently losing the rest of the sentence."""
    lines, current = [], ''
    for word in text.split():
        candidate = f'{current} {word}'.strip()
        if draw.textlength(candidate, font=font) <= max_width or not current:
            current = candidate
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        last = lines[-1]
        while last and draw.textlength(last + '...', font=font) > max_width:
            last = last.rsplit(' ', 1)[0] if ' ' in last else last[:-1]
        lines[-1] = last.rstrip(' ,.;:-') + '...'
    return lines


# --------------------------------------------------------------------------- composition

DEFAULT_STYLE = {**STYLE_PRESETS['editorial_serif'], 'weight': 'bold'}  # the look of the pinned (not art-directed) layouts
DEFAULT_ASPECT = 1.25        # 4:5 portrait - Instagram 1080 x 1350 (stories pass 16:9)
LOGO_WIDTH_FRACTION = 0.32   # logo width as a share of the image width
LOGO_MAX_HEIGHT_FRACTION = 0.11
CAPS_LEADING = 1.7           # line height of the widely spaced sub-line, as a multiple of its type size


def compose_creative(
    image_bytes, mime_type, *,
    eyebrow='', headline='', description='', cta='',
    logo_bytes=None, symbol_bytes=None, brand_profile=None,
    placement='auto', aspect=DEFAULT_ASPECT, creative_type='', variation_seed=None, composition=None,
    output_width=None, highlights=(), tagline='', brand_name='', website='',
):
    """Returns (composited_bytes, 'image/jpeg'), or the input unchanged if there is nothing to
    apply. `logo_bytes` (BrandProfile.logo) takes priority over `symbol_bytes`
    (BrandProfile.secondary_logo) - only one mark is ever drawn: the original file, never redrawn.

    The picture is the full scene the image AI drew: it is never extended, stretched or smoothed
    (one taller than `aspect` is centre-cropped to it, anything else is kept as drawn). The text
    and the logo are drawn over it. `placement` 'auto' (the default) art-directs the composition for this
    picture - the text block's family, position and typography, and the logo's corner, chosen from the
    picture's calm areas, the creative type and the brand's tone (art_direction.py); `variation_seed` varies
    the choice between near-equal options so repeated generations differ, and without one the single best is
    used. `composition` ('bottom', 'top', 'left' or 'right') is the calm space the picture was asked to leave
    for the text; it is favoured, but the picture's measured calm decides. The logo is always top-right.
    'below' pins the text centred along the bottom and 'top' left-aligned at the top-left instead.

    `output_width` makes the result high-resolution: the picture is enlarged to that width (never reduced)
    BEFORE the text and logo are drawn, so they are set sharp at the final size and not enlarged with it.

    `highlights` (the company's services as 2-4 short labels), `tagline`, `brand_name` and `website` dress a
    business creative as a designed poster: the kicker moves to a header row opposite the logo and a services strip
    and a footer are drawn along the bottom (see _paint_frame). Greetings and testimonials never get them."""
    mark_bytes = logo_bytes or symbol_bytes
    if not any([eyebrow, headline, description, cta, mark_bytes]):
        return image_bytes, mime_type

    eyebrow = _sanitize_text(eyebrow)
    headline = _sanitize_text(headline)
    description = _sanitize_text(description)
    cta = _sanitize_text(cta)
    highlights = [text for text in (_sanitize_text(str(label)).strip() for label in (highlights or ())) if text][:4]
    tagline, brand_name = _sanitize_text(tagline or '').strip(), _sanitize_text(brand_name or '').strip()

    base = Image.open(io.BytesIO(image_bytes)).convert('RGBA')
    primary, accent = _brand_colors(brand_profile)
    mark = _prepare_mark(mark_bytes) if mark_bytes else None

    base = _upscale(_crop_taller_than(base, aspect), output_width)
    if placement in ('top', 'below'):
        base = _draw_layout(
            base, placement=placement, eyebrow=eyebrow, headline=headline, description=description, cta=cta,
            primary=primary, accent=accent, mark=mark, brand_profile=brand_profile,
        )
    else:
        base = _art_direct(
            base, eyebrow=eyebrow, headline=headline, description=description, cta=cta, primary=primary,
            accent=accent, mark=mark, brand_profile=brand_profile, creative_type=creative_type, seed=variation_seed,
            composition=composition, highlights=highlights, tagline=tagline, brand_name=brand_name, website=website,
        )
    return _encode_jpeg(base.convert('RGB')), 'image/jpeg'


MAX_JPEG_BYTES = 4_500_000  # under WhatsApp's 5 MB image limit and Instagram's 8 MB one


def _encode_jpeg(image):
    """The finished creative as a high-quality JPEG (full-resolution colour, so thin text stays crisp), stepping
    the quality down only if the file would be too large to send on."""
    for quality in (95, 92, 88, 84, 80):
        output = io.BytesIO()
        image.save(output, format='JPEG', quality=quality, subsampling=0, optimize=True)
        if output.tell() <= MAX_JPEG_BYTES:
            break
    return output.getvalue()


def _upscale(base, output_width):
    """The picture enlarged to `output_width` with a high-quality filter and a light sharpening pass, so it reads
    as a crisp HD picture rather than a soft small one. Never reduces a picture that is already that wide."""
    if not output_width or base.width >= output_width:
        return base
    height = round(base.height * output_width / base.width)
    enlarged = base.convert('RGB').resize((output_width, height), Image.LANCZOS)
    return enlarged.filter(ImageFilter.UnsharpMask(radius=1.6, percent=60, threshold=2)).convert('RGBA')


def _prepare_mark(mark_bytes):
    """The logo as RGBA with a transparent background, trimmed to its artwork - or None if
    the file can't be read. Logos are often uploaded as JPEGs / opaque PNGs with a flat
    off-white background; that background is keyed out so the logo can sit directly on the
    creative instead of inside a white box."""
    try:
        mark = Image.open(io.BytesIO(mark_bytes)).convert('RGBA')
    except Exception:  # noqa: BLE001 - a corrupt/unsupported image file should never fail generation
        return None
    width, height = mark.size
    if mark.getchannel('A').getextrema()[0] >= 250:  # fully opaque: look for a flat background
        corners = [mark.getpixel(point)[:3] for point in ((0, 0), (width - 1, 0), (0, height - 1), (width - 1, height - 1))]
        background = tuple(sum(c[i] for c in corners) // 4 for i in range(3))
        if all(sum(abs(c[i] - background[i]) for i in range(3)) <= 45 for c in corners):
            difference = ImageChops.difference(mark.convert('RGB'), Image.new('RGB', mark.size, background)).convert('L')
            mark.putalpha(difference.point(lambda v: 0 if v < 24 else min(255, (v - 24) * 6)))
    box = mark.getchannel('A').point(lambda v: 255 if v > 24 else 0).getbbox()
    return mark.crop(box) if box else None


def _mix(hex_color, other_rgb, amount):
    r, g, b = _rgb(hex_color)
    return '#%02X%02X%02X' % tuple(int(c + (o - c) * amount) for c, o in zip((r, g, b), other_rgb))


def _relative_luminance(hex_color):
    def channel(value):
        value /= 255
        return value / 12.92 if value <= 0.03928 else ((value + 0.055) / 1.055) ** 2.4

    r, g, b = (channel(c) for c in _rgb(hex_color))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def _contrast_ratio(color_a, color_b):
    lighter, darker = sorted((_relative_luminance(color_a), _relative_luminance(color_b)), reverse=True)
    return (lighter + 0.05) / (darker + 0.05)


def _ensure_contrast(color, background, minimum):
    """`color` pushed darker on a light background / lighter on a dark one until it reads."""
    target = (0, 0, 0) if _relative_luminance(background) > 0.4 else (255, 255, 255)
    for _ in range(14):
        if _contrast_ratio(color, background) >= minimum:
            break
        color = _mix(color, target, 0.15)
    return color


# --- text

def _spaced_width(draw, text, font, spacing):
    """Width of `text` as _draw_spaced sets it."""
    if _has_devanagari(text):
        return draw.textlength(text, font=font)
    return sum(draw.textlength(char, font=font) for char in text) + spacing * (len(text) - 1)


def _draw_spaced(draw, x, top, text, font, fill, spacing, centered=True, align=None):
    """Text with extra letter spacing (Pillow has no built-in tracking), centred on x, starting at x ('left')
    or ending at x ('right')."""
    align = align or ('center' if centered else 'left')
    if _has_devanagari(text):
        # Letter by letter would pull the vowel signs (matras) off their consonants; draw it whole.
        draw.text((x, top), text, font=font, fill=fill, anchor={'center': 'ma', 'left': 'la', 'right': 'ra'}[align])
        return
    widths = [draw.textlength(char, font=font) for char in text]
    total = sum(widths) + spacing * (len(text) - 1)
    cursor = {'center': x - total / 2, 'left': x, 'right': x - total}[align]
    for char, char_width in zip(text, widths):
        draw.text((cursor, top), char, font=font, fill=fill)
        cursor += char_width + spacing


def _kicker_spacing(font, kicker):
    """Letter spacing of the kicker: wide and airy for the 'tracked' look, tight for the others."""
    return max(3, round(font.size * 0.3)) if kicker == 'tracked' else 3


def _build_text_parts(
    draw, *, centered=None, align=None, text_width, width, eyebrow, headline, description, cta, brand_profile,
    style=None,
):
    """The text stack, top to bottom, as (kind, data, height, gap_before) tuples: kicker, headline, a divider,
    body copy and a CTA - each only if there is text for it. `align` is 'center', 'left' or 'right'. `style` is
    one of art_direction.STYLE_PRESETS (headline face, weight, case and size, kicker, divider and CTA looks);
    without one the original centred look is used, with no divider or kicker rules when left-aligned.

    Nothing is cut short with an ellipsis if it can be avoided: the body copy shrinks (to a floor) to fit its
    column, and a long kicker such as "Strategy / Technology / Growth" shrinks to fit."""
    align = align or ('left' if centered is False else 'center')
    centered = align == 'center'
    eyebrow, headline, description, cta = (_typographic(value) for value in (eyebrow, headline, description, cta))
    pinned = style is None
    style = style or DEFAULT_STYLE
    kicker = ('rules' if centered else 'plain') if pinned else style['kicker']
    divider = ('diamond' if centered else 'none') if pinned else style['divider']
    parts = []
    if eyebrow:
        tracked = kicker == 'tracked'
        size = max(13, int(width * (0.021 if tracked else 0.026)))
        font = _brand_font(brand_profile, 'regular' if tracked else 'semibold', size, eyebrow)
        while size > 12 and _spaced_width(draw, eyebrow.upper(), font, _kicker_spacing(font, kicker)) > text_width:
            size -= 1
            font = _brand_font(brand_profile, 'regular' if tracked else 'semibold', size, eyebrow)
        parts.append(('eyebrow', (eyebrow, font, kicker), int(font.size * 1.7), 0))
    if headline:
        text = headline.upper() if style['case'] == 'upper' else headline
        weight = style.get('weight', 'bold')

        def font_at(size):
            if style['headline'] == 'brand':
                return _brand_font(brand_profile, weight, size, text)
            return _headline_font(weight, size, text)

        # A headline of two short sentences ("Ideas Into Innovation. Technology Into Growth.") keeps one sentence to
        # a line, and the word that closes each sentence is set in the accent colour (the 'accent_words' presets).
        by_sentence = bool(style.get('accent_words')) and not _has_devanagari(text)
        max_lines = 4 if by_sentence else 3

        def headline_lines(font, limit):
            if not by_sentence:
                return _wrapped_lines(draw, text, font, text_width, max_lines=limit)
            return [
                line for sentence in _sentences(text)
                for line in _wrapped_lines(draw, sentence, font, text_width, max_lines=99)
            ]

        size = max(30, int(width * style['size']))
        font = font_at(size)
        longest = max(text.split(), key=len)
        # Shrink until the longest word fits and the headline needs no more than three (four) lines.
        while size > 24 and (
            draw.textlength(longest, font=font) > text_width or len(headline_lines(font, 99)) > max_lines
        ):
            size -= 2
            font = font_at(size)
        lines = headline_lines(font, max_lines)
        tail = None
        if (
            style.get('italic_tail') and style['headline'] == 'serif' and style['case'] == 'title'
            and not _has_devanagari(text) and len(text.split()) >= 2
        ):
            tail = (text.split()[-1], _italic_headline_font(weight, font.size))
        emphasis = _emphasis_by_line(lines) if by_sentence else None
        parts.append((
            'lines', (lines, font, int(font.size * 1.2), 'headline', tail, emphasis),
            len(lines) * int(font.size * 1.2), 0,
        ))
    if description and style.get('body') == 'caps' and not _has_devanagari(description):
        # The sub-line of the poster look: small, widely spaced capitals with a short rule under them.
        font, spacing, lines = _caps_lines(draw, description, brand_profile, width, text_width, style.get('body_size', 0.019))
        line_height = int(font.size * CAPS_LEADING)
        parts.append(('spaced', (lines, font, spacing, 'body'), len(lines) * line_height, int(width * 0.025) if parts else 0))
        if divider != 'none':
            parts.append(('divider', divider, 2 * max(4, int(width * 0.008)), int(width * 0.012)))
    elif description:
        max_lines = 3 if text_width > width * 0.45 else 4
        body_width = int(width * 0.74) if centered else text_width
        size = max(16, int(width * style.get('body_size', 0.03)))
        floor = max(14, int(width * 0.021))
        font = _brand_font(brand_profile, 'regular', size, description)
        while size > floor and len(_wrapped_lines(draw, description, font, body_width, max_lines=99)) > max_lines:
            size -= 1
            font = _brand_font(brand_profile, 'regular', size, description)
        lines = _wrapped_lines(draw, description, font, body_width, max_lines=max_lines)
        gap = int(width * 0.025) if parts else 0
        if headline and divider != 'none':
            parts.append(('divider', divider, 2 * max(4, int(width * 0.008)), int(width * 0.02)))  # ornament between headline and body
            gap = int(width * 0.02)
        parts.append(('lines', (lines, font, int(font.size * 1.6), 'body'), len(lines) * int(font.size * 1.6), gap))
    if cta:
        quiet = style['cta'] == 'underline'  # a quiet text link: sentence case, regular weight
        font = _brand_font(brand_profile, 'regular' if quiet else 'semibold', max(15, int(width * (0.029 if quiet else 0.03))), cta)
        label = cta if quiet else cta.upper()
        label_width = int(draw.textlength(label, font=font))
        if quiet:
            box_h, box_w = int(font.size * 1.7), label_width + int(font.size * 1.9)  # room for the arrow
        elif style['cta'] == 'square':
            box_h = int(font.size * 2.2)
            box_w = label_width + int(box_h * 0.9)
        else:
            box_h = int(font.size * 2.3)
            box_w = label_width + int(box_h * 0.9)
        parts.append(('cta', (label, font, box_w, box_h, style['cta']), box_h, int(width * 0.04) if parts else 0))
    return parts


def _sentences(text):
    return [sentence for sentence in re.split(r'(?<=[.!?])\s+', text.strip()) if sentence]


def _emphasis_by_line(lines):
    """For each headline line, the indexes of its words set in the accent colour: the word that closes each
    sentence ("Innovation.", "Growth.") and, always, the last word of the headline."""
    last = len(lines) - 1
    marked = []
    for number, line in enumerate(lines):
        words = line.split()
        marked.append({
            index for index, word in enumerate(words) if word[-1:] in ('.', '!', '?') or (number == last and index == len(words) - 1)
        })
    return marked


def _wrapped_spaced(draw, text, font, spacing, max_width, max_lines=99):
    """Greedy word wrap of widely spaced capitals. A single word wider than the column keeps its own line."""
    lines, current = [], ''
    for word in text.split():
        candidate = f'{current} {word}'.strip()
        if _spaced_width(draw, candidate, font, spacing) <= max_width or not current:
            current = candidate
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines[:max_lines] if len(lines) <= max_lines else lines[:max_lines - 1] + [' '.join(lines[max_lines - 1:])]


def _caps_lines(draw, text, brand_profile, width, text_width, size_share):
    """(font, spacing, lines) for a sub-line in widely spaced capitals: at most three lines, the type shrinking to
    a floor to fit rather than being cut."""
    text = text.upper()
    size = max(13, int(width * size_share))
    floor = max(11, int(width * 0.013))
    while True:
        font = _brand_font(brand_profile, 'regular', size, text)
        spacing = max(2, round(font.size * 0.2))
        lines = _wrapped_spaced(draw, text, font, spacing, text_width)
        if len(lines) <= 3 or size <= floor:
            return font, spacing, lines
        size -= 1


def _parts_width(draw, parts, align, width):
    """How wide the stack really is (its widest line, ornament or button), so it can be positioned and
    judged against the picture by what it covers, not by the width it was allowed."""
    widest = 1
    for kind, data, _height, _gap in parts:
        if kind == 'eyebrow':
            text, font, kicker = data
            ruled = kicker in ('rules', 'bar')
            extra = 2 * int(width * 0.12) if ruled and align == 'center' else (int(width * 0.07) if ruled else 0)
            widest = max(widest, int(_spaced_width(draw, text.upper(), font, _kicker_spacing(font, kicker))) + extra)
        elif kind == 'lines':
            lines, font = data[0], data[1]
            widest = max(widest, *(int(draw.textlength(line, font=font)) for line in lines))
        elif kind == 'spaced':
            lines, font, spacing = data[:3]
            widest = max(widest, *(int(_spaced_width(draw, line, font, spacing)) for line in lines))
        elif kind == 'divider':
            widest = max(widest, int(width * 0.2) if align == 'center' else int(width * 0.16))
        elif kind == 'cta':
            widest = max(widest, data[2])
    return widest


def _vertical_gradient(size, color, max_alpha, ramp=0.7):
    """Solid `color` whose opacity ramps from 0 at the top to max_alpha `ramp` of the way down, then holds."""
    width, height = size
    column = Image.new('L', (1, height))
    for y in range(height):
        column.putpixel((0, y), int(max_alpha * min(1.0, (y / max(height - 1, 1)) / ramp) ** 1.4))
    solid = Image.new('RGBA', size, (*_rgb(color), 255))
    solid.putalpha(column.resize((width, height)))
    return solid


def _soft_veil(base, color, max_alpha, rect, blur, ellipse=False):
    """A soft glow of `color` over rect, fading out with a Gaussian of radius `blur`, so there is no visible
    edge - text or a logo sits in a halo of the brand tone, not on a panel. `rect` should extend about 1.5 x
    `blur` past what it has to protect, where the glow is at full strength. `ellipse` shapes the glow as an
    oval, which never reads as a box."""
    width, height = base.size
    reach = blur * 3
    left, top = max(0, rect[0] - reach), max(0, rect[1] - reach)
    right, bottom = min(width, rect[2] + reach), min(height, rect[3] + reach)
    if right <= left or bottom <= top:
        return
    mask = Image.new('L', (right - left, bottom - top), 0)
    shape = ImageDraw.Draw(mask).ellipse if ellipse else ImageDraw.Draw(mask).rectangle
    shape([rect[0] - left, rect[1] - top, rect[2] - left, rect[3] - top], fill=max_alpha)
    mask = mask.filter(ImageFilter.GaussianBlur(blur))
    layer = Image.new('RGBA', mask.size, (*_rgb(color), 255))
    layer.putalpha(mask)
    base.alpha_composite(layer, (left, top))


def _crop_taller_than(base, aspect):
    """A scene picture is never invented or stretched: one taller than the portrait ratio is centre-cropped
    to it, anything else is kept exactly as the image AI drew it."""
    width, height = base.size
    target = int(width * aspect)
    if height <= target:
        return base
    top = (height - target) // 2
    return base.crop((0, top, width, top + target))


# How opaque the veil behind the text may get, gentlest first. Nothing at all when the text already reads on
# the picture as it is: a cleaner, more luxurious look than a glow behind every block of text.
VEIL_STRENGTHS = (0.0, 0.2, 0.35, 0.5, 0.65, 0.8)


def _luminance_extremes(zone):
    """(bright_hex, dark_hex): the colour 90% of the way up and 10% of the way down the zone's brightness
    range. Text has to stay readable over the brightest spot behind it (a flame, a marigold) for white ink and
    the darkest one for dark ink, not just on the average colour."""
    pixels = sorted(
        zone.resize((48, 48)).getdata(), key=lambda p: 0.2126 * p[0] + 0.7152 * p[1] + 0.0722 * p[2],
    )
    pick = lambda share: '#%02X%02X%02X' % tuple(pixels[min(len(pixels) - 1, int(len(pixels) * share))][:3])  # noqa: E731
    return pick(0.9), pick(0.1)


def _text_style(backdrop_hex, primary, accent, bright_hex=None, dark_hex=None):
    """How the text reads best on the part of the picture it sits on, as (veil_color, veil_strength, ink,
    accent_color). The gentlest veil that gives readable contrast wins: a pale veil with dark brand-coloured
    text on a light picture (the usual look of a premium greeting: dark type straight onto a bright wall), or a
    deep brand-coloured veil with white text on a dark one. If nothing reaches the target even at the strongest
    veil, the better of the two at that strength is used. Contrast is judged at the worst spot behind the
    text - the darkest for dark ink, the brightest for white - and falls back to the average colour."""
    bright_hex, dark_hex = bright_hex or backdrop_hex, dark_hex or backdrop_hex
    deep = _mix(primary, (0, 0, 0), 0.62)
    pale = _mix(backdrop_hex, (255, 255, 255), 0.6)
    best = None
    for strength in VEIL_STRENGTHS:
        options = []
        light_bg = _mix(dark_hex, _rgb(pale), strength)
        if _relative_luminance(light_bg) > 0.4:
            ink = _ensure_contrast(_mix(primary, (0, 0, 0), 0.35), light_bg, 4.5)
            options.append((_contrast_ratio(ink, light_bg), pale, light_bg, ink))
        dark_bg = _mix(bright_hex, _rgb(deep), strength)
        options.append((_contrast_ratio('#FFFFFF', dark_bg), deep, dark_bg, '#FFFFFF'))
        contrast, veil, background, ink = max(options, key=lambda option: option[0])
        best = (veil, strength, ink, _ensure_contrast(accent, background, 3.0))
        if contrast >= 4.5:
            break
    return best


def _text_colors(base, rect, primary, accent):
    """(veil_color, veil_strength, ink, accent_color) for the text that will sit over `rect` of the picture."""
    zone = base.crop(rect).convert('RGB')
    backdrop_hex = '#%02X%02X%02X' % tuple(int(v) for v in ImageStat.Stat(zone).mean)
    bright_hex, dark_hex = _luminance_extremes(zone)
    return _text_style(backdrop_hex, primary, accent, bright_hex, dark_hex)


def _draw_layout(base, *, placement, eyebrow, headline, description, cta, primary, accent, mark, brand_profile):
    """The pinned layouts: 'below' (text centred along the bottom) and 'top' (text left-aligned at the
    top-left), the text over a gradient of the brand tone at the edge it is placed on, the logo top-right."""
    width, height = base.size
    pad = int(width * 0.06)
    top_anchored = placement == 'top'
    align = 'left' if top_anchored else 'center'
    edge_margin = pad if top_anchored else int(width * 0.09)
    text_width = int(width * 0.52) if top_anchored else int(width * 0.88)
    parts = _build_text_parts(
        ImageDraw.Draw(base), align=align, text_width=text_width, width=width,
        eyebrow=eyebrow, headline=headline, description=description, cta=cta, brand_profile=brand_profile,
    )
    if parts:
        total = sum(part_height + gap for _kind, _data, part_height, gap in parts)
        block_top = edge_margin if top_anchored else height - edge_margin - total
        veil_color, strength, ink, accent_color = _text_colors(base, (0, block_top, width, block_top + total), primary, accent)
        veil_height = min(int(height * 0.7), edge_margin + total + pad * 3)
        # The veil is at full strength by the time the text starts - the strength was chosen for the text, so
        # a fade that is still faint at the headline would leave it unreadable.
        lead = max(veil_height - edge_margin - total, int(veil_height * 0.05))
        veil = _vertical_gradient((width, veil_height), veil_color, int(255 * strength), ramp=min(0.7, lead / veil_height))
        if top_anchored:
            base.alpha_composite(veil.transpose(Image.Transpose.FLIP_TOP_BOTTOM), (0, 0))
        else:
            base.alpha_composite(veil, (0, height - veil_height))
        _paint_parts(
            ImageDraw.Draw(base), parts, x=width // 2 if align == 'center' else pad, y=block_top, align=align,
            width=width, ink=ink, accent_color=accent_color,
        )
    if mark is not None:
        _draw_logo(base, mark, logo_corners(base.size, _logo_size(mark, width, height))['top_right'], primary)
    return base


def _site_label(website):
    """A website as it is printed on a poster: no scheme, no "www.", no path ("https://rarisoftworks.com/" ->
    "rarisoftworks.com")."""
    host = re.sub(r'^[a-z]+://', '', (website or '').strip(), flags=re.IGNORECASE)
    return re.sub(r'^www\.', '', host, flags=re.IGNORECASE).split('/')[0].lower()


def _frame_metrics(width, height, labels, site, brand_name, tagline):
    """Where the poster furniture goes along the bottom: a services strip above a footer, with the room the text
    has to leave for them (`reserve`, in pixels from the bottom edge)."""
    foot_height = int(width * (0.036 if tagline else 0.022))
    strip_height = int(width * 0.075) if labels else 0
    bottom = height - int(width * 0.05)
    footer_top = bottom - foot_height
    strip_top = footer_top - int(width * 0.04) - strip_height
    top = (strip_top if labels else footer_top) - int(width * 0.03)
    return {
        'footer_top': footer_top, 'footer_height': foot_height, 'strip_top': strip_top, 'strip_height': strip_height,
        'reserve': height - top, 'has_footer': bool(site or brand_name),
    }


def _paint_frame(base, metrics, *, labels, site, brand_name, tagline, brand_profile, primary, accent):
    """The bottom of the poster: a strip of the company's services (a number over a widely spaced label, hairline
    dividers between them) and a footer - the company name and sign-off on the left, the website after a short rule
    on the right. A scrim of the brand tone sits under them only if the picture is too busy for them to read."""
    width, height = base.size
    top = metrics['strip_top'] if labels else metrics['footer_top']
    zone = (0, top - int(width * 0.02), width, height)
    veil_color, strength, ink, accent_color = _text_colors(base, zone, primary, accent)
    if strength:
        scrim_height = height - zone[1] + int(width * 0.08)
        base.alpha_composite(_vertical_gradient((width, scrim_height), veil_color, int(255 * strength), ramp=0.6), (0, height - scrim_height))
    backdrop = '#%02X%02X%02X' % tuple(int(v) for v in ImageStat.Stat(base.crop(zone).convert('RGB')).mean)
    body_color = _ensure_contrast(_mix(ink, _rgb(backdrop), 0.12), backdrop, 4.5)
    muted_color = _ensure_contrast(_mix(ink, _rgb(backdrop), 0.4), backdrop, 3.5)
    hairline = _mix(ink, _rgb(backdrop), 0.65)
    draw = ImageDraw.Draw(base)
    margin = int(width * 0.07)

    if labels:
        columns = len(labels)
        column = (width - 2 * margin) / columns
        size = max(12, int(width * 0.0165))
        text = ' '.join(labels).upper()
        font = _brand_font(brand_profile, 'regular', size, text)
        longest = max(text.split(), key=len)
        while size > 11 and _spaced_width(draw, longest, font, max(2, round(font.size * 0.16))) > column * 0.8:
            size -= 1
            font = _brand_font(brand_profile, 'regular', size, text)
        spacing = max(2, round(font.size * 0.16))
        for index, label in enumerate(labels):
            centre = margin + column * (index + 0.5)
            _draw_spaced(draw, centre, metrics['strip_top'], f'{index + 1:02d}', font, _rgb(accent_color), spacing, align='center')
            y = metrics['strip_top'] + int(font.size * 1.8)
            for line in _wrapped_spaced(draw, label.upper(), font, spacing, column * 0.84, max_lines=2):
                _draw_spaced(draw, centre, y, line, font, _rgb(body_color), spacing, align='center')
                y += int(font.size * 1.5)
            if index:
                edge = margin + column * index
                draw.line(
                    [(edge, metrics['strip_top']), (edge, metrics['strip_top'] + metrics['strip_height'])],
                    fill=_rgb(hairline), width=max(1, int(width * 0.0008)),
                )

    if metrics['has_footer']:
        y = metrics['footer_top']
        if brand_name:
            name_font = _brand_font(brand_profile, 'regular', max(12, int(width * 0.0205)), brand_name)
            draw.text((margin, y), brand_name, font=name_font, fill=_rgb(ink), anchor='la')
        if tagline:
            tag_font = _brand_font(brand_profile, 'regular', max(11, int(width * 0.0125)), tagline)
            _draw_spaced(
                draw, margin, y + int(width * 0.03), tagline.upper(), tag_font, _rgb(muted_color),
                max(2, round(tag_font.size * 0.22)), align='left',
            )
        if site:
            site_font = _brand_font(brand_profile, 'regular', max(12, int(width * 0.0168)), site)
            spacing = max(1, round(site_font.size * 0.08))
            right = width - margin
            _draw_spaced(draw, right, y, site, site_font, _rgb(ink), spacing, align='right')
            rule_end = right - _spaced_width(draw, site, site_font, spacing) - int(width * 0.015)
            mid = y + int(site_font.size * 0.62)
            draw.line([(rule_end - int(width * 0.05), mid), (rule_end, mid)], fill=_rgb(accent_color), width=max(2, int(width * 0.0014)))


def _header_height(draw, eyebrow, brand_profile, width):
    """Height of the header kicker row (0 without a kicker)."""
    if not eyebrow:
        return 0
    return _brand_font(brand_profile, 'regular', max(12, int(width * 0.0165)), eyebrow).size


def _paint_header(base, eyebrow, *, logo_rect, brand_profile, primary, accent):
    """The kicker as a header row opposite the logo: small, widely spaced capitals followed by a short accent rule,
    on the logo's centre line, shrunk to fit the room beside the logo."""
    width = base.width
    margin = int(width * 0.07)
    size = max(12, int(width * 0.0165))
    text = eyebrow.upper()
    font = _brand_font(brand_profile, 'regular', size, text)
    rule, gap = int(width * 0.045), int(width * 0.015)
    room = (logo_rect[0] - int(width * 0.04) if logo_rect else width - margin) - margin - rule - gap
    while size > 11 and _spaced_width(ImageDraw.Draw(base), text, font, max(3, round(font.size * 0.3))) > room:
        size -= 1
        font = _brand_font(brand_profile, 'regular', size, text)
    spacing = max(3, round(font.size * 0.3))
    text_width = _spaced_width(ImageDraw.Draw(base), text, font, spacing)
    centre = (logo_rect[1] + logo_rect[3]) // 2 if logo_rect else int(width * 0.06) + font.size
    top = centre - font.size // 2
    zone = (margin, top, margin + int(text_width) + gap + rule, top + font.size)
    veil_color, strength, ink, accent_color = _text_colors(base, zone, primary, accent)
    if strength:
        reach = int(width * 0.03)
        _soft_veil(base, veil_color, int(255 * strength), (zone[0] - reach, zone[1] - reach, zone[2] + reach, zone[3] + reach), blur=int(width * 0.04))
    backdrop = '#%02X%02X%02X' % tuple(int(v) for v in ImageStat.Stat(base.crop(zone).convert('RGB')).mean)
    draw = ImageDraw.Draw(base)
    _draw_spaced(draw, margin, top, text, font, _rgb(_ensure_contrast(_mix(ink, _rgb(backdrop), 0.15), backdrop, 4.5)), spacing, align='left')
    line_x = margin + int(text_width) + gap
    mid = top + int(font.size * 0.55)
    draw.line([(line_x, mid), (line_x + rule, mid)], fill=_rgb(accent_color), width=max(2, int(width * 0.0014)))


def _art_direct(
    base, *, eyebrow, headline, description, cta, primary, accent, mark, brand_profile, creative_type, seed,
    composition=None, highlights=(), tagline='', brand_name='', website='',
):
    """The art-directed layout: the text stack's family (centred / left / right / a narrow column) and position
    and the logo's corner are chosen for this picture's calm areas (art_direction.plan_layout), and the
    typography preset for the creative type and brand tone, both varied by `seed`. The text sits in a soft veil
    only as strong as its contrast needs; the logo is the original file, never redrawn.

    A business creative that has services and/or a website to show is dressed as a designed poster instead: the
    kicker in a header row, the headline in two tones, and a services strip and a footer along the bottom, the
    text stack placed in the calm space between them."""
    width, height = base.size
    rng = seeded(seed)
    labels = list(highlights)[:4] if len(highlights) >= 2 else []
    site = _site_label(website)
    framed = creative_type not in UNFRAMED_TYPES and bool(labels or site)
    _name, style = choose_style(rng, creative_type, brand_profile, framed=framed)
    framed = framed and bool(style.get('frame'))
    draw = ImageDraw.Draw(base)
    stacks = {}

    metrics = _frame_metrics(width, height, labels, site, brand_name, tagline) if framed else None
    header_text, stack_eyebrow = (eyebrow, '') if framed else ('', eyebrow)
    if framed and site:
        cta = ''  # the website in the footer is the call to action
    logo_size = _logo_size(mark, width, height) if mark is not None else None
    margin_top = margin_bottom = None
    if framed:
        pad = int(width * 0.06)
        margin_top = pad + max(logo_size[1] if logo_size else 0, _header_height(draw, header_text, brand_profile, width)) + int(width * 0.04)
        margin_bottom = metrics['reserve']

    def measure(family):
        parts = _build_text_parts(
            draw, align=family.align, text_width=int(width * family.width), width=width, eyebrow=stack_eyebrow,
            headline=headline, description=description, cta=cta, brand_profile=brand_profile, style=style,
        )
        stacks[family.name] = parts
        return _parts_width(draw, parts, family.align, width), sum(h + gap for _kind, _data, h, gap in parts)

    has_text = any((stack_eyebrow, headline, description, cta))
    plan = plan_layout(
        EnergyMap(base), base.size, measure=measure if has_text else None, logo_size=logo_size, rng=rng,
        prefer=composition, margin_top=margin_top, margin_bottom=margin_bottom,
    )

    if plan.text_rect is not None:
        parts, align = stacks[plan.family.name], plan.family.align
        left, top, right, bottom = plan.text_rect
        veil_color, strength, ink, accent_color = _text_colors(base, plan.text_rect, primary, accent)
        pad = int(width * 0.06)
        reach = int(pad * 1.5)
        _soft_veil(base, veil_color, int(255 * strength), (left - reach, top - reach, right + reach, bottom + reach), blur=pad)
        # The body copy and the kicker are a softer tone of the headline's ink, taken towards the picture behind
        # them (as a designer would grade them) - still held to a readable contrast.
        backdrop = '#%02X%02X%02X' % tuple(int(v) for v in ImageStat.Stat(base.crop(plan.text_rect).convert('RGB')).mean)
        body_color = _ensure_contrast(_mix(ink, _rgb(backdrop), 0.18), backdrop, 4.5)
        muted_color = _ensure_contrast(_mix(ink, _rgb(backdrop), 0.42), backdrop, 3.5)
        _paint_parts(
            ImageDraw.Draw(base), parts, x={'center': (left + right) // 2, 'left': left, 'right': right}[align],
            y=top, align=align, width=width, ink=ink, accent_color=accent_color,
            headline_color=accent_color if style['headline_color'] == 'accent' else ink,
            body_color=body_color, muted_color=muted_color,
        )
    if framed:
        if header_text:
            _paint_header(base, header_text, logo_rect=plan.logo_rect, brand_profile=brand_profile, primary=primary, accent=accent)
        _paint_frame(
            base, metrics, labels=labels, site=site, brand_name=brand_name, tagline=tagline,
            brand_profile=brand_profile, primary=primary, accent=accent,
        )
    if mark is not None and plan.logo_rect is not None:
        _draw_logo(base, mark, plan.logo_rect, primary)
    return base


def _draw_line(draw, x, y, text, font, fill, align, tail=None, emphasis=None, emphasis_fill=None):
    """One line of text, centred on x, starting at x or ending at x. With `tail` = (word, italic_font) and a
    line that ends with that word, the word is set in the italic font on the same baseline. With `emphasis` (the
    indexes of words in the line) those words are drawn in `emphasis_fill`."""
    if emphasis and emphasis_fill is not None:
        words = text.split(' ')
        space = draw.textlength(' ', font=font)
        widths = [draw.textlength(word, font=font) for word in words]
        total = sum(widths) + space * (len(words) - 1)
        cursor = {'center': x - total / 2, 'left': x, 'right': x - total}[align]
        for index, (word, word_width) in enumerate(zip(words, widths)):
            draw.text((cursor, y), word, font=font, fill=emphasis_fill if index in emphasis else fill, anchor='la')
            cursor += word_width + space
        return
    if tail is None or not text.endswith(tail[0]):
        draw.text((x, y), text, font=font, fill=fill, anchor={'center': 'ma', 'left': 'la', 'right': 'ra'}[align])
        return
    word, italic = tail
    prefix = text[:-len(word)]
    prefix_w, word_w = draw.textlength(prefix, font=font), draw.textlength(word, font=italic)
    start = {'center': x - (prefix_w + word_w) / 2, 'left': x, 'right': x - prefix_w - word_w}[align]
    baseline = y + font.getmetrics()[0]
    if prefix:
        draw.text((start, baseline), prefix, font=font, fill=fill, anchor='ls')
    draw.text((start + prefix_w, baseline), word, font=italic, fill=fill, anchor='ls')


def _paint_parts(
    draw, parts, *, x, y, align, width, ink, accent_color, headline_color=None, body_color=None, muted_color=None,
):
    """Draws the text stack top to bottom starting at y, centred on x, left-aligned at x or right-aligned at x.
    The headline is in `headline_color`, the body copy in `body_color` and a 'tracked' kicker in `muted_color`
    (each defaulting to the ink / accent)."""
    headline_color = headline_color or ink
    body_color = body_color or ink
    for kind, data, part_height, gap in parts:
        y += gap
        if kind == 'eyebrow':
            text, font, kicker = data
            text = text.upper()
            spacing = _kicker_spacing(font, kicker)
            text_w = _spaced_width(draw, text, font, spacing)
            mid = y + int(font.size * 0.55)
            line = _rgb(accent_color)
            if kicker == 'tracked':  # small, widely spaced and soft - a quiet category line, not a label
                _draw_spaced(draw, x, y, text, font, _rgb(muted_color or ink), spacing=spacing, align=align)
            elif kicker == 'plain':
                _draw_spaced(draw, x, y, text, font, line, spacing=spacing, align=align)
            elif align == 'center':  # thin rules either side of the kicker (shorter for the 'bar' look)
                rule = int(width * (0.1 if kicker == 'rules' else 0.05))
                gap_x = int(width * 0.02)
                _draw_spaced(draw, x, y, text, font, line, spacing=spacing, align='center')
                draw.line([(x - text_w / 2 - gap_x - rule, mid), (x - text_w / 2 - gap_x, mid)], fill=line, width=2)
                draw.line([(x + text_w / 2 + gap_x, mid), (x + text_w / 2 + gap_x + rule, mid)], fill=line, width=2)
            else:  # a short bar on the side the text starts from
                rule, gap_x = int(width * 0.05), int(width * 0.015)
                if align == 'left':
                    draw.line([(x, mid), (x + rule, mid)], fill=line, width=3)
                    _draw_spaced(draw, x + rule + gap_x, y, text, font, line, spacing=spacing, align='left')
                else:
                    draw.line([(x - rule, mid), (x, mid)], fill=line, width=3)
                    _draw_spaced(draw, x - rule - gap_x, y, text, font, line, spacing=spacing, align='right')
        elif kind == 'divider':
            _paint_divider(draw, data, x, y, align, width, accent_color)
        elif kind == 'lines':
            lines, font, line_height, role = data[:4]
            tail = data[4] if len(data) > 4 else None
            emphasis = data[5] if len(data) > 5 else None
            fill = _rgb(headline_color if role == 'headline' else body_color)
            for index, text_line in enumerate(lines):
                _draw_line(
                    draw, x, y + index * line_height, text_line, font, fill, align,
                    tail if index == len(lines) - 1 else None,
                    emphasis[index] if emphasis else None, _rgb(accent_color),
                )
        elif kind == 'spaced':
            lines, font, spacing = data[:3]
            for index, text_line in enumerate(lines):
                _draw_spaced(draw, x, y + index * int(font.size * CAPS_LEADING), text_line, font, _rgb(body_color), spacing, align=align)
        elif kind == 'cta':
            _paint_cta(draw, data, x, y, align, ink, accent_color)
        y += part_height


def _paint_divider(draw, style, x, y, align, width, accent_color):
    """A small ornament between the headline and the body: a diamond on a rule, a plain rule or three dots."""
    colour = _rgb(accent_color)
    d = max(4, int(width * 0.008))
    mid = y + d
    span = int(width * 0.14)
    x0, x1 = {'center': (x - span // 2, x + span // 2), 'left': (x, x + span), 'right': (x - span, x)}[align]
    if style == 'diamond' and align == 'center':
        half, notch = int(width * 0.1), int(width * 0.018)
        draw.line([(x - half, mid), (x - notch, mid)], fill=colour, width=2)
        draw.line([(x + notch, mid), (x + half, mid)], fill=colour, width=2)
        draw.polygon([(x, mid - d), (x + d, mid), (x, mid + d), (x - d, mid)], fill=colour)
    elif style == 'diamond':
        draw.line([(x0, mid), (x1, mid)], fill=colour, width=2)
        cx = x0 + d if align == 'left' else x1 - d
        draw.polygon([(cx, mid - d), (cx + d, mid), (cx, mid + d), (cx - d, mid)], fill=colour)
    elif style == 'dot':
        radius, spacing = max(2, d // 2), d * 3
        start = {'center': x - spacing, 'left': x + radius, 'right': x - radius - 2 * spacing}[align]
        for i in range(3):
            cx = start + i * spacing
            draw.ellipse([cx - radius, mid - radius, cx + radius, mid + radius], fill=colour)
    else:  # 'line'
        draw.line([(x0, mid), (x1, mid)], fill=colour, width=3)


def _paint_cta(draw, data, x, y, align, ink, accent_color):
    """The call to action as a filled pill, a filled square-cornered button, an outlined pill or an
    underlined label with an arrow - by the style preset."""
    label, font, box_w, box_h, kind = data
    left = {'center': x - box_w // 2, 'left': x, 'right': x - box_w}[align]
    accent = _rgb(accent_color)
    if kind in ('pill', 'square'):
        radius = box_h // 2 if kind == 'pill' else max(3, box_h // 8)
        draw.rounded_rectangle([left, y, left + box_w, y + box_h], radius=radius, fill=accent)
        label_color = '#FFFFFF' if _contrast_ratio('#FFFFFF', accent_color) >= _contrast_ratio('#000000', accent_color) else '#000000'
        draw.text((left + box_w // 2, y + box_h // 2), label, font=font, fill=_rgb(label_color), anchor='mm')
    elif kind == 'outline':
        draw.rounded_rectangle([left, y, left + box_w, y + box_h], radius=box_h // 2, outline=accent, width=3)
        draw.text((left + box_w // 2, y + box_h // 2), label, font=font, fill=_rgb(ink), anchor='mm')
    else:  # 'underline': label, a rule beneath it and an arrow after it
        label_w = int(draw.textlength(label, font=font))
        draw.text((left, y), label, font=font, fill=_rgb(ink), anchor='la')
        base_y = y + int(font.size * 1.35)
        draw.line([(left, base_y), (left + label_w, base_y)], fill=accent, width=3)
        arrow_x, arrow_y, head = left + label_w + int(font.size * 0.5), y + int(font.size * 0.55), int(font.size * 0.3)
        draw.line([(arrow_x, arrow_y), (arrow_x + int(font.size * 0.9), arrow_y)], fill=accent, width=3)
        tip = arrow_x + int(font.size * 0.9)
        draw.polygon([(tip, arrow_y - head), (tip + head, arrow_y), (tip, arrow_y + head)], fill=accent)


# --- logo

def _logo_size(mark, width, height):
    """(w, h) the logo is drawn at: its width share of the picture, capped by its height share."""
    mark_w = int(width * LOGO_WIDTH_FRACTION)
    mark_h = int(mark.height * mark_w / mark.width)
    if mark_h > height * LOGO_MAX_HEIGHT_FRACTION:
        mark_h = int(height * LOGO_MAX_HEIGHT_FRACTION)
        mark_w = int(mark.width * mark_h / mark.height)
    return max(1, mark_w), max(1, mark_h)


def _draw_plate(base, rect, color):
    """A rounded plate of `color` behind rect (the logo): nearly opaque, with a fully rounded end and an antialiased
    edge, so it reads as a deliberate brand tag and not a smudge on the picture."""
    left, top, right, bottom = rect
    pad_x, pad_y = int(base.width * 0.024), int(base.width * 0.014)
    box = (left - pad_x, top - pad_y, right + pad_x, bottom + pad_y)
    size = (box[2] - box[0], box[3] - box[1])
    scale = 3  # drawn at 3x and reduced, for a smooth edge
    mask = Image.new('L', (size[0] * scale, size[1] * scale), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, size[0] * scale - 1, size[1] * scale - 1], radius=size[1] * scale // 2, fill=236)
    layer = Image.new('RGBA', size, (*_rgb(color), 255))
    layer.putalpha(mask.resize(size, Image.LANCZOS))
    base.alpha_composite(layer, (max(0, box[0]), max(0, box[1])), (max(0, -box[0]), max(0, -box[1])))


def _draw_logo(base, mark, rect, primary):
    """The original logo file, resized into `rect` and composited as it is - never redrawn by AI and never
    recoloured, so its sharpness, colours and proportions are kept. The backdrop can be any colour (a brown
    logo on an orange sky is unreadable), so where the logo's own colours would not stand out from what is
    behind it, a clean rounded plate of a contrasting tone (white behind a dark logo, a deep brand tone behind a
    light one) is put behind it instead."""
    left, top, right, bottom = rect
    mark = mark.resize((max(1, right - left), max(1, bottom - top)), Image.LANCZOS)
    backdrop = ImageStat.Stat(base.crop(rect).convert('RGB')).mean
    backdrop_hex = '#%02X%02X%02X' % tuple(int(v) for v in backdrop)
    own = ImageStat.Stat(mark.convert('RGB'), mask=mark.getchannel('A')).mean
    own_hex = '#%02X%02X%02X' % tuple(int(v) for v in own)
    # A logo that kept its own opaque background (it could not be keyed out) is a solid rectangle already.
    keeps_background = ImageStat.Stat(mark.getchannel('A').point(lambda v: 255 if v > 128 else 0)).mean[0] > 0.9 * 255
    if not keeps_background and _contrast_ratio(own_hex, backdrop_hex) < 3.0:
        plate = '#FFFFFF' if _relative_luminance(own_hex) < 0.4 else _mix(primary, (0, 0, 0), 0.7)
        _draw_plate(base, rect, plate)
    base.alpha_composite(mark, (left, top))
