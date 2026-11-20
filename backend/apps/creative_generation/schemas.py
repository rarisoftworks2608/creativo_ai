"""JSON schema for the copy (caption/headline/description/CTA/hashtags/keywords)
generated alongside each image variation (Epic 06: Variations - Copy)."""

COPY_SCHEMA = {
    'type': 'object',
    'properties': {
        'caption': {'type': 'string', 'description': 'The social media caption/body copy.'},
        'eyebrow': {
            'type': 'string',
            'description': 'A very short (1-4 word) kicker/label shown above the headline in small caps, '
                           'e.g. "THE" or a category/campaign label - premium editorial style.',
        },
        'headline': {'type': 'string', 'description': 'A short headline/hook, if this format uses one.'},
        'description': {'type': 'string', 'description': 'A longer supporting description, if useful.'},
        'cta': {'type': 'string', 'description': 'The call to action, e.g. "Shop now".'},
        'visual_scene': {
            'type': 'string',
            'description': 'The creative brief and calendar entry rewritten as one clear, concrete English description '
                           'of the full scene an image model should draw: subject, setting, props, light and mood.',
        },
        'highlights': {
            'type': 'array', 'items': {'type': 'string'},
            'description': '3-4 short labels (1-3 words) of the company services or strengths for the services strip, '
                           'e.g. "Web Development"; empty for a greeting or testimonial.',
        },
        'tagline': {
            'type': 'string',
            'description': 'A 2-5 word company sign-off for the footer, e.g. "Your Technology Partner"; empty for a '
                           'greeting or testimonial.',
        },
        'hashtags': {'type': 'array', 'items': {'type': 'string'}},
        'keywords': {'type': 'array', 'items': {'type': 'string'}},
    },
    'required': [
        'caption', 'eyebrow', 'headline', 'description', 'cta', 'visual_scene', 'highlights', 'tagline', 'hashtags',
        'keywords',
    ],
    'additionalProperties': False,
}
