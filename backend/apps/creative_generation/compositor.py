"""Applies the brand layer onto an AI-generated creative (Epic 06: AI Creative Generation).

Diffusion image models are unreliable at rendering legible text and can never reproduce a
real logo - even top-tier ones misspell headlines and invent marks. So the image model is
asked for the full scene only (see prompts.build_image_prompt) and everything brand-specific is
drawn on top here with Pillow, from the real assets and the real copy.

One brand alignment template for every creative type (layouts.py): the brand logo large in the
TOP-RIGHT corner, and a text stack (kicker, headline, body, CTA pill in the brand fonts and colours)
whose position is the only thing that differs by type - centred along the bottom, or left-aligned at
the top beside the logo. The scene is never extended, stretched or smoothed; the text sits on a soft
gradient of the brand colour at the edge it is placed on.
"""

import io
import re
import unicodedata
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont, ImageStat

FONT_DIR = Path(__file__).resolve().parent / 'fonts'

# BrandProfile.fonts only stores a family name (e.g. "Poppins") - there's no uploaded font
# file - so brand font selection is a name match against this bundled, open-license set
# rather than truly arbitrary fonts. "variable" fonts carry every weight in one file,
# selected at render time via set_variation_by_name(); "bold"/"semibold" are separate
# static files for families that don't ship a variable version.
BRAND_FONT_LIBRARY = {
    'poppins': {'bold': FONT_DIR / 'Poppins-Bold.ttf', 'semibold': FONT_DIR / 'Poppins-SemiBold.ttf'},
    'montserrat': {'variable': FONT_DIR / 'Montserrat-Variable.ttf'},
    'roboto': {'variable': FONT_DIR / 'Roboto-Variable.ttf'},
    'inter': {'variable': FONT_DIR / 'Inter-Variable.ttf'},
    'playfair display': {'variable': FONT_DIR / 'PlayfairDisplay-Variable.ttf'},
    'open sans': {'variable': FONT_DIR / 'OpenSans-Variable.ttf'},
    'lato': {'bold': FONT_DIR / 'Lato-Bold.ttf', 'semibold': FONT_DIR / 'Lato-SemiBold.ttf'},
}
DEFAULT_FONT_FAMILY = 'poppins'
HEADLINE_FONT_FAMILY = 'playfair display'

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


def _load_font(spec, weight, size):
    """`weight` is 'bold', 'semibold' or 'regular'. Families shipped as static files only have
    bold/semibold, so 'regular' falls back to semibold for them."""
    if 'variable' in spec:
        font = ImageFont.truetype(str(spec['variable']), size)
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


# --------------------------------------------------------------------------- the brand alignment template

DEFAULT_ASPECT = 1.25        # 4:5 portrait - Instagram 1080 x 1350 (stories pass 16:9)
LOGO_WIDTH_FRACTION = 0.32   # logo width as a share of the image width
LOGO_MAX_HEIGHT_FRACTION = 0.11


def compose_creative(
    image_bytes, mime_type, *,
    eyebrow='', headline='', description='', cta='',
    logo_bytes=None, symbol_bytes=None, brand_profile=None,
    placement='below', aspect=DEFAULT_ASPECT,
):
    """Returns (composited_bytes, 'image/jpeg'), or the input unchanged if there is nothing to
    apply. `logo_bytes` (BrandProfile.logo) takes priority over `symbol_bytes`
    (BrandProfile.secondary_logo) - only one mark is ever drawn, always top-right.

    The picture is the full scene the image AI drew: it is never extended, stretched or smoothed
    (one taller than `aspect` is centre-cropped to it, anything else is kept as drawn). The text
    and the logo are drawn over it on a soft gradient of the brand colour. `placement` is 'below'
    (text centred along the bottom) or 'top' (text left-aligned at the top-left, beside the logo);
    the logo is top-right either way - see layouts.py."""
    mark_bytes = logo_bytes or symbol_bytes
    if not any([eyebrow, headline, description, cta, mark_bytes]):
        return image_bytes, mime_type

    eyebrow = _sanitize_text(eyebrow)
    headline = _sanitize_text(headline)
    description = _sanitize_text(description)
    cta = _sanitize_text(cta)

    base = Image.open(io.BytesIO(image_bytes)).convert('RGBA')
    primary, accent = _brand_colors(brand_profile)
    mark = _prepare_mark(mark_bytes) if mark_bytes else None

    base = _crop_taller_than(base, aspect)
    base = _draw_layout(
        base, placement='top' if placement == 'top' else 'below',
        eyebrow=eyebrow, headline=headline, description=description, cta=cta,
        primary=primary, accent=accent, mark=mark, brand_profile=brand_profile,
    )

    output = io.BytesIO()
    base.convert('RGB').save(output, format='JPEG', quality=95)
    return output.getvalue(), 'image/jpeg'


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


