"""What every creative type shares: the picture size, and that the composition is art-directed per picture.

The ONLY fixed thing is the brand logo: the original file, top-right, on every creative of every type.
Everything else follows the picture. Each variation's picture is asked to leave calm space at the bottom,
left, right or top (art_direction.COMPOSITIONS), and the compositor measures where the picture is really
calm and places the text stack (left, right, a narrow column or, only when nothing else fits, centred) there,
in a typography preset that suits the creative type and the brand - see art_direction.py. The picture
itself is always a full scene made from the calendar entry and the brand guidelines (prompts.py).

`placement` is 'auto' for every type. The compositor still understands 'below' (centred along the
bottom) and 'top' (left-aligned at the top-left) for anyone who wants to pin the text.
"""

from .creative_types import aspect_value, resolve_aspect_ratio

AUTO = 'auto'

PORTRAIT_4_5 = 1.25          # Instagram 1080 x 1350
STORY_9_16 = 16 / 9          # 1080 x 1920

# A story's top and bottom are covered by the app's own interface (progress bar and profile at the top, the reply
# bar at the bottom): the text and the logo stay out of these bands (shares of the height).
STORY_SAFE_TOP = 0.13
STORY_SAFE_BOTTOM = 0.18


def layout_for(creative_type, aspect_ratio=''):
    """{'placement': 'auto', 'aspect': height / width, 'ratio': '4:5', 'safe_top': share, 'safe_bottom': share} for a
    creative type at the requested aspect ratio (the type's default when that ratio is not allowed for it)."""
    ratio = resolve_aspect_ratio(creative_type, aspect_ratio)
    is_story = creative_type == 'story'
    return {
        'placement': AUTO,
        'aspect': aspect_value(ratio),
        'ratio': ratio,
        'safe_top': STORY_SAFE_TOP if is_story else 0.0,
        'safe_bottom': STORY_SAFE_BOTTOM if is_story else 0.0,
    }
