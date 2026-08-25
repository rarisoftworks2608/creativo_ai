"""Provider-agnostic text/LLM client (Epic 05: AI Content Strategy).

Anthropic and Groq are implemented. Swapping providers means adding a
branch to `get_provider()` and a class implementing `TextAIProvider` -
callers (views) only ever depend on the abstract interface below, per the
project's "keep AI providers replaceable" principle (project_plan.md #44).
"""

import json
from abc import ABC, abstractmethod

from django.conf import settings

from common.ai_errors import AIProviderError, AIProviderNotConfigured

__all__ = [
    'AIProviderError', 'AIProviderNotConfigured', 'TextAIProvider',
    'AnthropicProvider', 'GroqProvider', 'get_provider',
]


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


class GroqProvider(TextAIProvider):
    """Uses Groq's OpenAI-compatible chat completions API with strict JSON
    schema mode - every schema in this codebase already sets
    additionalProperties: False at each object level, which is what Groq's
    strict mode requires.
    """

    def __init__(self, model=None):
        self.model = model or settings.AI_TEXT_MODEL

    def generate_json(self, *, system, prompt, json_schema):
        import groq

        try:
            client = groq.Groq()
            response = client.chat.completions.create(
                model=self.model,
                messages=[
                    {'role': 'system', 'content': system},
                    {'role': 'user', 'content': prompt},
                ],
                response_format={
                    'type': 'json_schema',
                    'json_schema': {'name': 'response', 'strict': True, 'schema': json_schema},
                },
            )
        except groq.AuthenticationError as exc:
            raise AIProviderNotConfigured('Groq API key is missing or invalid.') from exc
        except groq.RateLimitError as exc:
            raise AIProviderError('The AI provider is rate-limiting requests. Try again shortly.') from exc
        except groq.APIConnectionError as exc:
            raise AIProviderError('Could not reach the AI provider. Try again shortly.') from exc
        except groq.APIStatusError as exc:
            raise AIProviderError(f'AI provider error: {exc.message}') from exc
        except groq.GroqError as exc:
            # Raised synchronously by Groq() itself when no api_key was passed and
            # GROQ_API_KEY isn't set - never reaches the network.
            raise AIProviderNotConfigured(
                'Groq API credentials are not configured. Set GROQ_API_KEY in the backend environment.'
            ) from exc

        text = response.choices[0].message.content
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
    if provider_name == 'groq':
        return GroqProvider()
    raise AIProviderError(f'Unknown AI_TEXT_PROVIDER "{provider_name}".')
