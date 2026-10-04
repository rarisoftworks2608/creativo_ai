"""Resolves which AI provider/model to use (Epic 19: AI provider settings / Model settings).

Admin Settings can override the provider and model per modality (text, image, video)
without a deploy; a blank override falls back to the .env value (AI_TEXT_PROVIDER,
AI_IMAGE_MODEL, ...). API keys are never stored here - they stay in .env and are read
by each provider class itself.
"""

import os

from django.conf import settings

# Which env vars each provider needs, so Admin Settings can show "key configured: yes/no"
# without ever exposing a secret's value.
PROVIDER_CREDENTIALS = {
    'text': {
        'anthropic': ['ANTHROPIC_API_KEY'],
        'groq': ['GROQ_API_KEY'],
        'openai': ['OPENAI_API_KEY'],
    },
    'image': {
        'gemini': ['GEMINI_API_KEY'],
        'huggingface': ['HF_TOKEN'],
        'cloudflare': ['CF_ACCOUNT_ID', 'CF_API_TOKEN'],
        'openai': ['OPENAI_API_KEY'],
    },
    'video': {
        'huggingface': ['HF_TOKEN'],
        'replicate': ['REPLICATE_API_TOKEN'],
    },
}

DEFAULT_MODELS = {
    ('text', 'anthropic'): 'claude-opus-5',
    ('text', 'groq'): 'openai/gpt-oss-120b',
    ('text', 'openai'): 'gpt-4.1-mini',
    ('image', 'gemini'): 'gemini-3.1-flash-image',
    ('image', 'huggingface'): 'stabilityai/stable-diffusion-3-medium-diffusers',
    ('image', 'cloudflare'): '@cf/black-forest-labs/flux-1-schnell',
    ('image', 'openai'): 'gpt-image-1',
    ('video', 'huggingface'): 'Wan-AI/Wan2.2-TI2V-5B',
    ('video', 'replicate'): 'wan-video/wan-2.2-i2v-fast',
}


def _platform_override(field):
    try:
        from apps.platform_settings.models import PlatformSettings

        return (getattr(PlatformSettings.load(), field, '') or '').strip()
    except Exception:  # noqa: BLE001 - DB not migrated yet / no DB access (e.g. collectstatic)
        return ''


def get_provider_name(kind):
    """kind: 'text' | 'image' | 'video'."""
    return _platform_override(f'ai_{kind}_provider') or getattr(settings, f'AI_{kind.upper()}_PROVIDER', '')


def get_model_name(kind):
    """The model for the active provider of `kind`. A provider override without a model
    override uses that provider's default model, since the .env model almost certainly
    belongs to the .env provider, not the overriding one.

    Likewise a .env model that is another provider's default (e.g. AI_IMAGE_PROVIDER
    switched to openai while AI_IMAGE_MODEL still names the Cloudflare model) is replaced
    by the active provider's default, so switching providers only needs the provider line."""
    model_override = _platform_override(f'ai_{kind}_model')
    if model_override:
        return model_override
    provider_override = _platform_override(f'ai_{kind}_provider')
    env_provider = getattr(settings, f'AI_{kind.upper()}_PROVIDER', '')
    if provider_override and provider_override != env_provider:
        return DEFAULT_MODELS.get((kind, provider_override), '')
    env_model = getattr(settings, f'AI_{kind.upper()}_MODEL', '')
    belongs_to_other_provider = any(
        model == env_model
        for (model_kind, provider), model in DEFAULT_MODELS.items()
        if model_kind == kind and provider != env_provider
    )
    if belongs_to_other_provider and (kind, env_provider) in DEFAULT_MODELS:
        return DEFAULT_MODELS[(kind, env_provider)]
    return env_model


def credentials_status():
    """{'text': {'openai': {'configured': False, 'env_vars': [...]}, ...}, ...} - booleans only."""
    return {
        kind: {
            provider: {
                'configured': all(bool(os.environ.get(var)) for var in env_vars),
                'env_vars': env_vars,
            }
            for provider, env_vars in providers.items()
        }
        for kind, providers in PROVIDER_CREDENTIALS.items()
    }


def get_content_language():
    """(code, label) of the language AI copy/voice-over should be produced in."""
    try:
        from apps.platform_settings.models import PlatformSettings

        platform_settings = PlatformSettings.load()
        return platform_settings.content_language, platform_settings.get_content_language_display()
    except Exception:  # noqa: BLE001
        return 'en', 'English'


def content_language_instruction():
    """A prompt line telling the model which language to write in - empty for English,
    so English prompts (and their tests) stay exactly as they were."""
    code, label = get_content_language()
    if code == 'en':
        return ''
    return (
        f'LANGUAGE: Write every piece of customer-facing text (captions, headlines, descriptions, CTAs, '
        f'narration) in {label}. Hashtags may stay in English. Brand and product names stay as given.'
    )
