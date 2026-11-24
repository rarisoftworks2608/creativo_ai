"""AgnesVideoProvider against mocked HTTP - never a real Agnes call."""

import io
import os
from unittest import mock

import httpx
from django.test import SimpleTestCase
from PIL import Image

from apps.video_generation import video_client
from apps.video_generation.video_client import AgnesVideoProvider, AIProviderError, AIProviderNotConfigured


def _png(size):
    buffer = io.BytesIO()
    Image.new('RGB', size, (20, 40, 60)).save(buffer, format='PNG')
    return buffer.getvalue()


def _response(status, json_body=None, content=b''):
    request = httpx.Request('GET', 'https://apihub.agnes-ai.com/x')
    if json_body is not None:
        return httpx.Response(status, json=json_body, request=request)
    return httpx.Response(status, content=content, request=request)


@mock.patch.dict(os.environ, {'AGNES_API_KEY': 'test-key'})
@mock.patch.object(video_client.time, 'sleep', lambda _seconds: None)
class AgnesVideoProviderTests(SimpleTestCase):
    def test_animates_the_scene_still_and_downloads_the_finished_clip(self):
        posts, gets = [], []

        def fake_post(url, **kwargs):
            posts.append((url, kwargs))
            return _response(200, {'video_id': 'video_123', 'status': 'queued'})

        polls = iter([{'status': 'in_progress'}, {'status': 'completed', 'video_url': 'https://cdn.agnes/clip.mp4'}])

        def fake_get(url, **kwargs):
            gets.append((url, kwargs))
            if url.endswith('clip.mp4'):
                return _response(200, content=b'MP4DATA')
            return _response(200, next(polls))

        with mock.patch('httpx.post', fake_post), mock.patch('httpx.get', fake_get):
            clip, mime = AgnesVideoProvider(model='agnes-video-v2.0').generate_video_clip(
                image_bytes=_png((768, 1344)), mime_type='image/png', prompt='Slow push in',
            )

        self.assertEqual((clip, mime), (b'MP4DATA', 'video/mp4'))
        url, kwargs = posts[0]
        self.assertEqual(url, 'https://apihub.agnes-ai.com/v1/videos')
        self.assertEqual(kwargs['headers']['Authorization'], 'Bearer test-key')
        body = kwargs['json']
        self.assertEqual(body['model'], 'agnes-video-v2.0')
        self.assertTrue(body['image'].startswith('data:image/png;base64,'))
        self.assertEqual((body['width'], body['height']), (768, 1152))  # a vertical still -> a vertical clip
        self.assertEqual((body['num_frames'] - 1) % 8, 0)
        self.assertEqual(gets[0][0], 'https://apihub.agnes-ai.com/agnesapi')
        self.assertEqual(gets[0][1]['params'], {'video_id': 'video_123', 'model_name': 'agnes-video-v2.0'})

    def test_an_inline_image_refused_falls_back_to_text_to_video(self):
        bodies = []

        def fake_post(url, **kwargs):
            bodies.append(dict(kwargs['json']))
            if 'image' in kwargs['json']:
                return _response(400, {'error': 'image must be a URL'})
            return _response(200, {'video_id': 'video_9', 'status': 'completed', 'url': 'https://cdn.agnes/c.mp4'})

        with mock.patch('httpx.post', fake_post), mock.patch('httpx.get', lambda url, **kw: _response(200, content=b'V')):
            clip, _mime = AgnesVideoProvider().generate_video_clip(
                image_bytes=_png((1024, 1024)), mime_type='image/png', prompt='Pan',
            )
        self.assertEqual(clip, b'V')
        self.assertIn('image', bodies[0])
        self.assertNotIn('image', bodies[1])
        self.assertEqual((bodies[1]['width'], bodies[1]['height']), (960, 960))

    def test_a_failed_task_raises_a_provider_error_so_the_scene_falls_back_to_zoom_pan(self):
        with mock.patch('httpx.post', lambda url, **kw: _response(200, {'video_id': 'video_1'})), \
                mock.patch('httpx.get', lambda url, **kw: _response(200, {'status': 'failed', 'error': 'division by zero'})):
            with self.assertRaisesMessage(AIProviderError, 'division by zero'):
                AgnesVideoProvider().generate_video_clip(image_bytes=b'', mime_type='image/png', prompt='x')

    def test_a_rejected_key_is_reported_as_not_configured(self):
        with mock.patch('httpx.post', lambda url, **kw: _response(401, {'error': 'unauthorized'})):
            with self.assertRaises(AIProviderNotConfigured):
                AgnesVideoProvider().generate_video_clip(image_bytes=_png((10, 10)), mime_type='image/png', prompt='x')

    def test_a_missing_key_never_calls_agnes(self):
        with mock.patch.dict(os.environ, {'AGNES_API_KEY': ''}), mock.patch('httpx.post') as post:
            with self.assertRaises(AIProviderNotConfigured):
                AgnesVideoProvider().generate_video_clip(image_bytes=b'', mime_type='image/png', prompt='x')
        post.assert_not_called()

    def test_selected_by_the_agnes_provider_setting(self):
        with mock.patch.object(video_client, 'get_provider_name', return_value='agnes'), \
                mock.patch.object(video_client, 'get_model_name', return_value='agnes-video-v2.0'):
            provider = video_client.get_video_provider()
        self.assertIsInstance(provider, AgnesVideoProvider)
        self.assertEqual(provider.model, 'agnes-video-v2.0')
