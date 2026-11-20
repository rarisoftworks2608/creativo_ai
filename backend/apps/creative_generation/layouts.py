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

AUTO = 'auto'

PORTRAIT_4_5 = 1.25          # Instagram 1080 x 1350
STORY_9_16 = 16 / 9          # 1080 x 1920


def layout_for(creative_type):
    """{'placement': 'auto', 'aspect': height / width} for a creative type."""
    return {
        'placement': AUTO,
        'aspect': STORY_9_16 if creative_type == 'story' else PORTRAIT_4_5,
    }
