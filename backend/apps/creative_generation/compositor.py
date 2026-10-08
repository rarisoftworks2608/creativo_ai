"""Applies the brand layer onto an AI-generated creative (Epic 06: AI Creative Generation).

Diffusion image models are unreliable at rendering legible text and can never reproduce a
real logo - even top-tier ones misspell headlines and invent marks. So the image model is
told to produce a clean photograph only (see prompts.build_image_prompt) and everything
brand-specific is drawn on top here with Pillow, from the real assets and the real copy:

  * a soft footer tinted with the brand's own color, carrying the headline, a CTA pill in the
    brand accent color, and the logo (cut out of its background and shown in white, so it
    never sits in a plate), all set in the brand fonts. With no copy to show, the footer is a
    slim strip with just the logo.

The photo itself is never resized or cropped.
"""

import io
import unicodedata
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFont

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

DEFAULT_BANNER_COLOR = '#1A1A1A'  # "ink" - headline/body text color
DEFAULT_ACCENT_COLOR = '#D4A017'  # eyebrow/CTA/divider accent
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


def _sanitize_text(text):
    """Replaces "smart" typographic characters the text AI commonly generates (en/em
    dashes, curly quotes, ...) with visible plain-ASCII equivalents, then strips anything
    else non-ASCII via NFKD decomposition as a final safety net. Not every bundled brand
    font is guaranteed to have a glyph for an arbitrary character, and an unsupported one
    renders as a visible tofu box instead of failing loudly - better to lose an accent or
    an unanticipated symbol than to render a broken-looking box in a client-facing creative.
    """
    for bad, good in _CHAR_REPLACEMENTS.items():
        text = text.replace(bad, good)
    return unicodedata.normalize('NFKD', text).encode('ascii', 'ignore').decode('ascii')


def _brand_font(brand_profile, weight, size):
    """Resolves (family, weight) to a loaded, correctly-weighted ImageFont, matching
    BrandProfile.fonts[0].name against BRAND_FONT_LIBRARY (case-insensitive), falling
    back to Poppins if unset or unrecognized. Used for the eyebrow/description/CTA -
    the brand's own configured font is right for body/UI-style text.
    """
    fonts = list(getattr(brand_profile, 'fonts', None) or [])
    family_name = (fonts[0].get('name') or '').strip().lower() if fonts else ''
    spec = BRAND_FONT_LIBRARY.get(family_name) or BRAND_FONT_LIBRARY[DEFAULT_FONT_FAMILY]
    return _load_font(spec, weight, size)


def _headline_font(weight, size):
    """The headline always uses the bundled premium editorial serif regardless of the
    brand's own configured font - a deliberate design-system choice (project_plan.md's
    "creative plan": "elegant high-contrast serif ... for major headlines", brand's own
    font reserved for supporting copy), not a brand-matching lookup like _brand_font.
    """
    return _load_font(BRAND_FONT_LIBRARY[HEADLINE_FONT_FAMILY], weight, size)


def _load_font(spec, weight, size):
    if 'variable' in spec:
        font = ImageFont.truetype(str(spec['variable']), size)
        font.set_variation_by_name('Bold' if weight == 'bold' else 'SemiBold')
        return font
    return ImageFont.truetype(str(spec[weight]), size)


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


# --------------------------------------------------------------------------- brand layer

