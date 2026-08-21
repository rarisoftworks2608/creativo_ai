"""Provider-agnostic voice-over (text-to-speech) client (Epic 07: AI Video Generation).

gTTS is the default provider: it's free and needs no API key (it calls
Google Translate's public TTS endpoint), so voice-over works out of the box
with no setup. Swapping in a paid provider (e.g. ElevenLabs) later means
adding a branch to `get_voice_provider()` and a class implementing
VoiceAIProvider - the same pattern as the text/image providers in Epics 05/06.
"""

from abc import ABC, abstractmethod
from io import BytesIO

from django.conf import settings

from common.ai_errors import AIProviderError, AIProviderNotConfigured

__all__ = ['AIProviderError', 'AIProviderNotConfigured', 'VoiceAIProvider', 'GTTSVoiceProvider', 'get_voice_provider']


class VoiceAIProvider(ABC):
    @abstractmethod
    def synthesize_speech(self, *, text: str, voice: str = '') -> tuple[bytes, str]:
        """Synthesizes narration audio for `text`. Returns (audio_bytes, mime_type)."""


class GTTSVoiceProvider(VoiceAIProvider):
    def synthesize_speech(self, *, text, voice=''):
        if not text.strip():
            raise AIProviderError('No narration text was provided for this scene.')

        from gtts import gTTS

        try:
            tts = gTTS(text=text, lang='en')
            buffer = BytesIO()
            tts.write_to_fp(buffer)
        except Exception as exc:
            raise AIProviderError(f'Voice-over generation failed: {exc}') from exc

        return buffer.getvalue(), 'audio/mpeg'


def get_voice_provider() -> VoiceAIProvider:
    provider_name = getattr(settings, 'AI_VOICE_PROVIDER', 'gtts')
    if provider_name == 'gtts':
        return GTTSVoiceProvider()
    raise AIProviderError(f'Unknown AI_VOICE_PROVIDER "{provider_name}".')
