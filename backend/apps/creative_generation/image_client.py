"""Provider-agnostic image generation client (Epic 06: AI Creative Generation).

Only Gemini is implemented today. Swapping providers means adding a branch
to `get_image_provider()` and a class implementing `ImageAIProvider` - the
same pattern as apps.ai_strategy.ai_client's text provider (Epic 05).

The google-genai SDK's exact exception hierarchy for auth/quota/network
failures is less battle-tested here than the Anthropic client in Epic 05,
so failures are deliberately caught broadly and normalized to
AIProviderError/AIProviderNotConfigured rather than risking an unhandled
exception reaching the view layer.
"""

import os
from abc import ABC, abstractmethod

from django.conf import settings

from common.ai_errors import AIProviderError, AIProviderNotConfigured

__all__ = [
    'AIProviderError', 'AIProviderNotConfigured', 'ImageAIProvider', 'GeminiImageProvider', 'get_image_provider',
]


class ImageAIProvider(ABC):
    @abstractmethod
    def generate_image(self, *, prompt: str, reference_images: list[tuple[bytes, str]] | None = None) -> tuple[bytes, str]:
        """Generate an image from a text prompt, optionally grounded by reference images
        (e.g. a brand logo) passed as a list of (raw_bytes, mime_type) tuples.

        Returns (image_bytes, mime_type).
        """


class GeminiImageProvider(ImageAIProvider):
    def __init__(self, model=None):
        self.model = model or settings.AI_IMAGE_MODEL

    def generate_image(self, *, prompt, reference_images=None):
        if not os.environ.get('GEMINI_API_KEY'):
            raise AIProviderNotConfigured(
                'Gemini API credentials are not configured. Set GEMINI_API_KEY in the backend environment.'
            )

        from google import genai
        from google.genai import types

        contents = [prompt]
        for image_bytes, mime_type in (reference_images or []):
            contents.append(types.Part.from_bytes(data=image_bytes, mime_type=mime_type))

        try:
            client = genai.Client()
            response = client.models.generate_content(
                model=self.model,
                contents=contents,
                config=types.GenerateContentConfig(response_modalities=['IMAGE']),
            )
        except Exception as exc:
            raise AIProviderError(f'Gemini image generation failed: {exc}') from exc

        parts = getattr(response, 'parts', None) or []
        image_part = next((p for p in parts if getattr(p, 'inline_data', None)), None)
        if image_part is None:
            raise AIProviderError('The AI provider returned no image content.')
        return image_part.inline_data.data, image_part.inline_data.mime_type


def get_image_provider() -> ImageAIProvider:
    provider_name = getattr(settings, 'AI_IMAGE_PROVIDER', 'gemini')
    if provider_name == 'gemini':
        return GeminiImageProvider()
    raise AIProviderError(f'Unknown AI_IMAGE_PROVIDER "{provider_name}".')
