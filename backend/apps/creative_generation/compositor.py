"""Overlays brand elements onto an AI-generated creative (Epic 06: AI Creative Generation).

Diffusion image models are unreliable at rendering legible text - even top-tier ones
regularly misspell headlines/CTAs baked into the picture. This module sidesteps that
entirely: the image model is instructed to produce a clean visual only (see
prompts.build_image_prompt), and the eyebrow/headline/description/CTA text - already
generated accurately as plain data by the text AI (Epic 05/06) - is drawn on top here
with Pillow. Since the text is never re-interpreted by an image model, spelling is
always exactly what was generated.

Layout system (project_plan.md's "creative plan" - fixed, not a style choice): the
image is generated RIGHT-hero / LEFT-calm-zone / TOP-RIGHT-logo-safe, vertical 4:5 (see
prompts.build_image_prompt's COMPOSITION section), and this module composites the real
copy into that same LEFT zone and the real logo into that same TOP-RIGHT corner - the
reserved space and the real overlay are two halves of one design, so they must always
target the same geometry.
"""

import io
import unicodedata
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

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

# The fixed layout system's proportions - kept as named constants since prompts.py's
# COMPOSITION section describes these same numbers in English; if either changes, the
# reserved space in the generated photo and the real overlay drift apart.
CONTENT_ZONE_WIDTH_FRACTION = 0.42  # left zone the copy is drawn into (spec: 40-45%)
LOGO_WIDTH_FRACTION = 0.16


