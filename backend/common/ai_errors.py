"""Shared exception types for AI provider clients (text, image, video).

Kept provider-agnostic and app-agnostic so every AI-backed epic (05, 06, ...)
raises and handles the same two error categories.
"""


class AIProviderError(Exception):
    """Raised when a configured AI provider can't fulfill a request."""


class AIProviderNotConfigured(AIProviderError):
    """Raised when no API credentials are available for the configured provider."""
