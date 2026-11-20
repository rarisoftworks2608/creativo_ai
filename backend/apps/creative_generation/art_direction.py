"""Art direction for a creative: where the text and the logo go on THIS picture, and how they look.

The image AI draws the scene only; the logo and the exact copy are composited afterwards (compositor.py).
This module decides the composition so that it is not the same centred template every time:

* `EnergyMap` measures how much detail (edges) each part of the picture has - a subject, lanterns or
  flowers are busy, a lit wall or a polished floor is calm.
* The image prompt asks for a different composition per variation (`COMPOSITIONS`): calm negative space at
  the bottom, top, left or right of the frame, so the picture itself leaves room for the text.
* `plan_layout` tries a text block in every layout family (left, right, narrow editorial columns on either
  side, and - least preferred - centred) at every height, scores each placement by how calm the picture is
  underneath and by how well it matches the composition asked for, and picks one of the best. The brand logo
  is fixed in the top-right corner and the text never overlaps it. With a seed it varies between near-equal
  choices, so two generations of the same brief do not look alike; without one it picks the single best.
* `choose_style` picks a typographic preset (headline face, case and size, kicker, divider and CTA style)
  from the creative type and the brand's tone, again varied by seed. Every preset uses only the brand's own
  fonts, colours and the bundled type set, so the creatives vary but stay on-brand.

Pure logic: no fonts and no drawing, so it is cheap to test.
"""

import random
from dataclasses import dataclass

from PIL import Image, ImageFilter


@dataclass(frozen=True)
class Family:
    """A text-block layout family: how its lines are aligned and how wide the block may be (share of width)."""
    name: str
    align: str      # 'center' | 'left' | 'right'
    width: float
    bias: float     # a small cost, so the plain centred block wins a tie but the others stay in the running


FAMILIES = (
    Family('center', 'center', 0.84, 1.2),        # a centred stack is the template look: only when clearly best
    Family('left', 'left', 0.52, 0.0),
    Family('right', 'right', 0.52, 0.0),
    Family('left_wide', 'left', 0.8, 0.1),         # a wide flush-left stack: a two-line headline, as in a web hero
    Family('right_wide', 'right', 0.8, 0.1),
    Family('left_column', 'left', 0.40, 0.3),     # a narrow editorial column
    Family('right_column', 'right', 0.40, 0.3),
)

# The composition each variation's picture is asked to have (see prompts._composition_sentence): which part of
# the frame is left calm for the text. Variations of one request rotate through them, so they differ.
COMPOSITIONS = ('bottom', 'left', 'right', 'top')


def composition_for(request_id, variation_number):
    """The composition for one variation of one request: the variations of a request always differ, and
    consecutive requests start on different ones."""
    return COMPOSITIONS[(request_id + variation_number) % len(COMPOSITIONS)]

# The brand logo is fixed in the top-right corner of every creative. Other corners can be allowed to
# plan_layout (they are scored by LOGO_CORNER_BIAS), but nothing does so today.
LOGO_CORNER_BIAS = {'top_right': 0.0, 'top_left': 0.5, 'bottom_right': 4.0, 'bottom_left': 4.0}
FIXED_LOGO_CORNERS = ('top_right',)


# --------------------------------------------------------------------------- how busy each part of the picture is

class EnergyMap:
    """Mean edge detail of any rectangle of the picture, from a summed-area table of a small copy of it."""

    WORKING_WIDTH = 160

    def __init__(self, image):
        width, height = image.size
        self.scale = self.WORKING_WIDTH / width
        small = image.convert('L').resize((self.WORKING_WIDTH, max(1, round(height * self.scale))))
        # The edge filter copies the picture's 1-pixel border through unchanged, which would read as detail
        # along every edge of the picture: only the interior counts.
        edges = Image.new('L', small.size, 0)
        edges.paste(small.filter(ImageFilter.FIND_EDGES).crop((1, 1, small.width - 1, small.height - 1)), (1, 1))
        self.width, self.height = edges.size
        data = list(edges.getdata())
        self.table = [[0] * (self.width + 1) for _ in range(self.height + 1)]
        for y in range(self.height):
            running = 0
            for x in range(self.width):
                running += data[y * self.width + x]
                self.table[y + 1][x + 1] = self.table[y][x + 1] + running

    def mean(self, rect):
        """Mean detail inside rect = (x0, y0, x1, y1) in picture pixels."""
        x0, y0, x1, y1 = rect
        c0 = min(self.width - 1, max(0, int(x0 * self.scale)))
        r0 = min(self.height - 1, max(0, int(y0 * self.scale)))
        c1 = min(self.width, max(c0 + 1, int(x1 * self.scale + 0.999)))
        r1 = min(self.height, max(r0 + 1, int(y1 * self.scale + 0.999)))
        total = self.table[r1][c1] - self.table[r0][c1] - self.table[r1][c0] + self.table[r0][c0]
        return total / ((r1 - r0) * (c1 - c0))


