"""Provider-agnostic AI motion (video generation) client (Epic 07: AI Video Generation).

Each scene already has a still image (see image_client.py, Epic 06's provider);
this turns that still into a few seconds of actual motion instead of the
FFmpeg zoom/pan fallback in rendering.py. Two providers are implemented:

- 'huggingface' (the default - free, no card required): text-to-video only,
  via Hugging Face's Inference Providers routed to fal-ai, billed against the
  same free monthly credit as HuggingFaceImageProvider (Epic 06) - $0.10/month
  per free HF account. That's enough for a couple of scenes; once it runs out
  each further scene raises AIProviderError like any other provider failure,
  and tasks.py falls back to zoom/pan rather than failing the whole request,
  since AI motion is an enhancement layer, not something the video needs to
  exist at all.
- 'replicate': proper image-to-video (animates the actual scene image, not
  just its text description), much higher quality, but no free tier - bills
  per second of generated video. An upgrade path once free-tier quality/limits
  stop being enough.

Swapping/adding a provider means adding a branch to `get_video_provider()` and
a class implementing `VideoAIProvider` - the same pattern as the text/image/
voice providers in Epics 05/06/07.
"""

import base64
import logging
import os
import time
from abc import ABC, abstractmethod

from django.conf import settings

from common.ai_config import get_model_name, get_provider_name
from common.ai_errors import AIProviderError, AIProviderNotConfigured

logger = logging.getLogger(__name__)

__all__ = [
    'AIProviderError', 'AIProviderNotConfigured', 'VideoAIProvider',
    'HuggingFaceVideoProvider', 'ReplicateVideoProvider', 'AgnesVideoProvider', 'get_video_provider',
]


class VideoAIProvider(ABC):
    @abstractmethod
    def generate_video_clip(self, *, image_bytes: bytes, mime_type: str, prompt: str) -> tuple[bytes, str]:
        """Animates a scene into a short video clip, guided by `prompt` (a motion/
        camera-movement description grounded in the scene's visual description).
        `image_bytes`/`mime_type` are the scene's already-generated still - providers
        that only support text-to-video accept but ignore them. Returns (video_bytes,
        mime_type).
        """


class HuggingFaceVideoProvider(VideoAIProvider):
    """Text-to-video via Hugging Face's Inference Providers, routed to fal-ai (the
    only route confirmed to serve a working text-to-video model at the time this was
    written - https://huggingface.co/docs/inference-providers/tasks/text-to-video).
    Needs HF_TOKEN (free to create, no card required - same token as
    HuggingFaceImageProvider, Epic 06); passing a genuine HF user access token (not a
    provider-native key) routes billing through HF's own free monthly credit rather
    than requiring a fal.ai account.

    image_bytes/mime_type are accepted for interface compatibility (VideoAIProvider)
    but ignored - Inference Providers doesn't yet expose a standardized image-to-video
    task, only text-to-video, so the clip is generated from `prompt` alone rather than
    animating the scene's actual still image.
    """

    ROUTE_PROVIDER = 'fal-ai'

    def __init__(self, model=None):
        self.model = model or get_model_name('video')

    def generate_video_clip(self, *, image_bytes, mime_type, prompt):
        token = os.environ.get('HF_TOKEN')
        if not token:
            raise AIProviderNotConfigured(
                'Hugging Face token is missing. Set HF_TOKEN in the backend environment.'
            )

        from huggingface_hub import InferenceClient
        from huggingface_hub.errors import HfHubHTTPError

        client = InferenceClient(provider=self.ROUTE_PROVIDER, token=token)
        try:
            video_bytes = client.text_to_video(prompt, model=self.model)
        except HfHubHTTPError as exc:
            status_code = getattr(exc.response, 'status_code', None)
            if status_code in (401, 403):
                raise AIProviderNotConfigured(
                    'Hugging Face token is invalid, or missing the "Inference Providers" '
                    'permission. Check HF_TOKEN in the backend environment.'
                ) from exc
            if status_code == 402:
                raise AIProviderError(
                    'Hugging Face Inference Providers free credit is used up for this month.'
                ) from exc
            if status_code == 429:
                raise AIProviderError('The AI provider is rate-limiting requests. Try again shortly.') from exc
            raise AIProviderError(f'Hugging Face video generation failed: {exc}') from exc
        except Exception as exc:  # noqa: BLE001 - normalize any SDK-internal failure
            raise AIProviderError(f'Hugging Face video generation failed: {exc}') from exc

        if not video_bytes:
            raise AIProviderError('The AI provider returned no video content.')
        return video_bytes, 'video/mp4'


