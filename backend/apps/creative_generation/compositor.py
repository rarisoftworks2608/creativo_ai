"""Overlays brand elements onto an AI-generated creative (Epic 06: AI Creative Generation).

Diffusion image models are unreliable at rendering legible text - even top-tier ones
regularly misspell headlines/CTAs baked into the picture. This module sidesteps that
entirely: the image model is instructed to produce a clean visual only (see
prompts.build_image_prompt), and the headline/CTA text - already generated accurately as
plain data by the text AI (Epic 05/06) - is drawn on top here with Pillow. Since the text
is never re-interpreted by an image model, spelling is always exactly what was generated.

Brand assets (logo, symbol mark, brand colors, brand font) are applied the same way
whenever they're set on the company's BrandProfile (Epic 03), regardless of whether the
brief happened to mention them - a logo and on-brand CTA button are part of what makes
this look like a real ad, not an optional extra.
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

DEFAULT_BANNER_COLOR = '#1A1A1A'
DEFAULT_ACCENT_COLOR = '#D4A017'
WHITE = '#FFFFFF'


def compose_creative(
    image_bytes, mime_type, *, headline='', cta='', logo_bytes=None, symbol_bytes=None, brand_profile=None,
):
    """Overlays a brand-colored headline banner, a CTA button, the brand logo, and a
    secondary symbol/icon mark (each only if the corresponding input is provided) onto
    image_bytes. Returns (composited_bytes, 'image/jpeg'). Returns the input unchanged if
    there's nothing to overlay.
    """
    if not headline and not cta and not logo_bytes and not symbol_bytes:
        return image_bytes, mime_type

    headline = _sanitize_text(headline)
    cta = _sanitize_text(cta)

    base = Image.open(io.BytesIO(image_bytes)).convert('RGBA')
    width, height = base.size
    overlay = Image.new('RGBA', base.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    banner_color, accent_color = _brand_colors(brand_profile)
    padding = max(20, width // 24)

    if headline:
        _draw_headline_banner(overlay, headline, width, height, padding, banner_color, bool(cta), brand_profile)

    if cta:
        _draw_cta_button(draw, cta, width, height, padding, accent_color, brand_profile)

    # Only paint a corner patch when there's a real logo/symbol to place on it - nothing
    # gets added to the image that wasn't actually provided. (Suppressing the AI's own
    # occasional fake corner logo attempt is handled at the source instead - see
    # HuggingFaceImageProvider.NEGATIVE_PROMPT and the image prompt's explicit
    # no-logo/no-branding instruction - rather than by covering it up here.)
    if logo_bytes:
        _place_corner_mark(overlay, logo_bytes, width, padding, banner_color, corner='top-left')
    if symbol_bytes:
        _place_corner_mark(overlay, symbol_bytes, width, padding, accent_color, corner='top-right', max_width_fraction=1 / 10)

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
    ' ': ' ',                      # non-breaking space
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
    back to Poppins if unset or unrecognized.
    """
    fonts = list(getattr(brand_profile, 'fonts', None) or [])
    family_name = (fonts[0].get('name') or '').strip().lower() if fonts else ''
    spec = BRAND_FONT_LIBRARY.get(family_name) or BRAND_FONT_LIBRARY[DEFAULT_FONT_FAMILY]

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


def _vertical_gradient(size, color, *, top_alpha, bottom_alpha):
    """A solid-color RGBA image whose alpha fades linearly from top_alpha to bottom_alpha -
    used as a soft scrim instead of a flat block, so the photo stays visible through it
    rather than getting covered by a hard-edged color panel.
    """
    width, height = size
    column = Image.new('L', (1, height))
    for y in range(height):
        t = y / max(height - 1, 1)
        column.putpixel((0, y), int(top_alpha + (bottom_alpha - top_alpha) * t))
    alpha_mask = column.resize((width, height))
    solid = Image.new('RGBA', (width, height), (*_rgb(color), 255))
    solid.putalpha(alpha_mask)
    return solid