def compose_creative(
    image_bytes, mime_type, *,
    eyebrow='', headline='', description='', cta='',
    logo_bytes=None, symbol_bytes=None, brand_profile=None,
):
    """Composites the eyebrow/headline/description/CTA copy into the image's LEFT
    content zone and the brand logo into its TOP-RIGHT corner (each only if the
    corresponding input is provided). Returns (composited_bytes, 'image/jpeg').
    Returns the input unchanged if there's nothing to overlay.
    """
    if not any([eyebrow, headline, description, cta, logo_bytes, symbol_bytes]):
        return image_bytes, mime_type

    eyebrow = _sanitize_text(eyebrow)
    headline = _sanitize_text(headline)
    description = _sanitize_text(description)
    cta = _sanitize_text(cta)

    base = Image.open(io.BytesIO(image_bytes)).convert('RGBA')
    width, height = base.size
    overlay = Image.new('RGBA', base.size, (0, 0, 0, 0))

    ink_color, accent_color = _brand_colors(brand_profile)
    padding = max(24, width // 20)

    if eyebrow or headline or description or cta:
        _draw_left_content_zone(
            overlay, eyebrow=eyebrow, headline=headline, description=description, cta=cta,
            width=width, height=height, padding=padding,
            ink_color=ink_color, accent_color=accent_color, brand_profile=brand_profile,
        )

    # The real brand logo is the single mark placed top-right per the layout system;
    # `logo_bytes` (BrandProfile.logo) takes priority over `symbol_bytes`
    # (BrandProfile.secondary_logo) when both are set, rather than drawing two marks
    # that would now collide with the LEFT content zone or the RIGHT hero subject.
    mark_bytes = logo_bytes or symbol_bytes
    if mark_bytes:
        _place_logo_top_right(overlay, mark_bytes, width, padding, accent_color)

    composed = Image.alpha_composite(base, overlay).convert('RGB')
    output = io.BytesIO()
    composed.save(output, format='JPEG', quality=95)
    return output.getvalue(), 'image/jpeg'


_CHAR_REPLACEMENTS = {
    '–': '-', '—': '-',       # en dash, em dash
    '‘': "'", '’': "'",       # curly single quotes
    '“': '"', '”': '"',       # curly double quotes
    '…': '...',                    # ellipsis
    '•': '-',                      # bullet
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
    words = text.split()
    lines, current = [], ''
    for word in words:
        candidate = f'{current} {word}'.strip()
        if draw.textlength(candidate, font=font) <= max_width or not current:
            current = candidate
        else:
            lines.append(current)
            current = word
        if len(lines) == max_lines - 1:
            break
    if current:
        lines.append(current)
    return lines[:max_lines]


def _horizontal_gradient(size, color, *, left_alpha, right_alpha):
    """A solid-color RGBA image whose alpha fades linearly from left_alpha to
    right_alpha - the scrim behind the LEFT content zone, fading out toward the RIGHT
    hero subject so the photo stays visible there instead of getting covered by a
    hard-edged panel.
    """
    width, height = size
    row = Image.new('L', (width, 1))
    for x in range(width):
        t = x / max(width - 1, 1)
        row.putpixel((x, 0), int(left_alpha + (right_alpha - left_alpha) * t))
    alpha_mask = row.resize((width, height))
    solid = Image.new('RGBA', (width, height), (*_rgb(color), 255))
    solid.putalpha(alpha_mask)
    return solid


def _draw_left_content_zone(overlay, *, eyebrow, headline, description, cta, width, height, padding, ink_color, accent_color, brand_profile):
    """Draws eyebrow -> thin divider -> headline -> description -> CTA, top to bottom,
    inside the LEFT CONTENT_ZONE_WIDTH_FRACTION of the frame - the typography hierarchy
    from project_plan.md's "creative plan" (small kicker, large serif headline,
    supporting sans copy, understated CTA), over a soft white scrim so it stays legible
    regardless of what's actually behind it in the generated photo.
    """
    zone_width = int(width * CONTENT_ZONE_WIDTH_FRACTION)
    # Wider than the zone itself so the fade-out doesn't create a hard edge right at the
    # text boundary - it keeps softening a bit further into the hero side.
    scrim_width = min(width, int(width * (CONTENT_ZONE_WIDTH_FRACTION + 0.16)))
    scrim = _horizontal_gradient((scrim_width, height), WHITE, left_alpha=240, right_alpha=0)
    overlay.alpha_composite(scrim, (0, 0))

    draw = ImageDraw.Draw(overlay)
    max_text_width = zone_width - 2 * padding
    y = padding * 2

    if eyebrow:
        eyebrow_font = _brand_font(brand_profile, 'semibold', max(14, width // 45))
        eyebrow_text = eyebrow.upper()
        draw.text((padding, y), eyebrow_text, font=eyebrow_font, fill=_rgb(accent_color))
        bbox = draw.textbbox((padding, y), eyebrow_text, font=eyebrow_font)
        y = bbox[3] + padding // 2
        divider_end = min(padding + max(60, zone_width // 4), width - padding)
        draw.line([(padding, y), (divider_end, y)], fill=_rgb(accent_color), width=2)
        y += padding

    if headline:
        headline_font = _headline_font('bold', max(30, width // 12))
        lines = _wrapped_lines(draw, headline, headline_font, max_text_width, max_lines=4)
        line_height = int(headline_font.size * 1.22)
        for line in lines:
            draw.text((padding, y), line, font=headline_font, fill=_rgb(ink_color))
            y += line_height
        y += padding // 2

    if description:
        desc_font = _brand_font(brand_profile, 'semibold', max(16, width // 42))
        lines = _wrapped_lines(draw, description, desc_font, max_text_width, max_lines=4)
        line_height = int(desc_font.size * 1.45)
        for line in lines:
            draw.text((padding, y), line, font=desc_font, fill=_rgb(ink_color))
            y += line_height
        y += padding // 2

    if cta:
        cta_font = _brand_font(brand_profile, 'semibold', max(16, width // 40))
        cta_text = cta.upper()
        draw.text((padding, y), cta_text, font=cta_font, fill=_rgb(accent_color))
        bbox = draw.textbbox((padding, y), cta_text, font=cta_font)
        underline_y = bbox[3] + 4
        draw.line([(padding, underline_y), (bbox[2], underline_y)], fill=_rgb(accent_color), width=2)


def _place_logo_top_right(overlay, mark_bytes, width, padding, accent_color):
    """Pastes the real brand logo into the TOP-RIGHT corner, on a small opaque patch so
    it stays legible over the hero photo regardless of what's behind it - and, same as
    before, so nothing the image model may have drawn in that corner survives underneath
    it. Only drawn when a real logo/symbol was actually provided (corrupt bytes still
    paint the patch alone, as a safe fallback, but nothing is invented from nothing).
    """
    try:
        mark = Image.open(io.BytesIO(mark_bytes)).convert('RGBA')
    except Exception:  # noqa: BLE001 - a corrupt/unsupported image file should never fail generation
        mark = None

    if mark is not None:
        mark_w = max(1, int(width * LOGO_WIDTH_FRACTION))
        mark_h = max(1, int(mark.height * (mark_w / mark.width)))
        mark = mark.resize((mark_w, mark_h))
        chip_w, chip_h = mark_w + padding, mark_h + padding
    else:
        chip_w = chip_h = int(width * (LOGO_WIDTH_FRACTION + 0.06))

    margin = padding // 2
    chip_x = overlay.width - margin - chip_w
    chip_box = [chip_x, margin, chip_x + chip_w, margin + chip_h]

    draw = ImageDraw.Draw(overlay)
    # Fully opaque white patch with a thin accent rule underneath - a clean logo plate,
    # not a colored block, matching the "premium editorial" look rather than a badge.
    draw.rounded_rectangle(chip_box, radius=min(14, chip_h // 4), fill=(*_rgb(WHITE), 255))
    draw.line(
        [(chip_x, margin + chip_h), (chip_x + chip_w, margin + chip_h)], fill=_rgb(accent_color), width=2,
    )

    if mark is not None:
        mark_x = chip_x + (chip_w - mark_w) // 2
        mark_y = margin + (chip_h - mark_h) // 2
        overlay.alpha_composite(mark, (mark_x, mark_y))