# --------------------------------------------------------------------------- the layout

@dataclass(frozen=True)
class Plan:
    family: Family | None
    text_rect: tuple | None
    logo_corner: str | None
    logo_rect: tuple | None
    score: float


def _intersects(a, b):
    return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]


def _inflated(rect, amount):
    return (rect[0] - amount, rect[1] - amount, rect[2] + amount, rect[3] + amount)


def logo_corners(size, logo_size):
    """{corner: rect} for a logo of `logo_size` at the standard margin in each corner."""
    width, height = size
    logo_w, logo_h = logo_size
    pad = int(width * 0.06)
    return {
        'top_right': (width - pad - logo_w, pad, width - pad, pad + logo_h),
        'top_left': (pad, pad, pad + logo_w, pad + logo_h),
        'bottom_right': (width - pad - logo_w, height - pad - logo_h, width - pad, height - pad),
        'bottom_left': (pad, height - pad - logo_h, pad + logo_w, height - pad),
    }


def _in_zone(zone, rect, size):
    """Whether rect lies in the part of the frame the composition `zone` ('bottom', 'top', 'left', 'right') left calm."""
    centre_x, centre_y = (rect[0] + rect[2]) / 2 / size[0], (rect[1] + rect[3]) / 2 / size[1]
    return {'bottom': centre_y > 0.58, 'top': centre_y < 0.42, 'left': centre_x < 0.46, 'right': centre_x > 0.54}.get(zone, False)