def _silhouette(mark, color):
    """The logo recolored to one solid color (a "reversed" logo), keeping its shape."""
    solid = Image.new('RGBA', mark.size, (*_rgb(color), 255))
    solid.putalpha(mark.getchannel('A'))
    return solid


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

def _draw_spaced(draw, x, top, text, font, fill, spacing, centered=True):
    """Text with extra letter spacing (Pillow has no built-in tracking), centred on x or starting at x."""
    if _has_devanagari(text):
        # Letter by letter would pull the vowel signs (matras) off their consonants; draw it whole.
        draw.text((x, top), text, font=font, fill=fill, anchor='ma' if centered else 'la')
        return
    widths = [draw.textlength(char, font=font) for char in text]
    total = sum(widths) + spacing * (len(text) - 1)
    cursor = x - total / 2 if centered else x
    for char, char_width in zip(text, widths):
        draw.text((cursor, top), char, font=font, fill=fill)
        cursor += char_width + spacing


def _build_text_parts(draw, *, centered, text_width, width, eyebrow, headline, description, cta, brand_profile):
    """The text stack, top to bottom, as (kind, data, height, gap_before) tuples: kicker, headline,
    body copy and a CTA pill - each only if there is text for it."""
    parts = []
    if eyebrow:
        font = _brand_font(brand_profile, 'semibold', max(14, int(width * 0.026)), eyebrow)
        parts.append(('eyebrow', (eyebrow, font), int(font.size * 1.7), 0))
    if headline:
        size = max(30, int(width * 0.085))
        font = _headline_font('bold', size, headline)
        longest = max(headline.split(), key=len)
        while size > 24 and draw.textlength(longest, font=font) > text_width:
            size -= 2
            font = _headline_font('bold', size, headline)
        lines = _wrapped_lines(draw, headline, font, text_width, max_lines=3)
        parts.append(('lines', (lines, font, int(font.size * 1.2)), len(lines) * int(font.size * 1.2), 0))
    if description:
        font = _brand_font(brand_profile, 'regular', max(16, int(width * 0.03)), description)
        lines = _wrapped_lines(draw, description, font, text_width if not centered else int(width * 0.74), max_lines=3)
        parts.append(('lines', (lines, font, int(font.size * 1.55)), len(lines) * int(font.size * 1.55), int(width * 0.025) if parts else 0))
    if cta:
        font = _brand_font(brand_profile, 'semibold', max(15, int(width * 0.03)), cta)
        pill_h = int(font.size * 2.3)
        parts.append(('cta', (cta.upper(), font, int(draw.textlength(cta.upper(), font=font) + pill_h * 0.9), pill_h), pill_h, int(width * 0.04) if parts else 0))
    return parts


def _vertical_gradient(size, color, max_alpha):
    """Solid `color` whose opacity ramps from 0 at the top to max_alpha 70% of the way down."""
    width, height = size
    column = Image.new('L', (1, height))
    for y in range(height):
        column.putpixel((0, y), int(max_alpha * min(1.0, (y / max(height - 1, 1)) / 0.7) ** 1.4))
    solid = Image.new('RGBA', size, (*_rgb(color), 255))
    solid.putalpha(column.resize((width, height)))
    return solid


def _crop_taller_than(base, aspect):
    """A scene picture is never invented or stretched: one taller than the portrait ratio is centre-cropped
    to it, anything else is kept exactly as the image AI drew it."""
    width, height = base.size
    target = int(width * aspect)
    if height <= target:
        return base
    top = (height - target) // 2
    return base.crop((0, top, width, top + target))