class ReplicateVideoProvider(VideoAIProvider):
    """Runs an image-to-video model (default: wan-video/wan-2.2-i2v-fast) on Replicate
    (https://replicate.com). Needs REPLICATE_API_TOKEN - created at
    replicate.com/account/api-tokens; billed per second of generated video, no free tier.

    Uses Replicate's "models" prediction endpoint (always runs the model's latest
    version, no version id to keep in sync). Generation regularly takes longer than
    Replicate's 60s synchronous wait cap, so this polls the prediction instead of
    blocking on `Prefer: wait` - safe here since it already runs inside a Celery task,
    not a request/response HTTP view.
    """

    BASE_URL = 'https://api.replicate.com/v1'
    POLL_INTERVAL_SECONDS = 3
    POLL_TIMEOUT_SECONDS = 600
    REQUEST_TIMEOUT_SECONDS = 60.0

    def __init__(self, model=None):
        self.model = model or get_model_name('video')

    def _headers(self, token):
        return {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}

    def generate_video_clip(self, *, image_bytes, mime_type, prompt):
        import httpx

        token = getattr(settings, 'REPLICATE_API_TOKEN', '') or ''
        if not token:
            raise AIProviderNotConfigured(
                'Replicate API token is missing. Set REPLICATE_API_TOKEN in the backend environment.'
            )

        image_data_uri = f'data:{mime_type};base64,{base64.b64encode(image_bytes).decode("ascii")}'

        try:
            response = httpx.post(
                f'{self.BASE_URL}/models/{self.model}/predictions',
                headers=self._headers(token),
                json={'input': {'image': image_data_uri, 'prompt': prompt}},
                timeout=self.REQUEST_TIMEOUT_SECONDS,
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code in (401, 403):
                raise AIProviderNotConfigured(
                    'Replicate API token is invalid. Check REPLICATE_API_TOKEN in the backend environment.'
                ) from exc
            if exc.response.status_code == 429:
                raise AIProviderError('The AI provider is rate-limiting requests. Try again shortly.') from exc
            raise AIProviderError(f'Replicate video generation failed to start: {exc}') from exc
        except httpx.HTTPError as exc:
            raise AIProviderError(f'Could not reach the AI provider: {exc}') from exc

        prediction = response.json()
        get_url = (prediction.get('urls') or {}).get('get')
        if not get_url:
            raise AIProviderError('The AI provider did not return a prediction to poll.')

        deadline = time.monotonic() + self.POLL_TIMEOUT_SECONDS
        while True:
            status = prediction.get('status')
            if status == 'succeeded':
                break
            if status in ('failed', 'canceled'):
                detail = prediction.get('error') or f'prediction {status}'
                raise AIProviderError(f'Replicate video generation failed: {detail}')
            if time.monotonic() >= deadline:
                raise AIProviderError('Timed out waiting for the AI provider to render the video clip.')
            time.sleep(self.POLL_INTERVAL_SECONDS)
            try:
                poll_response = httpx.get(get_url, headers=self._headers(token), timeout=self.REQUEST_TIMEOUT_SECONDS)
                poll_response.raise_for_status()
            except httpx.HTTPError as exc:
                raise AIProviderError(f'Could not reach the AI provider: {exc}') from exc
            prediction = poll_response.json()

        output = prediction.get('output')
        video_url = output[0] if isinstance(output, list) else output
        if not video_url:
            raise AIProviderError('The AI provider returned no video content.')

        try:
            video_response = httpx.get(video_url, timeout=self.REQUEST_TIMEOUT_SECONDS)
            video_response.raise_for_status()
        except httpx.HTTPError as exc:
            raise AIProviderError(f'Could not download the generated video clip: {exc}') from exc

        return video_response.content, 'video/mp4'


class AgnesVideoProvider(VideoAIProvider):
    """Image-to-video on Agnes AI (https://apihub.agnes-ai.com, model agnes-video-v2.0). Needs AGNES_API_KEY.

    Asynchronous like Replicate: `POST /v1/videos` starts a task and returns a `video_id`, then
    `GET /agnesapi?video_id=...` is polled until `status` is `completed` (or `failed`); the clip's URL is in
    `video_url` / `url`. The scene's still is sent as a data URI in `image` so the clip animates the actual
    picture; if Agnes refuses an inline image, the clip is made from the prompt alone (text-to-video).
    Clip length is frames / frame rate - 121 frames at 24 fps, about 5 seconds; rendering.py loops or trims it
    to the scene's duration.
    """

    BASE_URL = 'https://apihub.agnes-ai.com'
    NUM_FRAMES = 121  # must be 8n + 1 and <= 441
    FRAME_RATE = 24
    POLL_INTERVAL_SECONDS = 10
    POLL_TIMEOUT_SECONDS = 900
    REQUEST_TIMEOUT_SECONDS = 120.0
    # (width, height) per picture shape - Agnes' documented default is 1152 x 768 landscape.
    SIZES = {'landscape': (1152, 768), 'portrait': (768, 1152), 'square': (960, 960)}

    def __init__(self, model=None):
        self.model = model or get_model_name('video') or 'agnes-video-v2.0'

    def _token(self):
        # Read from the environment only (like HF_TOKEN), so the test suite's key-blanking always applies.
        token = os.environ.get('AGNES_API_KEY', '')
        if not token:
            raise AIProviderNotConfigured('Agnes API key is missing. Set AGNES_API_KEY in the backend environment.')
        return token

    @classmethod
    def _size_for(cls, image_bytes):
        try:
            import io

            from PIL import Image

            width, height = Image.open(io.BytesIO(image_bytes)).size
        except Exception:  # noqa: BLE001 - unreadable still: Agnes' default landscape size
            return cls.SIZES['landscape']
        ratio = width / height if height else 1.0
        if ratio > 1.15:
            return cls.SIZES['landscape']
        if ratio < 0.87:
            return cls.SIZES['portrait']
        return cls.SIZES['square']

    def _raise_for(self, exc, action):
        status_code = exc.response.status_code
        logger.warning('Agnes video request failed to %s (HTTP %s): %s', action, status_code, exc.response.text[:500])
        if status_code in (401, 403):
            raise AIProviderNotConfigured('Agnes API key is invalid. Check AGNES_API_KEY in the backend environment.') from exc
        if status_code == 429:
            raise AIProviderError('The AI provider is rate-limiting requests. Try again shortly.') from exc
        raise AIProviderError(f'Agnes video generation failed to {action}: {exc}') from exc

    @staticmethod
    def _video_url(data):
        for key in ('video_url', 'url'):
            value = data.get(key)
            if isinstance(value, str) and value.startswith(('http://', 'https://')):
                return value
        for item in data.get('data') or []:
            if isinstance(item, dict):
                found = AgnesVideoProvider._video_url(item)
                if found:
                    return found
        return ''

    def generate_video_clip(self, *, image_bytes, mime_type, prompt):
        import httpx

        token = self._token()
        headers = {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}
        width, height = self._size_for(image_bytes)
        payload = {
            'model': self.model, 'prompt': prompt, 'width': width, 'height': height,
            'num_frames': self.NUM_FRAMES, 'frame_rate': self.FRAME_RATE,
        }
        if image_bytes:
            payload['image'] = f'data:{mime_type};base64,{base64.b64encode(image_bytes).decode("ascii")}'

        try:
            response = httpx.post(
                f'{self.BASE_URL}/v1/videos', headers=headers, json=payload, timeout=self.REQUEST_TIMEOUT_SECONDS,
            )
            if 'image' in payload and (response.status_code in (400, 413, 422) or response.status_code >= 500):
                # The inline still was refused (Agnes documents image URLs, and has answered an inline image with a
                # 500): make the clip from the prompt alone rather than lose the motion.
                logger.warning(
                    'Agnes refused the scene image (HTTP %s: %s) - retrying as text-to-video.',
                    response.status_code, response.text[:300],
                )
                payload.pop('image')
                response = httpx.post(
                    f'{self.BASE_URL}/v1/videos', headers=headers, json=payload, timeout=self.REQUEST_TIMEOUT_SECONDS,
                )
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            self._raise_for(exc, 'start')
        except httpx.HTTPError as exc:
            raise AIProviderError(f'Could not reach the AI provider: {exc}') from exc

        task = response.json()
        video_id = task.get('video_id') or ''
        task_id = task.get('task_id') or task.get('id') or ''
        if not (video_id or task_id):
            raise AIProviderError('The AI provider did not return a video task to poll.')
        if video_id:
            poll_url, params = f'{self.BASE_URL}/agnesapi', {'video_id': video_id, 'model_name': self.model}
        else:  # older responses only carry a task id
            poll_url, params = f'{self.BASE_URL}/v1/videos/{task_id}', None

        deadline = time.monotonic() + self.POLL_TIMEOUT_SECONDS
        result = task
        while True:
            status = str(result.get('status', '')).lower()
            if result.get('error') or status == 'failed':
                detail = result.get('error') or 'the task failed'
                raise AIProviderError(f'Agnes video generation failed: {detail}')
            if status == 'completed':
                break
            if time.monotonic() >= deadline:
                raise AIProviderError('Timed out waiting for the AI provider to render the video clip.')
            time.sleep(self.POLL_INTERVAL_SECONDS)
            try:
                poll = httpx.get(poll_url, headers=headers, params=params, timeout=self.REQUEST_TIMEOUT_SECONDS)
                poll.raise_for_status()
            except httpx.HTTPStatusError as exc:
                self._raise_for(exc, 'report progress')
            except httpx.HTTPError as exc:
                raise AIProviderError(f'Could not reach the AI provider: {exc}') from exc
            result = poll.json()

        video_url = self._video_url(result)
        if not video_url:
            raise AIProviderError('The AI provider returned no video content.')
        try:
            video = httpx.get(video_url, timeout=self.REQUEST_TIMEOUT_SECONDS, follow_redirects=True)
            video.raise_for_status()
        except httpx.HTTPError as exc:
            raise AIProviderError(f'Could not download the generated video clip: {exc}') from exc
        return video.content, 'video/mp4'


def get_video_provider() -> VideoAIProvider:
    provider_name = get_provider_name('video') or 'huggingface'
    if provider_name == 'huggingface':
        return HuggingFaceVideoProvider()
    if provider_name == 'replicate':
        return ReplicateVideoProvider()
    if provider_name == 'agnes':
        return AgnesVideoProvider()
    raise AIProviderError(f'Unknown AI_VIDEO_PROVIDER "{provider_name}".')