def _draw_headline_banner(overlay, headline, width, height, padding, banner_color, reserve_for_cta, brand_profile):
    font_size = max(24, width // 16)
    font = _brand_font(brand_profile, 'bold', font_size)
    max_text_width = width - 2 * padding
    draw = ImageDraw.Draw(overlay)
    lines = _wrapped_lines(draw, headline.upper(), font, max_text_width, max_lines=2)
    line_height = int(font_size * 1.3)

    banner_height = padding * 2 + line_height * len(lines)
    if reserve_for_cta:
        banner_height += int(font_size * 1.8)

    # The scrim fades in above the text zone rather than starting abruptly at its edge, so
    # this is taller than the text actually needs - a soft gradient, not a hard-edged
    # block, keeps the photo the dominant element instead of covering a chunk of it.
    scrim_height = min(height, int(banner_height * 1.7))
    scrim = _vertical_gradient((width, scrim_height), banner_color, top_alpha=0, bottom_alpha=235)
    overlay.alpha_composite(scrim, (0, height - scrim_height))

    # A soft drop shadow keeps the text legible over whatever photo detail still shows
    # through the gradient, without needing a fully opaque background behind it.
    shadow_offset = max(2, font_size // 16)
    y = height - banner_height + padding
    for line in lines:
        draw.text((padding + shadow_offset, y + shadow_offset), line, font=font, fill=(0, 0, 0, 150))
        draw.text((padding, y), line, font=font, fill=_rgb(WHITE))
        y += line_height


def _draw_cta_button(draw, cta, width, height, padding, accent_color, brand_profile):
    font_size = max(18, width // 26)
    font = _brand_font(brand_profile, 'semibold', font_size)
    text_width = draw.textlength(cta, font=font)
    button_padding_x, button_padding_y = 22, 12
    button_w = text_width + button_padding_x * 2
    button_h = font_size + button_padding_y * 2

    # If there's a headline banner, its height already reserves room for this button at
    # its bottom edge (see reserve_for_cta in _draw_headline_banner); with no banner, the
    # button just floats on the raw image with the same padding from the bottom edge.
    button_x = padding
    button_y = height - padding - button_h

    draw.rounded_rectangle(
        [button_x, button_y, button_x + button_w, button_y + button_h],
        radius=button_h // 2, fill=_rgb(accent_color),
    )
    draw.text((button_x + button_padding_x, button_y + button_padding_y - 1), cta, font=font, fill=_rgb(WHITE))


def _place_corner_mark(overlay, mark_bytes, width, padding, patch_color, *, corner, max_width_fraction=1 / 6):
    """Paints a solid, rounded color patch into one top corner, then pastes the real mark
    image (logo or symbol) centered on it if one was provided. The patch is always drawn,
    sized generously around the mark's actual dimensions (or a smaller flat accent chip if
    there's no mark) - diffusion models frequently hallucinate their own fake corner
    logo/watermark even with negative_prompt guidance discouraging it, so covering the
    corner with a real design element is the only way to guarantee nothing the model drew
    there survives, the same way the banner elsewhere unconditionally covers the bottom.
    """
    mark = None
    if mark_bytes:
        try:
            mark = Image.open(io.BytesIO(mark_bytes)).convert('RGBA')
        except Exception:  # noqa: BLE001 - a corrupt/unsupported image file should never fail generation
            mark = None

    if mark is not None:
        mark_w = max(1, int(width * max_width_fraction))
        mark_h = max(1, int(mark.height * (mark_w / mark.width)))
        mark = mark.resize((mark_w, mark_h))
        chip_w, chip_h = mark_w + padding, mark_h + padding
    else:
        # No real mark to size against - the AI-hallucinated logos this guards against
        # regularly run ~20-25% of the image width, notably bigger than a typical small
        # logo, so this has to be sized generously rather than as a subtle accent chip.
        chip_w = chip_h = int(width * 0.24)

    margin = padding // 2
    if corner == 'top-left':
        chip_x = margin
    else:
        chip_x = overlay.width - margin - chip_w
    chip_box = [chip_x, margin, chip_x + chip_w, margin + chip_h]

    draw = ImageDraw.Draw(overlay)
    # Fully opaque - this exists specifically to guarantee nothing drawn underneath (an
    # AI-hallucinated logo attempt) is even partially visible, so no blending allowed.
    draw.rounded_rectangle(chip_box, radius=min(16, chip_h // 4), fill=(*_rgb(patch_color), 255))

    if mark is not None:
        mark_x = chip_x + (chip_w - mark_w) // 2
        mark_y = margin + (chip_h - mark_h) // 2
        overlay.alpha_composite(mark, (mark_x, mark_y))
