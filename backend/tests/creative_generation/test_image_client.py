import os
from unittest.mock import MagicMock, patch

import httpx
from django.test import TestCase, override_settings

from apps.creative_generation.image_client import (
    AIProviderError,
    AIProviderNotConfigured,
    GeminiImageProvider,
    HuggingFaceImageProvider,
    get_image_provider,
)


def fake_response(*, status_code=200, content_type='image/jpeg', content=b'fake-image-bytes', method='GET', url='https://router.huggingface.co/hf-inference/models/test'):
    response = httpx.Response(
        status_code=status_code,
        headers={'content-type': content_type},
        content=content,
        request=httpx.Request(method, url),
    )
    return response


class HuggingFaceImageProviderTests(TestCase):
    """Exercises the HF Inference wrapper (network mocked) to make sure every failure
    mode maps to AIProviderError/AIProviderNotConfigured rather than an uncaught
    exception, and that a normal (raw-bytes) response round-trips correctly.
    """

    def setUp(self):
        self._old_token = os.environ.pop('HF_TOKEN', None)
        os.environ['HF_TOKEN'] = 'test-token'

    def tearDown(self):
        os.environ.pop('HF_TOKEN', None)
        if self._old_token is not None:
            os.environ['HF_TOKEN'] = self._old_token

    @patch('httpx.post')
    def test_success_returns_image_bytes_and_content_type(self, mock_post):
        mock_post.return_value = fake_response(
            content_type='image/jpeg', content=b'\xff\xd8\xff', method='POST',
            url='https://router.huggingface.co/hf-inference/models/stabilityai/stable-diffusion-3-medium-diffusers',
        )
        provider = HuggingFaceImageProvider(model='stabilityai/stable-diffusion-3-medium-diffusers')

        image_bytes, mime_type = provider.generate_image(prompt='a red bicycle')

        self.assertEqual(image_bytes, b'\xff\xd8\xff')
        self.assertEqual(mime_type, 'image/jpeg')

    @patch('httpx.post')
    def test_reference_images_are_accepted_but_ignored(self, mock_post):
        mock_post.return_value = fake_response(method='POST', url='https://router.huggingface.co/hf-inference/models/test-model')
        provider = HuggingFaceImageProvider(model='test-model')

        provider.generate_image(prompt='a red bicycle', reference_images=[(b'logo-bytes', 'image/png')])

        mock_post.assert_called_once()

    def test_missing_credentials_raises_not_configured(self):
        os.environ.pop('HF_TOKEN', None)
        provider = HuggingFaceImageProvider(model='test-model')

        with self.assertRaises(AIProviderNotConfigured):
            provider.generate_image(prompt='a red bicycle')

    @patch('httpx.post')
    def test_invalid_token_raises_not_configured(self, mock_post):
        response = fake_response(status_code=401, method='POST', url='https://router.huggingface.co/hf-inference/models/test-model')
        mock_post.return_value = response
        mock_post.return_value.raise_for_status = MagicMock(
            side_effect=httpx.HTTPStatusError('unauthorized', request=response.request, response=response)
        )
        provider = HuggingFaceImageProvider(model='test-model')

        with self.assertRaises(AIProviderNotConfigured):
            provider.generate_image(prompt='a red bicycle')

    @patch('httpx.post')
    def test_cold_start_raises_provider_error(self, mock_post):
        response = fake_response(status_code=503, method='POST', url='https://router.huggingface.co/hf-inference/models/test-model')
        mock_post.return_value = response
        mock_post.return_value.raise_for_status = MagicMock(
            side_effect=httpx.HTTPStatusError('loading', request=response.request, response=response)
        )
        provider = HuggingFaceImageProvider(model='test-model')

        with self.assertRaises(AIProviderError):
            provider.generate_image(prompt='a red bicycle')

    @patch('httpx.post')
    def test_connection_failure_raises_provider_error(self, mock_post):
        mock_post.side_effect = httpx.ConnectError('connection refused')
        provider = HuggingFaceImageProvider(model='test-model')

        with self.assertRaises(AIProviderError):
            provider.generate_image(prompt='a red bicycle')

    @patch('httpx.post')
    def test_non_image_response_raises_provider_error(self, mock_post):
        mock_post.return_value = fake_response(
            content_type='application/json', content=b'{}', method='POST',
            url='https://router.huggingface.co/hf-inference/models/test-model',
        )
        provider = HuggingFaceImageProvider(model='test-model')

        with self.assertRaises(AIProviderError):
            provider.generate_image(prompt='a red bicycle')


class GetImageProviderFactoryTests(TestCase):
    def test_defaults_to_gemini(self):
        with override_settings(AI_IMAGE_PROVIDER='gemini'):
            self.assertIsInstance(get_image_provider(), GeminiImageProvider)

    def test_selects_huggingface(self):
        with override_settings(AI_IMAGE_PROVIDER='huggingface'):
            self.assertIsInstance(get_image_provider(), HuggingFaceImageProvider)

    def test_unknown_provider_raises(self):
        with override_settings(AI_IMAGE_PROVIDER='not-a-real-provider'):
            with self.assertRaises(AIProviderError):
                get_image_provider()
