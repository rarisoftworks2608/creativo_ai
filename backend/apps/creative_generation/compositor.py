"""Applies the brand layer onto an AI-generated creative (Epic 06: AI Creative Generation).

Diffusion image models are unreliable at rendering legible text and can never reproduce a
real logo - even top-tier ones misspell headlines and invent marks. So the image model is
told to produce a clean, plain-background picture of ONE subject only (see
prompts.build_image_prompt) and everything brand-specific is drawn on top here with Pillow,
from the real assets and the real copy.

One design system for every creative type (project_plan.md, "Festive Creative Plan" and the
design-system note under it; reference image docs/festive-design-flow.jpg): plain light background,
one hero subject, the brand logo large in the TOP-RIGHT corner, and a text stack whose position is
the only thing that differs by type (layouts.py) - centred below the subject, or left-aligned at
the top beside the logo. Festival creatives use the greeting style (small greeting word, festival
name, ornament divider, wish); every other type uses kicker / headline / body / CTA pill.

The picture is never covered: the text goes where there is no subject, and the canvas is extended
with plain background when the picture has no room left for it.
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


# --------------------------------------------------------------------------- the plain design system

DEFAULT_ASPECT = 1.25        # 4:5 portrait - Instagram 1080 x 1350 (stories pass 16:9)
MAX_GROWTH_RATIO = 1.45      # the canvas is never grown taller than 1 : 1.45 to make room for text
LOGO_WIDTH_FRACTION = 0.32   # logo width as a share of the image width
LOGO_MAX_HEIGHT_FRACTION = 0.11


def compose_creative(
    image_bytes, mime_type, *,
    eyebrow='', headline='', description='', cta='',
    logo_bytes=None, symbol_bytes=None, brand_profile=None,
    layout='standard', placement='below', aspect=DEFAULT_ASPECT, background='plain',
):
    """Returns (composited_bytes, 'image/jpeg'), or the input unchanged if there is nothing to
    apply. `logo_bytes` (BrandProfile.logo) takes priority over `symbol_bytes`
    (BrandProfile.secondary_logo) - only one mark is ever drawn, always top-right.

    `layout` is the text style - 'festive' (greeting, divider, wish; always centred below) or
    'standard' (kicker, headline, body, CTA pill) - and `placement` is 'below' (centred under the
    subject) or 'top' (left-aligned at the top-left, beside the logo); see layouts.py.

    `background` is 'plain' (the picture is one subject on a plain background: the canvas is fitted and
    extended around it and the text sits on the bare background) or 'scene' (a full photograph the admin
    described: it is never extended or smoothed, and the text and logo are drawn over it on a soft
    gradient of the brand colour). The text and the logo are in the same place either way."""
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
    placement = 'top' if (placement == 'top' and layout != 'festive') else 'below'

    if background == 'scene':
        base = _crop_taller_than(base, aspect)
        base = _draw_scene_layout(
            base, style=layout, placement=placement,
            eyebrow=eyebrow, headline=headline, description=description, cta=cta,
            primary=primary, accent=accent, mark=mark, brand_profile=brand_profile,
        )
    else:
        base = _fit_to_aspect(base, aspect, placement)
        base = _draw_plain_layout(
            base, style=layout, placement=placement, aspect=aspect,
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


def _mark_brightness(mark):
    """Average brightness (0-1) of the logo's visible pixels."""
    return ImageStat.Stat(mark.convert('L'), mask=mark.getchannel('A')).mean[0] / 255


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


# --- canvas helpers: fitting the picture to 4:5 / 9:16 and growing it with plain background

