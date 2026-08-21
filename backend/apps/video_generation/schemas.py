"""JSON schema for the script/scene breakdown (Epic 07: Video Components - Script, Scenes)."""

SCRIPT_SCHEMA = {
    'type': 'object',
    'properties': {
        'scenes': {
            'type': 'array',
            'minItems': 3,
            'maxItems': 8,
            'items': {
                'type': 'object',
                'properties': {
                    'narration': {'type': 'string', 'description': 'The voice-over line for this scene.'},
                    'visual_description': {'type': 'string', 'description': 'What should be shown on screen.'},
                    'duration_seconds': {
                        'type': 'number',
                        'description': 'How long this scene should be shown, in seconds.',
                    },
                },
                'required': ['narration', 'visual_description', 'duration_seconds'],
                'additionalProperties': False,
            },
        },
    },
    'required': ['scenes'],
    'additionalProperties': False,
}
