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
        'hashtags': {'type': 'array', 'items': {'type': 'string'}},
        'keywords': {'type': 'array', 'items': {'type': 'string'}},
    },
    'required': ['caption', 'eyebrow', 'headline', 'description', 'cta', 'hashtags', 'keywords'],
    'additionalProperties': False,
}