def _draw_layout(base, *, placement, eyebrow, headline, description, cta, primary, accent, mark, brand_profile):
    """The text stack and the logo, drawn over the full scene: white text with the brand accent on a
    soft gradient of the (darkened) brand colour at the edge the text sits on, and the logo large in
    the top-right corner. Nothing is extended, cropped away or smoothed, so the scene is shown whole."""
    width, height = base.size
    pad = int(width * 0.06)
    top_anchored = placement == 'top'
    centered = not top_anchored
    edge_margin = pad if top_anchored else int(width * 0.09)
    text_width = int(width * 0.52) if top_anchored else int(width * 0.88)
    parts = _build_text_parts(
        ImageDraw.Draw(base), centered=centered, text_width=text_width, width=width,
        eyebrow=eyebrow, headline=headline, description=description, cta=cta, brand_profile=brand_profile,
    )
    if parts:
        total = sum(part_height + gap for _kind, _data, part_height, gap in parts)
        deep = _mix(primary, (0, 0, 0), 0.62)  # dark brand tone: white text on it always reads
        scrim_height = min(int(height * 0.7), edge_margin + total + pad * 3)
        scrim = _vertical_gradient((width, scrim_height), deep, 225)
        if top_anchored:
            base.alpha_composite(scrim.transpose(Image.Transpose.FLIP_TOP_BOTTOM), (0, 0))
            block_top = edge_margin
        else:
            base.alpha_composite(scrim, (0, height - scrim_height))
            block_top = height - edge_margin - total
        _paint_parts(
            ImageDraw.Draw(base), parts, x=width // 2 if centered else pad, y=block_top, centered=centered,
            ink='#FFFFFF', accent_color=_ensure_contrast(accent, deep, 3.0),
        )
    if mark is not None:
        _place_logo(base, mark, primary, pad)
    return base


def _paint_parts(draw, parts, *, x, y, centered, ink, accent_color):
    """Draws the text stack top to bottom starting at y, centred on x or left-aligned at x."""
    anchor = 'ma' if centered else 'la'
    for kind, data, part_height, gap in parts:
        y += gap
        if kind == 'eyebrow':
            _draw_spaced(draw, x, y, data[0].upper(), data[1], _rgb(accent_color), spacing=3, centered=centered)
        elif kind == 'lines':
            lines, font, line_height = data
            for index, line in enumerate(lines):
                draw.text((x, y + index * line_height), line, font=font, fill=_rgb(ink), anchor=anchor)
        elif kind == 'cta':
            label, font, pill_w, pill_h = data
            left = x - pill_w // 2 if centered else x
            draw.rounded_rectangle([left, y, left + pill_w, y + pill_h], radius=pill_h // 2, fill=_rgb(accent_color))
            label_color = '#FFFFFF' if _contrast_ratio('#FFFFFF', accent_color) >= _contrast_ratio('#000000', accent_color) else '#000000'
            draw.text((left + pill_w // 2, y + pill_h // 2), label, font=font, fill=_rgb(label_color), anchor='mm')
        y += part_height


def _place_logo(base, mark, primary, pad):
    """The logo, large, in the top-right corner at a consistent margin, straight onto the picture
    (no plate). The backdrop can be any colour (a brown logo on an orange sky is unreadable), so the
    logo keeps its own colours only if they contrast enough with what is behind it, else it is drawn
    in white or the brand's dark tone, whichever contrasts more. A white logo also gets a faint
    shadow to stay readable on lighter patches."""
    width, height = base.size
    mark_w = int(width * LOGO_WIDTH_FRACTION)
    mark_h = int(mark.height * mark_w / mark.width)
    if mark_h > height * LOGO_MAX_HEIGHT_FRACTION:
        mark_h = int(height * LOGO_MAX_HEIGHT_FRACTION)
        mark_w = int(mark.width * mark_h / mark.height)
    mark = mark.resize((max(1, mark_w), max(1, mark_h)), Image.LANCZOS)
    x, y = width - pad - mark_w, pad
    mean = ImageStat.Stat(base.crop((x, y, x + mark_w, y + mark_h)).convert('RGB')).mean
    backdrop_hex = '#%02X%02X%02X' % tuple(int(v) for v in mean)
    own = ImageStat.Stat(mark.convert('RGB'), mask=mark.getchannel('A')).mean
    own_hex = '#%02X%02X%02X' % tuple(int(v) for v in own)
    dark_hex = _mix(primary, (0, 0, 0), 0.55)
    light_logo = False
    if _contrast_ratio(own_hex, backdrop_hex) >= 4.0:
        pass
    elif _contrast_ratio('#FFFFFF', backdrop_hex) >= _contrast_ratio(dark_hex, backdrop_hex):
        mark = _silhouette(mark, '#FFFFFF')
        light_logo = True
    else:
        mark = _silhouette(mark, dark_hex)
    if light_logo:
        shadow = Image.new('RGBA', mark.size, (0, 0, 0, 0))
        shadow.putalpha(mark.getchannel('A').point(lambda v: int(v * 0.55)))
        layer = Image.new('RGBA', base.size, (0, 0, 0, 0))
        layer.alpha_composite(shadow, (x, y + 2))
        base.alpha_composite(layer.filter(ImageFilter.GaussianBlur(max(2, mark_w // 80))))
    base.alpha_composite(mark, (x, y))
