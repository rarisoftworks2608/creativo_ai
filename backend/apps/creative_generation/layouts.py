"""The brand alignment template shared by every creative: where the logo and the text go.

Whatever the creative type, the brand logo sits large in the TOP-RIGHT corner at the same margin
and size. The only thing that differs between types is where the text stack is placed:

    below - the text stack is centred along the bottom (subject in the upper-middle)
    top   - the text stack is left-aligned at the top-left, beside the logo (subject in the lower-middle)

The picture itself is always a full scene made from the calendar entry and the brand guidelines
(see prompts.py); this template only decides which part of it is kept calm for the text and logo.

Change PLACEMENT_BY_TYPE to move a type; everything else (the image prompt that keeps the right
area calm, the compositor that draws the text and logo) follows from the result.
"""

BELOW = 'below'
TOP = 'top'

PLACEMENT_BY_TYPE = {
    'promotional_creative': TOP,
    'event_creative': TOP,
    'announcement_creative': TOP,
    'educational_creative': TOP,
    'testimonial_creative': TOP,
}  # every other type: BELOW

PORTRAIT_4_5 = 1.25          # Instagram 1080 x 1350
STORY_9_16 = 16 / 9          # 1080 x 1920


def layout_for(creative_type):
    """{'placement': 'below' | 'top', 'aspect': height / width} for a creative type."""
    return {
        'placement': PLACEMENT_BY_TYPE.get(creative_type, BELOW),
        'aspect': STORY_9_16 if creative_type == 'story' else PORTRAIT_4_5,
    }