def _extend_down(base, extra):
    """`base` with `extra` more pixels added below, continuing its bottom edge. On a plain edge
    that is the average of the last rows stretched down and smoothed (so grain does not become
    vertical streaks). If something touches the bottom edge (a subject placed low) stretching it
    would smear its colours into streaks, so the extension instead starts as a heavily blurred
    version of the edge and fades into the picture's plain background colour."""
    if extra <= 0:
        return base
    width, height = base.size
    edge = base.crop((0, max(0, height - 12), width, height)).resize((width, 1), Image.BOX)
    row = list(edge.convert('RGB').getdata())
    median = tuple(sorted(px[i] for px in row)[width // 2] for i in range(3))
    busy = sum(1 for px in row if abs(px[0] - median[0]) + abs(px[1] - median[1]) + abs(px[2] - median[2]) > 60)
    if busy <= 0.06 * width:
        strip = edge.resize((width, extra)).filter(ImageFilter.GaussianBlur(6))
    else:
        softened = edge.filter(ImageFilter.GaussianBlur(max(2, width // 12))).resize((width, extra))
        flat = Image.new('RGBA', (width, extra), (*median, 255))
        ramp = max(1, int(extra * 0.6))
        mask = Image.new('L', (1, extra))
        for y in range(extra):
            mask.putpixel((0, y), min(255, int(255 * y / ramp)))
        strip = Image.composite(flat, softened.convert('RGBA'), mask.resize((width, extra)))
    extended = Image.new('RGBA', (width, height + extra))
    extended.paste(base, (0, 0))
    extended.paste(strip, (0, height))
    return extended


def _extend_up(base, extra):
    flipped = base.transpose(Image.Transpose.FLIP_TOP_BOTTOM)
    return _extend_down(flipped, extra).transpose(Image.Transpose.FLIP_TOP_BOTTOM)


def _fit_to_aspect(base, aspect, placement):
    """Brings the image to the portrait ratio (4:5, or 9:16 for stories). A taller image (e.g.
    OpenAI's 2:3) is centre-cropped; a square or near-square one (e.g. Cloudflare FLUX) is extended
    on the side the text goes (below, or above for the 'top' placement) by continuing its edge - the
    background is plain by design, so only empty background is ever trimmed or added. A clearly
    landscape image is left alone: stretching it to portrait would invent most of the picture."""
    width, height = base.size
    target = int(width * aspect)
    if height > target:
        top = (height - target) // 2
        return base.crop((0, top, width, top + target))
    if height < target and height >= width * 0.9:
        extra = target - height
        return _extend_up(base, extra) if placement == 'top' else _extend_down(base, extra)
    return base


def _content_bottom(base, min_height):
    """The y below which the picture is plain background: the bottom of its lowest substantial
    subject. A row counts as "subject" when a noticeable share of its pixels differ strongly from
    that row's own typical colour (a plain row - even a gradient or vignette one - has none), and a
    subject is a run of such rows at least `min_height` tall, so thin stray marks (a line of
    painted lettering, a watermark) are not mistaken for it."""
    scale = 4
    small = base.convert('RGB').resize((max(1, base.width // scale), max(1, base.height // scale)), Image.BOX)
    pixels = small.load()
    w, h = small.size
    flags = []
    for y in range(h):
        row = [pixels[x, y] for x in range(w)]
        median = tuple(sorted(px[i] for px in row)[w // 2] for i in range(3))
        far = sum(1 for px in row if abs(px[0] - median[0]) + abs(px[1] - median[1]) + abs(px[2] - median[2]) > 60)
        flags.append(far > 0.06 * w)
    bottom, run_start, last_flag, gap = 0, None, 0, 0
    for y, flag in enumerate(flags + [False] * 4):
        if flag:
            if run_start is None:
                run_start = y
            last_flag, gap = y, 0
        elif run_start is not None:
            gap += 1
            if gap > 2:  # a 2-row (8px) dip does not split one subject in two
                if (last_flag + 1 - run_start) * scale >= min_height:
                    bottom = (last_flag + 1) * scale
                run_start = None
    return bottom


def _content_top(base, min_height):
    """The y above which the picture is plain background (== its height when there is no subject)."""
    return base.height - _content_bottom(base.transpose(Image.Transpose.FLIP_TOP_BOTTOM), min_height)


def _clear_stray_marks(base, y_start, y_end, fade_edge, ramp):
    """Smooths rows y_start..y_end - the part of the picture the text will sit on - so any lettering
    or watermark the image model painted there disappears and the only words are the admin's own.
    A median filter (at quarter size) removes thin strokes but keeps gradients, so unlike painting
    over the area with a flat colour it leaves no panel or seam. The effect fades in over `ramp`
    pixels at the edge facing the subject ('top' edge of a bottom zone, 'bottom' edge of a top zone)."""
    width = base.width
    y_start, y_end = max(0, y_start), min(base.height, y_end)
    zone_height = y_end - y_start
    if zone_height < 16:
        return
    scale = 4
    zone = base.crop((0, y_start, width, y_end)).convert('RGB')
    small = zone.resize((max(1, width // scale), max(1, zone_height // scale)), Image.BOX)
    cleaned = small.filter(ImageFilter.MedianFilter(11)).resize((width, zone_height), Image.BICUBIC).convert('RGBA')
    ramp = max(1, ramp)
    mask = Image.new('L', (1, zone_height))
    for y in range(zone_height):
        distance = y if fade_edge == 'top' else zone_height - 1 - y
        mask.putpixel((0, y), min(255, int(255 * distance / ramp)))
    cleaned.putalpha(mask.resize((width, zone_height)))
    base.alpha_composite(cleaned, (0, y_start))


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


def _build_text_parts(draw, *, style, centered, text_width, width, eyebrow, headline, description, cta, brand_profile):
    """The text stack, top to bottom, as (kind, data, height, gap_before) tuples."""
    parts = []
    if style == 'festive':
        name = headline or eyebrow
        small = eyebrow if headline else ''
        if name:
            size = max(40, int(width * 0.13))
            name_font = _headline_font('bold', size, name)
            while size > 36 and draw.textlength(name, font=name_font) > text_width:
                size -= 2
                name_font = _headline_font('bold', size, name)
            if small:
                small_font = _headline_font('regular', max(24, int(name_font.size * 0.5)), small)
                parts.append(('small', (small, small_font), small_font.size, 0))
            parts.append(('name', (name, name_font), int(name_font.size * (1.5 if _has_devanagari(name) else 1.15)), 0))
        if description:
            wish_font = _brand_font(brand_profile, 'regular', max(16, int(width * 0.032)), description)
            lines = _wrapped_lines(draw, description, wish_font, int(width * 0.6), max_lines=3)
            if name:
                parts.append(('divider', None, 0, int(width * 0.03)))
            parts.append(('lines', (lines, wish_font, int(wish_font.size * 1.75), 'wish'), len(lines) * int(wish_font.size * 1.75), int(width * 0.035) if name else 0))
        return parts

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
        parts.append(('lines', (lines, font, int(font.size * 1.2), 'headline'), len(lines) * int(font.size * 1.2), 0))
    if description:
        font = _brand_font(brand_profile, 'regular', max(16, int(width * 0.03)), description)
        lines = _wrapped_lines(draw, description, font, text_width if not centered else int(width * 0.74), max_lines=3)
        parts.append(('lines', (lines, font, int(font.size * 1.55), 'body'), len(lines) * int(font.size * 1.55), int(width * 0.025) if parts else 0))
    if cta:
        font = _brand_font(brand_profile, 'semibold', max(15, int(width * 0.03)), cta)
        pill_h = int(font.size * 2.3)
        parts.append(('cta', (cta.upper(), font, int(draw.textlength(cta.upper(), font=font) + pill_h * 0.9), pill_h), pill_h, int(width * 0.04) if parts else 0))
    return parts


def _draw_plain_layout(base, *, style, placement, aspect, eyebrow, headline, description, cta, primary, accent, mark, brand_profile):
    """The text stack plus the logo on the plain background. The layout adapts to the picture
    instead of assuming where the subject is: the text goes where there is no subject, and if the
    picture has no room left for it the canvas is extended with plain background (the subject is
    never covered or cut). Returns the finished image, which may be taller than the one passed in."""
    width = base.width
    pad = int(width * 0.06)
    top_anchored = placement == 'top'
    centered = not top_anchored
    edge_margin = pad if top_anchored else int(width * 0.09)
    text_width = int(width * 0.52) if top_anchored else int(width * 0.88)

    parts = _build_text_parts(
        ImageDraw.Draw(base), style=style, centered=centered, text_width=text_width, width=width,
        eyebrow=eyebrow, headline=headline, description=description, cta=cta, brand_profile=brand_profile,
    )
    total = sum(height + gap for _kind, _data, height, gap in parts)

    if parts:
        height = base.height
        subject_gap = int(width * 0.05)
        min_subject = int(height * 0.07)
        room = max(0, int(width * max(MAX_GROWTH_RATIO, aspect + 0.2)) - height)
        if top_anchored:
            subject_top = _content_top(base, min_subject)
            needed = edge_margin + total + subject_gap - subject_top
            if needed > 0:
                grow = min(needed, room)
                base = _extend_up(base, grow)
                subject_top += grow
            block_top = edge_margin
            _clear_stray_marks(
                base, 0, min(subject_top - 4, block_top + total + 64), 'bottom', ramp=min(64, max(1, subject_top - 4 - (block_top + total))),
            )
        else:
            subject_bottom = _content_bottom(base, min_subject)
            needed = subject_bottom + subject_gap - (height - edge_margin - total)
            if needed > 0:
                base = _extend_down(base, min(needed, room))
            block_top = base.height - edge_margin - total
            _clear_stray_marks(
                base, max(subject_bottom + 4, block_top - 64), base.height, 'top', ramp=min(64, max(1, block_top - subject_bottom - 4)),
            )

        draw = ImageDraw.Draw(base)
        zone = base.crop((0, max(0, block_top), width, min(base.height, block_top + total))).convert('RGB')
        background = '#%02X%02X%02X' % tuple(int(v) for v in ImageStat.Stat(zone).mean)
        dark = _relative_luminance(background) <= 0.4
        ink = '#FFFFFF' if dark else _ensure_contrast(_mix(primary, (0, 0, 0), 0.35), background, 4.5)
        accent_color = _ensure_contrast(accent, background, 3.0)
        soft = _mix(ink, _rgb(background), 0.25)
        _paint_parts(
            draw, parts, x=width // 2 if centered else pad, y=block_top, centered=centered, width=width,
            ink=ink, accent_color=accent_color, soft=soft, background=background, dark=dark,
        )

    if mark is not None:
        _place_logo(base, mark, primary, pad)
    return base


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


def _draw_scene_layout(base, *, style, placement, eyebrow, headline, description, cta, primary, accent, mark, brand_profile):
    """The same text stack and logo, drawn over a full photograph instead of a plain background: white
    text with the brand accent on a soft gradient of the (darkened) brand colour at the edge the text
    sits on, and the logo top-right in white with a faint shadow. Nothing is extended, cropped away or
    smoothed, so the scene the admin described is shown whole."""
    width, height = base.size
    pad = int(width * 0.06)
    top_anchored = placement == 'top'
    centered = not top_anchored
    edge_margin = pad if top_anchored else int(width * 0.09)
    text_width = int(width * 0.52) if top_anchored else int(width * 0.88)
    parts = _build_text_parts(
        ImageDraw.Draw(base), style=style, centered=centered, text_width=text_width, width=width,
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
            ImageDraw.Draw(base), parts, x=width // 2 if centered else pad, y=block_top, centered=centered, width=width,
            ink='#FFFFFF', accent_color=_ensure_contrast(accent, deep, 3.0), soft=_mix('#FFFFFF', _rgb(deep), 0.2),
            background=deep, dark=True,
        )
    if mark is not None:
        _place_logo(base, mark, primary, pad, scene=True)
    return base


def _paint_parts(draw, parts, *, x, y, centered, width, ink, accent_color, soft, background, dark):
    """Draws the text stack top to bottom starting at y, centred on x or left-aligned at x."""
    anchor = 'ma' if centered else 'la'
    for kind, data, part_height, gap in parts:
        y += gap
        if kind == 'small':
            draw.text((x, y), data[0], font=data[1], fill=_rgb(soft), anchor=anchor)
        elif kind == 'name':
            draw.text((x, y), data[0], font=data[1], fill=_rgb(accent_color), anchor=anchor)
        elif kind == 'eyebrow':
            _draw_spaced(draw, x, y, data[0].upper(), data[1], _rgb(accent_color), spacing=3, centered=centered)
        elif kind == 'divider':
            half, notch = int(width * 0.12), int(width * 0.018)
            line_color = _rgb(_mix(accent_color, _rgb(background), 0.2))
            draw.line([(x - half, y), (x - notch, y)], fill=line_color, width=2)
            draw.line([(x + notch, y), (x + half, y)], fill=line_color, width=2)
            d = max(4, int(width * 0.008))
            draw.polygon([(x, y - d), (x + d, y), (x, y + d), (x - d, y)], fill=line_color)
        elif kind == 'lines':
            lines, font, line_height, role = data
            for index, line in enumerate(lines):
                top = y + index * line_height
                if role == 'wish':
                    _draw_spaced(draw, x, top, line, font, _rgb(ink), spacing=1.5, centered=centered)
                else:
                    draw.text((x, top), line, font=font, fill=_rgb(ink), anchor=anchor)
        elif kind == 'cta':
            label, font, pill_w, pill_h = data
            left = x - pill_w // 2 if centered else x
            fill = accent_color
            draw.rounded_rectangle([left, y, left + pill_w, y + pill_h], radius=pill_h // 2, fill=_rgb(fill))
            label_color = '#FFFFFF' if _contrast_ratio('#FFFFFF', fill) >= _contrast_ratio(ink if not dark else '#000000', fill) else (ink if not dark else '#000000')
            draw.text((left + pill_w // 2, y + pill_h // 2), label, font=font, fill=_rgb(label_color), anchor='mm')
        y += part_height


def _place_logo(base, mark, primary, pad, scene=False):
    """The logo, large, in the top-right corner at a consistent margin, straight onto the
    background (no plate): in its own colours on a light background, white on a dark one, and in
    the brand's dark tone if the logo itself is too pale to show. Over a photograph (scene=True)
    a white logo also gets a faint shadow."""
    width, height = base.size
    mark_w = int(width * LOGO_WIDTH_FRACTION)
    mark_h = int(mark.height * mark_w / mark.width)
    if mark_h > height * LOGO_MAX_HEIGHT_FRACTION:
        mark_h = int(height * LOGO_MAX_HEIGHT_FRACTION)
        mark_w = int(mark.width * mark_h / mark.height)
    mark = mark.resize((max(1, mark_w), max(1, mark_h)), Image.LANCZOS)
    x, y = width - pad - mark_w, pad
    backdrop = ImageStat.Stat(base.crop((x, y, x + mark_w, y + mark_h)).convert('L')).mean[0] / 255
    light_logo = False
    if scene:
        # Over a photograph the backdrop can be any colour (a brown logo on an orange sky is unreadable),
        # so use the logo's own colours only if they contrast enough, else white or the brand's dark tone,
        # whichever contrasts more.
        mean = ImageStat.Stat(base.crop((x, y, x + mark_w, y + mark_h)).convert('RGB')).mean
        backdrop_hex = '#%02X%02X%02X' % tuple(int(v) for v in mean)
        own = ImageStat.Stat(mark.convert('RGB'), mask=mark.getchannel('A')).mean
        own_hex = '#%02X%02X%02X' % tuple(int(v) for v in own)
        dark_hex = _mix(primary, (0, 0, 0), 0.55)
        if _contrast_ratio(own_hex, backdrop_hex) >= 4.0:
            pass
        elif _contrast_ratio('#FFFFFF', backdrop_hex) >= _contrast_ratio(dark_hex, backdrop_hex):
            mark = _silhouette(mark, '#FFFFFF')
            light_logo = True
        else:
            mark = _silhouette(mark, dark_hex)
    elif backdrop < 0.5:
        mark = _silhouette(mark, '#FFFFFF')
        light_logo = True
    elif _mark_brightness(mark) > 0.6:
        mark = _silhouette(mark, _mix(primary, (0, 0, 0), 0.45))
    if scene and light_logo:
        # A white logo over a photograph needs a faint shadow to stay readable on lighter patches.
        shadow = Image.new('RGBA', mark.size, (0, 0, 0, 0))
        shadow.putalpha(mark.getchannel('A').point(lambda v: int(v * 0.55)))
        layer = Image.new('RGBA', base.size, (0, 0, 0, 0))
        layer.alpha_composite(shadow, (x, y + 2))
        base.alpha_composite(layer.filter(ImageFilter.GaussianBlur(max(2, mark_w // 80))))
    base.alpha_composite(mark, (x, y))
