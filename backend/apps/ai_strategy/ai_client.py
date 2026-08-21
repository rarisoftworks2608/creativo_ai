"""Provider-agnostic text/LLM client (Epic 05: AI Content Strategy).

Only Anthropic is implemented today. Swapping providers means adding a
branch to `get_provider()` and a class implementing `TextAIProvider` -
callers (views) only ever depend on the abstract interface below, per the
project's "keep AI providers replaceable" principle (project_plan.md #44).
"""

import json
from abc import ABC, abstractmethod

from django.conf import settings

from common.ai_errors import AIProviderError, AIProviderNotConfigured

__all__ = ['AIProviderError', 'AIProviderNotConfigured', 'TextAIProvider', 'AnthropicProvider', 'get_provider']


class TextAIProvider(ABC):
    @abstractmethod
    def generate_json(self, *, system: str, prompt: str, json_schema: dict) -> dict:
        """Generate a JSON object matching json_schema, given a system prompt and user prompt."""


class AnthropicProvider(TextAIProvider):
    def __init__(self, model=None):
        self.model = model or settings.AI_TEXT_MODEL

    def generate_json(self, *, system, prompt, json_schema):
        import anthropic

        try:
            client = anthropic.Anthropic()
            response = client.messages.create(
                model=self.model,
                max_tokens=8000,
                system=system,
                messages=[{'role': 'user', 'content': prompt}],
                output_config={'format': {'type': 'json_schema', 'schema': json_schema}},
            )
        except anthropic.AuthenticationError as exc:
            raise AIProviderNotConfigured('Anthropic API key is missing or invalid.') from exc
        except anthropic.RateLimitError as exc:
            raise AIProviderError('The AI provider is rate-limiting requests. Try again shortly.') from exc
        except anthropic.APIConnectionError as exc:
            raise AIProviderError('Could not reach the AI provider. Try again shortly.') from exc
        except anthropic.APIStatusError as exc:
            raise AIProviderError(f'AI provider error: {exc.message}') from exc
        except TypeError as exc:
            # The SDK raises a plain TypeError - not an AnthropicError subclass - when it
            # can't resolve any credentials at all (no API key, auth token, or ant profile).
            raise AIProviderNotConfigured(
                'Anthropic API credentials are not configured. Set ANTHROPIC_API_KEY in the backend environment.'
            ) from exc

        text = next((block.text for block in response.content if block.type == 'text'), None)
        if text is None:
            raise AIProviderError('The AI provider returned no text content.')
        try:
            return json.loads(text)
        except json.JSONDecodeError as exc:
            raise AIProviderError('The AI provider returned invalid JSON.') from exc


def get_provider() -> TextAIProvider:
    provider_name = getattr(settings, 'AI_TEXT_PROVIDER', 'anthropic')
    if provider_name == 'anthropic':
        return AnthropicProvider()
    raise AIProviderError(f'Unknown AI_TEXT_PROVIDER "{provider_name}".')
