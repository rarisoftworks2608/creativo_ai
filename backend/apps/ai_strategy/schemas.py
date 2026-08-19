"""JSON schemas and generation instructions for each AI Planning / AI Strategy kind (Epic 05).

Keeping these as data (rather than one view per kind) means the view layer
is a single generic "generate for this kind" endpoint - adding a new kind
later is a dict entry, not a new class.
"""

from .models import StrategyOutput

BRAND_CONTEXT_SCHEMA = {
    'type': 'object',
    'properties': {
        'business_analysis': {'type': 'string', 'description': 'Analysis of the business itself: what it does, its market position.'},
        'brand_guidelines_analysis': {'type': 'string', 'description': 'Analysis of the brand voice, tone, visual style and guardrails.'},
        'products_services_analysis': {'type': 'string', 'description': 'Analysis of the products/services and what makes them marketable.'},
        'audience_analysis': {'type': 'string', 'description': 'Analysis of the target audience and customer personas.'},
        'summary': {
            'type': 'string',
            'description': 'A synthesized brand context paragraph grounding future content generation - '
                            'combines the above into one coherent picture of who this brand is and who it speaks to.',
        },
    },
    'required': [
        'business_analysis', 'brand_guidelines_analysis', 'products_services_analysis', 'audience_analysis', 'summary',
    ],
    'additionalProperties': False,
}


def _items_schema(item_properties, required):
    return {
        'type': 'object',
        'properties': {'items': {'type': 'array', 'items': {
            'type': 'object', 'properties': item_properties, 'required': required, 'additionalProperties': False,
        }}},
        'required': ['items'],
        'additionalProperties': False,
    }


STRATEGY_KINDS = {
    # ---------- AI Planning ----------
    StrategyOutput.Kind.CONTENT_IDEAS: {
        'instruction': (
            'Generate a list of concrete content ideas this brand could post about. '
            'Each idea should be specific enough to brief a designer/copywriter directly.'
        ),
        'schema': _items_schema(
            {
                'title': {'type': 'string'},
                'description': {'type': 'string'},
                'content_type': {'type': 'string', 'description': 'e.g. Single image, Carousel, Reel, Story.'},
                'rationale': {'type': 'string', 'description': 'Why this idea fits the brand and audience.'},
            },
            ['title', 'description', 'content_type', 'rationale'],
        ),
    },
    StrategyOutput.Kind.TOPIC_SUGGESTIONS: {
        'instruction': 'Suggest broad topics this brand should regularly talk about, with why each is relevant.',
        'schema': _items_schema(
            {'topic': {'type': 'string'}, 'why_relevant': {'type': 'string'}},
            ['topic', 'why_relevant'],
        ),
    },
    StrategyOutput.Kind.CONTENT_THEMES: {
        'instruction': 'Suggest recurring content themes (e.g. weekly pillars) this brand could organize its calendar around.',
        'schema': _items_schema(
            {'name': {'type': 'string'}, 'description': {'type': 'string'}},
            ['name', 'description'],
        ),
    },
    StrategyOutput.Kind.CAMPAIGN_SUGGESTIONS: {
        'instruction': 'Suggest marketing campaigns this brand could run, each with a clear objective.',
        'schema': _items_schema(
            {'name': {'type': 'string'}, 'objective': {'type': 'string'}, 'description': {'type': 'string'}},
            ['name', 'objective', 'description'],
        ),
    },
    StrategyOutput.Kind.POSTING_SUGGESTIONS: {
        'instruction': 'Suggest a posting cadence per platform: frequency, best times, and any notes.',
        'schema': _items_schema(
            {
                'platform': {'type': 'string'},
                'frequency': {'type': 'string'},
                'best_times': {'type': 'string'},
                'notes': {'type': 'string'},
            },
            ['platform', 'frequency', 'best_times', 'notes'],
        ),
    },
    # ---------- AI Strategy ----------
    StrategyOutput.Kind.CONTENT_STRATEGY: {
        'instruction': 'Produce an overall content strategy: a summary, content pillars, and concrete recommendations.',
        'schema': {
            'type': 'object',
            'properties': {
                'summary': {'type': 'string'},
                'pillars': {'type': 'array', 'items': {
                    'type': 'object',
                    'properties': {'name': {'type': 'string'}, 'description': {'type': 'string'}},
                    'required': ['name', 'description'], 'additionalProperties': False,
                }},
                'recommendations': {'type': 'array', 'items': {'type': 'string'}},
            },
            'required': ['summary', 'pillars', 'recommendations'],
            'additionalProperties': False,
        },
    },
    StrategyOutput.Kind.PLATFORM_STRATEGY: {
        'instruction': 'Produce a per-platform strategy: how this brand should use each relevant social platform.',
        'schema': _items_schema(
            {'platform': {'type': 'string'}, 'strategy': {'type': 'string'}, 'content_mix': {'type': 'string'}},
            ['platform', 'strategy', 'content_mix'],
        ),
    },
    StrategyOutput.Kind.AUDIENCE_STRATEGY: {
        'instruction': 'Produce an audience strategy: a summary plus how to approach each audience segment.',
        'schema': {
            'type': 'object',
            'properties': {
                'summary': {'type': 'string'},
                'segments': {'type': 'array', 'items': {
                    'type': 'object',
                    'properties': {'segment': {'type': 'string'}, 'approach': {'type': 'string'}},
                    'required': ['segment', 'approach'], 'additionalProperties': False,
                }},
            },
            'required': ['summary', 'segments'],
            'additionalProperties': False,
        },
    },
    StrategyOutput.Kind.CAMPAIGN_STRATEGY: {
        'instruction': 'Produce a campaign strategy: a summary plus specific campaigns with goal, approach and timeline.',
        'schema': {
            'type': 'object',
            'properties': {
                'summary': {'type': 'string'},
                'campaigns': {'type': 'array', 'items': {
                    'type': 'object',
                    'properties': {
                        'name': {'type': 'string'}, 'goal': {'type': 'string'},
                        'approach': {'type': 'string'}, 'timeline': {'type': 'string'},
                    },
                    'required': ['name', 'goal', 'approach', 'timeline'], 'additionalProperties': False,
                }},
            },
            'required': ['summary', 'campaigns'],
            'additionalProperties': False,
        },
    },
}
