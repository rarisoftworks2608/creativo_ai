"""Overlays brand elements onto an AI-generated creative (Epic 06: AI Creative Generation).

Diffusion image models are unreliable at rendering legible text - even top-tier ones
regularly misspell headlines/CTAs baked into the picture. This module sidesteps that
entirely: the image model is instructed to produce a clean visual only (see
prompts.build_image_prompt), and the headline/CTA text - already generated accurately as
plain data by the text AI (Epic 05/06) - is drawn on top here with Pillow. Since the text
is never re-interpreted by an image model, spelling is always exactly what was generated.

Brand assets (logo, brand colors) are applied the same way whenever they're set on the
company's BrandProfile (Epic 03), regardless of whether the brief happened to mention
them - a logo and on-brand CTA button are part of what makes this look like a real ad,
not an optional extra.
"""

import io
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

FONT_DIR = Path(__file__).resolve().parent / 'fonts'
BOLD_FONT_PATH = FONT_DIR / 'Poppins-Bold.ttf'
SEMIBOLD_FONT_PATH = FONT_DIR / 'Poppins-SemiBold.ttf'

DEFAULT_BANNER_COLOR = '#1A1A1A'
DEFAULT_ACCENT_COLOR = '#D4A017'
WHITE = '#FFFFFF'


def compose_creative(image_bytes, mime_type, *, headline='', cta='', logo_bytes=None, brand_profile=None):
    """Overlays a brand-colored headline banner, a CTA button, and the brand logo (each
    only if the corresponding input is provided) onto image_bytes. Returns
    (composited_bytes, 'image/jpeg'). Returns the input unchanged if there's nothing to
    overlay.
    """
    if not headline and not cta and not logo_bytes:
        return image_bytes, mime_type

    base = Image.open(io.BytesIO(image_bytes)).convert('RGBA')
    width, height = base.size
    overlay = Image.new('RGBA', base.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    banner_color, accent_color = _brand_colors(brand_profile)
    padding = max(20, width // 24)

    if headline:
        _draw_headline_banner(draw, headline, width, height, padding, banner_color, bool(cta))

    if cta:
        _draw_cta_button(draw, cta, width, height, padding, accent_color)

    if logo_bytes:
        _paste_logo(overlay, logo_bytes, width, padding)

    composed = Image.alpha_composite(base, overlay).convert('RGB')
    output = io.BytesIO()
    composed.save(output, format='JPEG', quality=92)
    return output.getvalue(), 'image/jpeg'


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


def _draw_headline_banner(draw, headline, width, height, padding, banner_color, reserve_for_cta):
    font_size = max(24, width // 16)
    font = ImageFont.truetype(str(BOLD_FONT_PATH), font_size)
    max_text_width = width - 2 * padding
    lines = _wrapped_lines(draw, headline.upper(), font, max_text_width, max_lines=2)
    line_height = int(font_size * 1.3)

    banner_height = padding * 2 + line_height * len(lines)
    if reserve_for_cta:
        banner_height += int(font_size * 1.8)

    draw.rectangle([0, height - banner_height, width, height], fill=(*_rgb(banner_color), 235))

    y = height - banner_height + padding
    for line in lines:
        draw.text((padding, y), line, font=font, fill=_rgb(WHITE))
        y += line_height


def _draw_cta_button(draw, cta, width, height, padding, accent_color):
    font_size = max(18, width // 26)
    font = ImageFont.truetype(str(SEMIBOLD_FONT_PATH), font_size)
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


def _paste_logo(overlay, logo_bytes, width, padding):
    try:
        logo = Image.open(io.BytesIO(logo_bytes)).convert('RGBA')
    except Exception:  # noqa: BLE001 - a corrupt/unsupported logo file should never fail generation
        return
    logo_w = width // 6
    logo_h = max(1, int(logo.height * (logo_w / logo.width)))
    logo = logo.resize((logo_w, logo_h))
    overlay.alpha_composite(logo, (padding, padding))