def plan_layout(
    energy, size, *, measure=None, logo_size=None, rng=None, corners_allowed=FIXED_LOGO_CORNERS, prefer=None,
    margin_top=None, margin_bottom=None,
):
    """The text block's family and position and the logo's corner for this picture.

    `measure(family)` returns (content_width, block_height) of the text stack set for that family, or is None
    when there is no text. `logo_size` is (w, h) or None. `prefer` is the composition the picture was asked to
    have ('bottom', 'top', 'left' or 'right' calm space): text in that zone is favoured, so the layout matches
    the picture - but the measured calm of the picture still decides, so a picture that ignored the request is
    laid out by what it actually looks like. With `rng` (a random.Random) the choice is made among the best few
    distinct combinations; without it, it is the single best. `margin_top` / `margin_bottom` (pixels) keep the text
    clear of a header row or a footer that is drawn there."""
    width, height = size
    margin_x = int(width * 0.07)
    margin_top = int(width * 0.06) if margin_top is None else margin_top
    margin_bottom = int(width * 0.09) if margin_bottom is None else margin_bottom
    gap = int(width * 0.03)
    corners = (
        {name: rect for name, rect in logo_corners(size, logo_size).items() if name in corners_allowed}
        if logo_size else {}
    )

    def best_corner(avoid=None):
        options = [
            (0.7 * energy.mean(rect) + LOGO_CORNER_BIAS[name], name, rect)
            for name, rect in corners.items() if avoid is None or not _intersects(avoid, rect)
        ]
        return min(options) if options else None

    candidates = []
    if measure is None:
        found = best_corner()
        if found:
            candidates = [Plan(None, None, found[1], found[2], found[0])]
            candidates += [
                Plan(None, None, name, rect, 0.7 * energy.mean(rect) + LOGO_CORNER_BIAS[name])
                for name, rect in corners.items() if name != found[1]
            ]
    else:
        for family in FAMILIES:
            content_w, block_h = measure(family)
            content_w = min(content_w, width - 2 * margin_x)
            x0 = {
                'left': margin_x, 'right': width - margin_x - content_w, 'center': (width - content_w) // 2,
            }[family.align]
            low, high = margin_top, height - margin_bottom - block_h
            if high < low:
                continue
            steps = 14
            for step in range(steps + 1):
                y = low + (high - low) * step // steps
                rect = (x0, y, x0 + content_w, y + block_h)
                higher = (high - y) / max(high - low, 1)  # 0 at the lowest position, 1 at the highest
                pull = (1 - higher) if prefer == 'top' else higher  # a small pull towards the preferred edge
                # Overlapping anything busy costs far more than the small preferences between layouts.
                score = 3 * energy.mean(_inflated(rect, gap // 2)) * (1 + 0.25 * pull) + 0.5 * pull + family.bias
                if prefer and _in_zone(prefer, rect, size):
                    score -= 1.5
                if corners:
                    found = best_corner(avoid=_inflated(rect, gap))
                    if found is None:
                        continue
                    candidates.append(Plan(family, rect, found[1], found[2], score + found[0]))
                else:
                    candidates.append(Plan(family, rect, None, None, score))

    if not candidates:  # nothing fits (a huge text block): the bottom centre, logo top-right
        rect = None
        if measure is not None:
            content_w, block_h = measure(FAMILIES[0])
            rect = ((width - content_w) // 2, max(margin_top, height - margin_bottom - block_h), (width + content_w) // 2, height - margin_bottom)
        return Plan(FAMILIES[0] if rect else None, rect, 'top_right' if corners else None, corners.get('top_right'), 0.0)

    candidates.sort(key=lambda plan: plan.score)
    if rng is None:
        return candidates[0]
    limit = candidates[0].score * 1.3 + 1.0
    distinct, seen = [], set()
    for plan in candidates:
        key = (plan.family.name if plan.family else None, plan.logo_corner)
        if plan.score <= limit and key not in seen:
            seen.add(key)
            distinct.append(plan)
    return rng.choice(distinct[:4])


# --------------------------------------------------------------------------- the typography

# headline: 'serif' (the bundled editorial serif) or 'brand' (the brand's own font); weight ('regular' is the
# refined light cut); case; size as a share of width; italic_tail sets the headline's last word in italic.
# kicker: 'tracked' (small, widely spaced, soft), 'rules' (thin rules either side), 'bar' (a short bar), 'plain'.
# divider: 'diamond', 'line', 'dot', 'none'. cta: 'underline' (a quiet text link with an arrow), 'outline',
# 'pill', 'square'. body_size: body copy as a share of width.
# Luxury first: light serif cuts, soft type, hairlines and quiet calls to action; the one heavy preset
# ('bold_sans') is only offered for promotions.
STYLE_PRESETS = {
    # The premium editorial web-hero look: a tracked kicker, a large light serif headline whose last word is
    # italic, soft body copy and an underlined link.
    'web_editorial': {
        'headline': 'serif', 'weight': 'regular', 'case': 'title', 'size': 0.094, 'italic_tail': True,
        'headline_color': 'ink', 'kicker': 'tracked', 'divider': 'none', 'cta': 'underline', 'body_size': 0.027,
    },
    'editorial_serif': {
        'headline': 'serif', 'weight': 'regular', 'case': 'title', 'size': 0.088, 'italic_tail': True,
        'headline_color': 'ink', 'kicker': 'rules', 'divider': 'diamond', 'cta': 'pill', 'body_size': 0.028,
    },
    'quiet_luxury': {
        'headline': 'serif', 'weight': 'regular', 'case': 'title', 'size': 0.096, 'italic_tail': False,
        'headline_color': 'ink', 'kicker': 'tracked', 'divider': 'line', 'cta': 'underline', 'body_size': 0.027,
    },
    'gold_serif': {
        'headline': 'serif', 'weight': 'semibold', 'case': 'title', 'size': 0.09, 'italic_tail': True,
        'headline_color': 'accent', 'kicker': 'plain', 'divider': 'line', 'cta': 'outline', 'body_size': 0.028,
    },
    'serif_caps': {
        'headline': 'serif', 'weight': 'regular', 'case': 'upper', 'size': 0.06, 'italic_tail': False,
        'headline_color': 'ink', 'kicker': 'bar', 'divider': 'dot', 'cta': 'outline', 'body_size': 0.027,
    },
    'modern_caps': {
        'headline': 'brand', 'weight': 'regular', 'case': 'upper', 'size': 0.05, 'italic_tail': False,
        'headline_color': 'ink', 'kicker': 'tracked', 'divider': 'line', 'cta': 'underline', 'body_size': 0.027,
    },
    'bold_sans': {
        'headline': 'brand', 'weight': 'bold', 'case': 'title', 'size': 0.078, 'italic_tail': False,
        'headline_color': 'ink', 'kicker': 'bar', 'divider': 'none', 'cta': 'square', 'body_size': 0.03,
    },
    # The two "designed poster" looks, for business creatives: a header row (the kicker opposite the logo), a large
    # light headline whose closing word of each sentence is in the accent colour (tech_luxe) or italic (luxe_frame),
    # a small widely spaced sub-line with a short rule under it, and - drawn by compositor._paint_frame - a strip of
    # the company's services and a footer with its name, sign-off and website. No CTA button: the website is the call.
    'tech_luxe': {
        'headline': 'brand', 'weight': 'regular', 'case': 'title', 'size': 0.072, 'italic_tail': False,
        'accent_words': True, 'headline_color': 'ink', 'kicker': 'tracked', 'divider': 'line', 'cta': 'underline',
        'body': 'caps', 'body_size': 0.019, 'frame': True,
    },
    'luxe_frame': {
        'headline': 'serif', 'weight': 'regular', 'case': 'title', 'size': 0.086, 'italic_tail': True,
        'headline_color': 'ink', 'kicker': 'tracked', 'divider': 'line', 'cta': 'underline',
        'body': 'caps', 'body_size': 0.019, 'frame': True,
    },
}
FRAMED_PRESETS = ('tech_luxe', 'luxe_frame')
# Greetings and testimonials are not adverts for the company's services: no services strip or footer.
UNFRAMED_TYPES = ('festival_creative', 'testimonial_creative')

# Used for any creative type without a pool of its own: every preset but the heavy one.
DEFAULT_POOL = ('web_editorial', 'editorial_serif', 'quiet_luxury', 'gold_serif', 'serif_caps', 'modern_caps')
STYLE_POOLS = {
    'festival_creative': ('web_editorial', 'editorial_serif', 'quiet_luxury', 'gold_serif'),
    'testimonial_creative': ('editorial_serif', 'quiet_luxury', 'web_editorial'),
    'promotional_creative': ('gold_serif', 'modern_caps', 'web_editorial', 'bold_sans'),
    'product_creative': ('quiet_luxury', 'web_editorial', 'gold_serif'),
    'announcement_creative': ('web_editorial', 'modern_caps', 'serif_caps'),
    'event_creative': ('web_editorial', 'serif_caps', 'modern_caps'),
    'educational_creative': ('modern_caps', 'web_editorial', 'quiet_luxury'),
}
SERIF_PRESETS = ('web_editorial', 'editorial_serif', 'quiet_luxury', 'gold_serif', 'serif_caps', 'luxe_frame')
SANS_PRESETS = ('modern_caps', 'bold_sans', 'tech_luxe')
SERIF_TONES = ('luxur', 'premium', 'elegan', 'classic', 'heritage', 'refined', 'sophisticated', 'timeless', 'tradition')
SANS_TONES = (
    'bold', 'modern', 'playful', 'young', 'tech', 'energetic', 'vibrant', 'minimal', 'clean', 'fun', 'innovat',
    'digital', 'software', 'data',
)


def _tone_leaning(brand_profile):
    """'serif', 'sans' or None: which kind of typography the brand's tone and visual style point to."""
    tone = ' '.join(
        str(getattr(brand_profile, field, '') or '') for field in ('tone', 'visual_style', 'brand_voice')
    ).lower()
    serif, sans = any(word in tone for word in SERIF_TONES), any(word in tone for word in SANS_TONES)
    if serif == sans:
        return None
    return 'serif' if serif else 'sans'


def style_pool(creative_type, brand_profile, framed=False):
    """The presets that suit this creative type and the brand's own tone and visual style: a luxurious brand
    leans to the serif presets, a bold modern one to the sans ones. Always at least one. `framed` (the creative
    has a services strip / footer to draw) offers the two poster presets instead."""
    leaning = _tone_leaning(brand_profile)
    if framed and creative_type not in UNFRAMED_TYPES:
        return [{'serif': 'luxe_frame', 'sans': 'tech_luxe'}[leaning]] if leaning else list(FRAMED_PRESETS)
    pool = list(STYLE_POOLS.get(creative_type) or DEFAULT_POOL)
    if leaning:
        favoured = SERIF_PRESETS if leaning == 'serif' else SANS_PRESETS
        narrowed = [name for name in pool if name in favoured]
        pool = narrowed or [name for name in DEFAULT_POOL if name in favoured] or list(favoured)
    return pool


def choose_style(rng, creative_type, brand_profile, framed=False):
    """(name, preset) - the first of the pool without a seed, a seeded pick from it with one."""
    pool = style_pool(creative_type, brand_profile, framed)
    name = rng.choice(pool) if rng is not None else pool[0]
    return name, STYLE_PRESETS[name]


def seeded(seed):
    """A random.Random for a seed, or None when there is no seed (no variation)."""
    return random.Random(seed) if seed is not None else None
