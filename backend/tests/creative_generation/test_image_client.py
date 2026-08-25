import base64
import os
from unittest.mock import MagicMock, patch

import httpx
from django.test import TestCase, override_settings

from apps.creative_generation.image_client import (
    AIProviderError,
    AIProviderNotConfigured,
    CloudflareImageProvider,
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


def fake_cf_response(*, status_code=200, success=True, image_b64=None, errors=None, url='https://api.cloudflare.com/client/v4/accounts/acc/ai/run/model'):
    body = {'success': success, 'errors': errors or [], 'messages': [], 'result': {}}
    if image_b64 is not None:
        body['result']['image'] = image_b64
    return httpx.Response(status_code=status_code, json=body, request=httpx.Request('POST', url))


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
    def test_sends_a_negative_prompt_to_suppress_baked_in_text(self, mock_post):
        mock_post.return_value = fake_response(
            content_type='image/jpeg', method='POST',
            url='https://router.huggingface.co/hf-inference/models/stabilityai/stable-diffusion-3-medium-diffusers',
        )
        provider = HuggingFaceImageProvider(model='stabilityai/stable-diffusion-3-medium-diffusers')

        provider.generate_image(prompt='a red bicycle')

        sent_json = mock_post.call_args.kwargs['json']
        self.assertIn('negative_prompt', sent_json['parameters'])
        self.assertIn('text', sent_json['parameters']['negative_prompt'])
        self.assertIn('logo', sent_json['parameters']['negative_prompt'])

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


class CloudflareImageProviderTests(TestCase):
    """Exercises the Cloudflare Workers AI wrapper (network mocked) to make sure every
    failure mode maps to AIProviderError/AIProviderNotConfigured rather than an uncaught
    exception, and that a normal (base64-in-JSON) response round-trips correctly.
    """

    def setUp(self):
        self._old_account = os.environ.pop('CF_ACCOUNT_ID', None)
        self._old_token = os.environ.pop('CF_API_TOKEN', None)
        os.environ['CF_ACCOUNT_ID'] = 'test-account'
        os.environ['CF_API_TOKEN'] = 'test-token'

    def tearDown(self):
        os.environ.pop('CF_ACCOUNT_ID', None)
        os.environ.pop('CF_API_TOKEN', None)
        if self._old_account is not None:
            os.environ['CF_ACCOUNT_ID'] = self._old_account
        if self._old_token is not None:
            os.environ['CF_API_TOKEN'] = self._old_token

    @patch('httpx.post')
    def test_success_returns_decoded_image_bytes(self, mock_post):
        raw_bytes = b'\xff\xd8\xff-fake-jpeg'
        mock_post.return_value = fake_cf_response(image_b64=base64.b64encode(raw_bytes).decode())
        provider = CloudflareImageProvider(model='@cf/black-forest-labs/flux-1-schnell')

        image_bytes, mime_type = provider.generate_image(prompt='a red bicycle')

        self.assertEqual(image_bytes, raw_bytes)
        self.assertEqual(mime_type, 'image/jpeg')

    @patch('httpx.post')
    def test_sends_account_id_in_url_and_token_in_header(self, mock_post):
        mock_post.return_value = fake_cf_response(image_b64=base64.b64encode(b'x').decode())
        provider = CloudflareImageProvider(model='@cf/black-forest-labs/flux-1-schnell')

        provider.generate_image(prompt='a red bicycle')

        called_url = mock_post.call_args.args[0]
        self.assertIn('test-account', called_url)
        self.assertIn('@cf/black-forest-labs/flux-1-schnell', called_url)
        self.assertEqual(mock_post.call_args.kwargs['headers']['Authorization'], 'Bearer test-token')

    @patch('httpx.post')
    def test_reference_images_are_accepted_but_ignored(self, mock_post):
        mock_post.return_value = fake_cf_response(image_b64=base64.b64encode(b'x').decode())
        provider = CloudflareImageProvider(model='test-model')

        provider.generate_image(prompt='a red bicycle', reference_images=[(b'logo-bytes', 'image/png')])

        mock_post.assert_called_once()

    def test_missing_account_id_raises_not_configured(self):
        os.environ.pop('CF_ACCOUNT_ID', None)
        provider = CloudflareImageProvider(model='test-model')

        with self.assertRaises(AIProviderNotConfigured):
            provider.generate_image(prompt='a red bicycle')

    def test_missing_token_raises_not_configured(self):
        os.environ.pop('CF_API_TOKEN', None)
        provider = CloudflareImageProvider(model='test-model')

        with self.assertRaises(AIProviderNotConfigured):
            provider.generate_image(prompt='a red bicycle')

    @patch('httpx.post')
    def test_invalid_token_raises_not_configured(self, mock_post):
        response = fake_cf_response(status_code=401, success=False)
        mock_post.return_value = response
        mock_post.return_value.raise_for_status = MagicMock(
            side_effect=httpx.HTTPStatusError('unauthorized', request=response.request, response=response)
        )
        provider = CloudflareImageProvider(model='test-model')

        with self.assertRaises(AIProviderNotConfigured):
            provider.generate_image(prompt='a red bicycle')

    @patch('httpx.post')
    def test_api_level_failure_raises_provider_error(self, mock_post):
        mock_post.return_value = fake_cf_response(
            success=False, errors=[{'code': 5007, 'message': 'model not found'}],
        )
        provider = CloudflareImageProvider(model='test-model')

        with self.assertRaises(AIProviderError):
            provider.generate_image(prompt='a red bicycle')

    @patch('httpx.post')
    def test_connection_failure_raises_provider_error(self, mock_post):
        mock_post.side_effect = httpx.ConnectError('connection refused')
        provider = CloudflareImageProvider(model='test-model')

        with self.assertRaises(AIProviderError):
            provider.generate_image(prompt='a red bicycle')

    @patch('httpx.post')
    def test_missing_image_in_response_raises_provider_error(self, mock_post):
        mock_post.return_value = fake_cf_response(image_b64=None)
        provider = CloudflareImageProvider(model='test-model')

        with self.assertRaises(AIProviderError):
            provider.generate_image(prompt='a red bicycle')

    @patch('httpx.post')
    def test_malformed_base64_raises_provider_error(self, mock_post):
        mock_post.return_value = fake_cf_response(image_b64='not-valid-base64!!!')
        provider = CloudflareImageProvider(model='test-model')

        with self.assertRaises(AIProviderError):
            provider.generate_image(prompt='a red bicycle')

    @patch('httpx.post')
    def test_long_prompt_is_truncated_to_fit_the_model_limit(self, mock_post):
        mock_post.return_value = fake_cf_response(image_b64=base64.b64encode(b'x').decode())
        provider = CloudflareImageProvider(model='test-model')
        long_prompt = 'a ' * 2000  # 4000 chars, well past MAX_PROMPT_CHARS

        provider.generate_image(prompt=long_prompt)

        sent_prompt = mock_post.call_args.kwargs['json']['prompt']
        self.assertLessEqual(len(sent_prompt), provider.MAX_PROMPT_CHARS)

    @patch('httpx.post')
    def test_truncated_prompt_still_ends_with_the_no_text_instruction(self, mock_post):
        mock_post.return_value = fake_cf_response(image_b64=base64.b64encode(b'x').decode())
        provider = CloudflareImageProvider(model='test-model')
        long_prompt = 'a ' * 2000

        provider.generate_image(prompt=long_prompt)

        sent_prompt = mock_post.call_args.kwargs['json']['prompt']
        self.assertTrue(sent_prompt.endswith(provider.CRITICAL_SUFFIX))

    @patch('httpx.post')
    def test_short_prompt_is_not_modified(self, mock_post):
        mock_post.return_value = fake_cf_response(image_b64=base64.b64encode(b'x').decode())
        provider = CloudflareImageProvider(model='test-model')

        provider.generate_image(prompt='a red bicycle')

        sent_prompt = mock_post.call_args.kwargs['json']['prompt']
        self.assertEqual(sent_prompt, 'a red bicycle')


class GetImageProviderFactoryTests(TestCase):
    def test_defaults_to_gemini(self):
        with override_settings(AI_IMAGE_PROVIDER='gemini'):
            self.assertIsInstance(get_image_provider(), GeminiImageProvider)

    def test_selects_huggingface(self):
        with override_settings(AI_IMAGE_PROVIDER='huggingface'):
            self.assertIsInstance(get_image_provider(), HuggingFaceImageProvider)

    def test_selects_cloudflare(self):
        with override_settings(AI_IMAGE_PROVIDER='cloudflare'):
            self.assertIsInstance(get_image_provider(), CloudflareImageProvider)

    def test_unknown_provider_raises(self):
        with override_settings(AI_IMAGE_PROVIDER='not-a-real-provider'):
            with self.assertRaises(AIProviderError):
                get_image_provider()
