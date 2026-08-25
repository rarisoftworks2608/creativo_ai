"""Provider-agnostic image generation client (Epic 06: AI Creative Generation).

Gemini, Hugging Face, and Cloudflare Workers AI are implemented. Swapping
providers means adding a branch to `get_image_provider()` and a class
implementing `ImageAIProvider` - the same pattern as
apps.ai_strategy.ai_client's text provider (Epic 05).

The google-genai SDK's exact exception hierarchy for auth/quota/network
failures is less battle-tested here than the Anthropic client in Epic 05,
so failures are deliberately caught broadly and normalized to
AIProviderError/AIProviderNotConfigured rather than risking an unhandled
exception reaching the view layer.
"""

import base64
import os
from abc import ABC, abstractmethod

from django.conf import settings

from common.ai_errors import AIProviderError, AIProviderNotConfigured

__all__ = [
    'AIProviderError', 'AIProviderNotConfigured', 'ImageAIProvider', 'GeminiImageProvider',
    'HuggingFaceImageProvider', 'CloudflareImageProvider', 'get_image_provider',
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

    # A prompt-level "do not render text" instruction is unreliable on diffusion models -
    # negative_prompt is the mechanism actually built for suppressing unwanted elements,
    # and is far more effective in practice. Also targets the usual diffusion artifacts
    # (blur, distortion, extra limbs) since a clean, in-focus photo matters just as much
    # as a text-free one once the compositor is the only thing drawing text/logo.
    NEGATIVE_PROMPT = (
        'text, words, letters, typography, writing, caption, watermark, '
        'logo, brand logo, emblem, insignia, brand mark, badge, seal, trademark, product label, packaging text, '
        'blurry, low quality, distorted, deformed, disfigured, extra limbs, extra fingers, '
        'mutated hands, out of frame, cropped, jpeg artifacts, worst quality, '
        'illustration, cartoon, anime, painting, drawing, sketch, 3d render, cgi, plastic skin, '
        'airbrushed, artificial, fake, doll-like'
    )

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
                json={'inputs': prompt, 'parameters': {'negative_prompt': self.NEGATIVE_PROMPT}},
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


class CloudflareImageProvider(ImageAIProvider):
    """Uses Cloudflare Workers AI (https://developers.cloudflare.com/workers-ai/) to run
    FLUX.1 [schnell]. The best free tier found so far: every Cloudflare account gets
    10,000 free "Neurons" a day (resets daily, not monthly), enough for roughly 100+
    full-size images/day - versus Hugging Face's $0.10/month. Needs CF_ACCOUNT_ID (from
    the Cloudflare dashboard URL/sidebar) and CF_API_TOKEN (an API token with "Workers AI
    - Read/Edit" permission, from dash.cloudflare.com/profile/api-tokens) - both free, no
    card required to create them, though Cloudflare may ask for one on the account itself.

    Reference images aren't supported - FLUX.1 [schnell] is text-to-image only.
    reference_images is accepted for interface compatibility but ignored, same as the
    other providers above.
    """

    BASE_URL = 'https://api.cloudflare.com/client/v4/accounts'
    DEFAULT_TIMEOUT_SECONDS = 60.0

    # FLUX.1 [schnell]'s hard limit, per Cloudflare's docs - the shared prompt built by
    # prompts.build_image_prompt() (brand voice, do's/don'ts, ...) routinely exceeds this
    # for a company with a fleshed-out brand profile, even though it's well within what
    # every other provider here accepts, so this provider has to defend itself.
    MAX_PROMPT_CHARS = 2048
    # Since there's no negative_prompt on this model (see NEGATIVE_PROMPT's absence),
    # this is the only lever suppressing baked-in text/logos - it must never be the part
    # that gets cut if the prompt is over budget.
    CRITICAL_SUFFIX = (
        ' Do not render any text, logo, or watermark into the image - clean photographic '
        'visual only, photorealistic, professional photography.'
    )

    def __init__(self, model=None):
        self.model = model or settings.AI_IMAGE_MODEL

    def _fit_prompt(self, prompt):
        if len(prompt) <= self.MAX_PROMPT_CHARS:
            return prompt
        budget = self.MAX_PROMPT_CHARS - len(self.CRITICAL_SUFFIX)
        return prompt[:budget].rsplit(' ', 1)[0] + self.CRITICAL_SUFFIX

    def generate_image(self, *, prompt, reference_images=None):
        import httpx

        prompt = self._fit_prompt(prompt)

        account_id = os.environ.get('CF_ACCOUNT_ID')
        api_token = os.environ.get('CF_API_TOKEN')
        if not account_id or not api_token:
            raise AIProviderNotConfigured(
                'Cloudflare credentials are missing. Set CF_ACCOUNT_ID and CF_API_TOKEN in the backend environment.'
            )
        headers = {'Authorization': f'Bearer {api_token}'}

        try:
            response = httpx.post(
                f'{self.BASE_URL}/{account_id}/ai/run/{self.model}',
                headers=headers,
                # FLUX.1 [schnell] has no negative_prompt/guidance parameter at all (it's a
                # guidance-distilled model) - `steps` (max 8, default 4) is the only lever
                # available for quality/prompt-adherence on this endpoint.
                json={'prompt': prompt, 'steps': 8},
                timeout=self.DEFAULT_TIMEOUT_SECONDS,
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code in (401, 403):
                raise AIProviderNotConfigured(
                    'Cloudflare API token is invalid or missing "Workers AI" permission. '
                    'Check CF_API_TOKEN in the backend environment.'
                ) from exc
            if exc.response.status_code == 429:
                raise AIProviderError('The AI provider is rate-limiting requests. Try again shortly.') from exc
            raise AIProviderError(f'Cloudflare image generation failed: {exc}') from exc
        except httpx.HTTPError as exc:
            raise AIProviderError(f'Could not reach the AI provider: {exc}') from exc

        try:
            payload = response.json()
        except ValueError as exc:
            raise AIProviderError('The AI provider returned a non-JSON response.') from exc

        if not payload.get('success'):
            messages = [e.get('message', str(e)) for e in (payload.get('errors') or [])]
            raise AIProviderError(f'Cloudflare image generation failed: {"; ".join(messages) or "unknown error"}')

        image_b64 = (payload.get('result') or {}).get('image')
        if not image_b64:
            raise AIProviderError('The AI provider returned no image content.')
        try:
            return base64.b64decode(image_b64), 'image/jpeg'
        except ValueError as exc:
            raise AIProviderError('The AI provider returned malformed image data.') from exc


def get_image_provider() -> ImageAIProvider:
    provider_name = getattr(settings, 'AI_IMAGE_PROVIDER', 'gemini')
    if provider_name == 'gemini':
        return GeminiImageProvider()
    if provider_name == 'huggingface':
        return HuggingFaceImageProvider()
    if provider_name == 'cloudflare':
        return CloudflareImageProvider()
    raise AIProviderError(f'Unknown AI_IMAGE_PROVIDER "{provider_name}".')
