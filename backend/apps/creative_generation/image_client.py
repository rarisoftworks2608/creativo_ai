"""Provider-agnostic image generation client (Epic 06: AI Creative Generation).

Gemini and Hugging Face are implemented. Swapping providers means adding a
branch to `get_image_provider()` and a class implementing
`ImageAIProvider` - the same pattern as apps.ai_strategy.ai_client's text
provider (Epic 05).

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
    'AIProviderError', 'AIProviderNotConfigured', 'ImageAIProvider', 'GeminiImageProvider',
    'HuggingFaceImageProvider', 'get_image_provider',
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


class HuggingFaceImageProvider(ImageAIProvider):
    """Uses Hugging Face's own first-party serverless compute (the "hf-inference"
    provider - https://huggingface.co/docs/inference-providers/en/providers/hf-inference).
    HF_TOKEN is free to create (Settings -> Access Tokens, with "Inference Providers"
    permission) - no card required. Free accounts get $0.10/month in Inference Provider
    credits (billed by compute time, same as any other provider); once that's spent,
    calls fail until the credits renew next month or more are purchased - check
    huggingface.co/settings/billing for the actual balance. Can also have cold-start
    delays on less-frequently-used models.

    Reference images (e.g. brand logo) aren't supported - the default model
    (stable-diffusion-3-medium) is text-to-image only. reference_images is accepted for
    interface compatibility but ignored, same as the other providers above.
    """

    BASE_URL = 'https://router.huggingface.co/hf-inference/models'
    DEFAULT_TIMEOUT_SECONDS = 120.0

    def __init__(self, model=None):
        self.model = model or settings.AI_IMAGE_MODEL

    def generate_image(self, *, prompt, reference_images=None):
        import httpx

        token = os.environ.get('HF_TOKEN')
        if not token:
            raise AIProviderNotConfigured(
                'Hugging Face token is missing. Set HF_TOKEN in the backend environment.'
            )
        headers = {'Authorization': f'Bearer {token}'}

        try:
            response = httpx.post(
                f'{self.BASE_URL}/{self.model}',
                headers=headers,
                json={'inputs': prompt},
                timeout=self.DEFAULT_TIMEOUT_SECONDS,
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code in (401, 403):
                raise AIProviderNotConfigured(
                    'Hugging Face token is invalid, or missing the "Inference Providers" '
                    'permission. Check HF_TOKEN in the backend environment.'
                ) from exc
            if exc.response.status_code == 503:
                raise AIProviderError('The AI provider is loading the model (cold start). Try again shortly.') from exc
            if exc.response.status_code == 429:
                raise AIProviderError('The AI provider is rate-limiting requests. Try again shortly.') from exc
            raise AIProviderError(f'Hugging Face image generation failed: {exc}') from exc
        except httpx.HTTPError as exc:
            raise AIProviderError(f'Could not reach the AI provider: {exc}') from exc

        content_type = response.headers.get('content-type', '').split(';')[0].strip()
        if not content_type.startswith('image/'):
            raise AIProviderError('The AI provider returned no image content.')
        return response.content, content_type


def get_image_provider() -> ImageAIProvider:
    provider_name = getattr(settings, 'AI_IMAGE_PROVIDER', 'gemini')
    if provider_name == 'gemini':
        return GeminiImageProvider()
    if provider_name == 'huggingface':
        return HuggingFaceImageProvider()
    raise AIProviderError(f'Unknown AI_IMAGE_PROVIDER "{provider_name}".')
