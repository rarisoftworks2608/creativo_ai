"""One design system for every creative: where the text goes, per creative type.

Every creative - whatever its type - has the same skeleton (see project_plan.md, "Festive
Creative Plan" and the design-system note under it): a plain light background, ONE hero subject,
and the brand logo large in the TOP-RIGHT corner. The only thing that differs between types is
where the text is placed:

    below - the text stack is centred underneath the subject (subject in the upper-middle)
    top   - the text stack is left-aligned at the top-left, beside the logo (subject in the lower-middle)

A brief that describes a scene is followed (the picture shows that scene instead of the plain
background), but the text and the logo stay exactly where they are for the type.

Change PLACEMENT_BY_TYPE to move a type; everything else (the image prompt that keeps the right
area empty, the compositor that draws the text) follows from the result.
"""

from .festive import describes_scene, is_festive_request

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


def layout_for(creative_type, brief=''):
    """{'style': 'festive' | 'standard', 'placement': 'below' | 'top', 'aspect': height / width,
    'background': 'plain' | 'scene'}.

    style / placement / aspect never depend on whether the brief describes a scene - the text and the
    logo are in the same place on every creative. 'background' says what the image AI was asked for: a
    plain background with one subject (no brief, or the template), or the scene the admin described."""
    festive = is_festive_request(creative_type, brief)
    return {
        'style': 'festive' if festive else 'standard',
        'placement': BELOW if festive else PLACEMENT_BY_TYPE.get(creative_type, BELOW),
        'aspect': STORY_9_16 if creative_type == 'story' and not festive else PORTRAIT_4_5,
        'background': 'scene' if describes_scene(brief) else 'plain',
    }