def compose_creative(
    image_bytes, mime_type, *,
    eyebrow='', headline='', description='', cta='',
    logo_bytes=None, symbol_bytes=None, brand_profile=None,
):
    """Returns (composited_bytes, 'image/jpeg'), or the input unchanged if there is nothing
    to apply. `logo_bytes` (BrandProfile.logo) takes priority over `symbol_bytes`
    (BrandProfile.secondary_logo) - only one mark is ever drawn."""
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

    if mark is not None or any([eyebrow, headline, description, cta]):
        _draw_brand_footer(
            base, eyebrow=eyebrow, headline=headline, description=description, cta=cta,
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


def _readable_on(color, background, minimum=3.0):
    """`color`, lightened step by step until it reads against `background`."""
    for _ in range(12):
        if _contrast_ratio(color, background) >= minimum:
            break
        color = _mix(color, (255, 255, 255), 0.15)
    return color


def _vertical_gradient(size, color, max_alpha):
    """Solid `color` whose opacity ramps from 0 at the top to max_alpha by 60% of the way down."""
    width, height = size
    column = Image.new('L', (1, height))
    for y in range(height):
        column.putpixel((0, y), int(max_alpha * min(1.0, (y / max(height - 1, 1)) / 0.6) ** 1.5))
    solid = Image.new('RGBA', size, (*_rgb(color), 255))
    solid.putalpha(column.resize((width, height)))
    return solid


def _draw_brand_footer(base, *, eyebrow, headline, description, cta, primary, accent, mark, brand_profile):
    """Eyebrow / headline / (description) above a row holding the logo (left) and the CTA
    pill (right), over a gradient of the brand's own color fading in from the bottom edge.
    Any of those parts may be missing; with only a logo this is just a slim logo strip."""
    width, height = base.size
    unit = min(width, int(height * 0.7))  # keeps a wide landscape image from getting a towering footer
    pad = max(20, int(unit * 0.045))
    max_width = width - 2 * pad
    deep = _mix(primary, (0, 0, 0), 0.62)  # dark brand tone: white text on it is always legible
    accent_on_dark = _readable_on(accent, deep)
    draw = ImageDraw.Draw(base)

    # --- measure everything first, bottom-up, so the gradient can be sized to fit
    row_h = int(unit * 0.085)
    pill = None
    if cta:
        cta_font = _brand_font(brand_profile, 'semibold', max(15, int(unit * 0.03)))
        pill_h = int(row_h * 0.82)
        pill = (cta.upper(), cta_font, int(draw.textlength(cta.upper(), font=cta_font) + pill_h * 0.9), pill_h)
    logo = None
    if mark is not None:
        scale = min(row_h / mark.height, max_width * (0.5 if pill else 0.6) / mark.width)
        logo = _silhouette(mark.resize((max(1, int(mark.width * scale)), max(1, int(mark.height * scale))), Image.LANCZOS), '#FFFFFF')
    has_row = bool(pill or logo)
    row_top = height - pad - (row_h if has_row else 0)
    cursor = row_top - (int(pad * 0.6) if has_row else 0)  # bottom edge of the text block

    lines, font, line_h = [], None, 0
    text = headline or description
    if text:
        size = max(26, int(unit * (0.058 if headline else 0.04)))
        make_font = (lambda px: _headline_font('bold', px)) if headline else (lambda px: _brand_font(brand_profile, 'semibold', px))
        font = make_font(size)
        longest_word = max(text.split(), key=len)
        while size > 20 and draw.textlength(longest_word, font=font) > max_width:
            size -= 2
            font = make_font(size)
        lines = _wrapped_lines(draw, text, font, max_width, max_lines=2 if headline else 3)
        line_h = int(font.size * 1.2)
        cursor -= line_h * len(lines)
    text_top = cursor
    eyebrow_font = None
    if eyebrow:
        eyebrow_font = _brand_font(brand_profile, 'semibold', max(14, int(unit * 0.026)))
        cursor -= int(eyebrow_font.size * 1.6)
    content_top = cursor

    scrim_h = min(int(height * 0.6), height - content_top + pad * 2)
    base.alpha_composite(_vertical_gradient((width, scrim_h), deep, 235), (0, height - scrim_h))
    draw = ImageDraw.Draw(base)

    # --- draw
    if eyebrow_font:
        draw.text((pad, content_top), eyebrow.upper(), font=eyebrow_font, fill=_rgb(accent_on_dark))
    for index, line in enumerate(lines):
        draw.text((pad, text_top + index * line_h), line, font=font, fill=(255, 255, 255))
    if logo is not None:
        base.alpha_composite(logo, (pad, row_top + (row_h - logo.height) // 2))
    if pill:
        text_value, cta_font, pill_w, pill_h = pill
        x1, y0 = width - pad, row_top + (row_h - pill_h) // 2
        draw.rounded_rectangle([x1 - pill_w, y0, x1, y0 + pill_h], radius=pill_h // 2, fill=_rgb(accent_on_dark))
        label_color = '#FFFFFF' if _contrast_ratio('#FFFFFF', accent_on_dark) >= _contrast_ratio(deep, accent_on_dark) else deep
        draw.text((x1 - pill_w // 2, y0 + pill_h // 2), text_value, font=cta_font, fill=_rgb(label_color), anchor='mm')
