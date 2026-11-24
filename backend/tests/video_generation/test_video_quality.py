"""Background music when the library is empty, scene pictures drawn in the video's shape, sharper rendering."""

import io
import os
import tempfile
import wave
from types import SimpleNamespace
from unittest import mock

import httpx
from django.test import SimpleTestCase
from PIL import Image

from apps.video_generation import prompts, rendering
from apps.video_generation.models import VideoGenerationRequest
from apps.video_generation.music_bed import write_music_bed
from apps.video_generation.tasks import _scene_image
from apps.video_generation.video_client import AgnesVideoProvider

from .test_video_generation import (
    BaseVideoGenerationTestCase, FakeImageProvider, FakeTextProvider, FakeVideoProvider, FakeVoiceProvider,
    fake_render_result,
)


class MusicBedTests(SimpleTestCase):
    def test_writes_a_seamless_sixteen_second_loop(self):
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, 'bed.wav')
            self.assertEqual(write_music_bed(path, seed=1), 16.0)
            with wave.open(path) as bed:
                self.assertAlmostEqual(bed.getnframes() / bed.getframerate(), 16.0, places=1)
                frames = bed.readframes(bed.getnframes())
        loud = max(abs(int.from_bytes(frames[i:i + 2], 'little', signed=True)) for i in range(0, len(frames), 2))
        self.assertGreater(loud, 20000)  # an audible bed, normalised - not silence
        self.assertLess(abs(int.from_bytes(frames[:2], 'little', signed=True)), 50)  # starts from silence: no click


class MusicSelectionTests(BaseVideoGenerationTestCase):
    @mock.patch('apps.video_generation.tasks.rendering.render_video', return_value=fake_render_result())
    @mock.patch('apps.video_generation.tasks.get_video_provider', return_value=FakeVideoProvider())
    @mock.patch('apps.video_generation.tasks.get_voice_provider', return_value=FakeVoiceProvider())
    @mock.patch('apps.video_generation.tasks.get_image_provider', return_value=FakeImageProvider())
    @mock.patch('apps.video_generation.tasks.get_text_provider', return_value=FakeTextProvider())
    def test_music_on_with_an_empty_library_uses_the_built_in_bed(self, _t, _i, _v, _m, mock_render):
        response = self.create_request(music_enabled=True)
        request_obj = VideoGenerationRequest.objects.get(pk=response.data['id'])
        self.assertEqual(request_obj.status, VideoGenerationRequest.Status.SUCCEEDED)
        self.assertTrue(mock_render.call_args.kwargs['builtin_music'])
        self.assertEqual(request_obj.usage['music_track'], 'Built-in ambient bed')

    @mock.patch('apps.video_generation.tasks.rendering.render_video', return_value=fake_render_result())
    @mock.patch('apps.video_generation.tasks.get_video_provider', return_value=FakeVideoProvider())
    @mock.patch('apps.video_generation.tasks.get_voice_provider', return_value=FakeVoiceProvider())
    @mock.patch('apps.video_generation.tasks.get_image_provider', return_value=FakeImageProvider())
    @mock.patch('apps.video_generation.tasks.get_text_provider', return_value=FakeTextProvider())
    def test_music_off_stays_silent(self, _t, _i, _v, _m, mock_render):
        response = self.create_request(music_enabled=False)
        request_obj = VideoGenerationRequest.objects.get(pk=response.data['id'])
        self.assertFalse(mock_render.call_args.kwargs['builtin_music'])
        self.assertIsNone(request_obj.usage['music_track'])


class ScenePictureShapeTests(SimpleTestCase):
    def test_a_provider_that_can_draw_any_shape_is_asked_for_a_vertical_picture(self):
        calls = []

        class Shaped:
            def generate_image(self, *, prompt, reference_images=None, aspect=None):
                calls.append(aspect)
                return b'img', 'image/png'

        _scene_image(Shaped(), 'p', '9:16')
        _scene_image(Shaped(), 'p', '16:9')
        self.assertAlmostEqual(calls[0], 16 / 9)
        self.assertAlmostEqual(calls[1], 9 / 16)

    def test_a_provider_without_an_aspect_option_is_called_as_before(self):
        class Plain:
            def generate_image(self, *, prompt):
                return b'img', 'image/png'

        self.assertEqual(_scene_image(Plain(), 'p', '9:16'), (b'img', 'image/png'))

    def test_the_prompt_keeps_the_subject_inside_a_vertical_crop(self):
        company = SimpleNamespace(name='Shaahi Creations')
        text = prompts.build_scene_image_prompt(company, None, 'instagram_reel', 'A mandap at dusk', aspect_ratio='9:16')
        self.assertIn('central vertical third', text)
        self.assertIn('Sharp focus', text)


@mock.patch.dict(os.environ, {'AGNES_API_KEY': 'test-key'})
class AgnesServerErrorTests(SimpleTestCase):
    def test_a_server_error_on_the_inline_picture_retries_as_text_to_video(self):
        bodies = []
        request = httpx.Request('POST', 'https://apihub.agnes-ai.com/v1/videos')

        def fake_post(url, **kwargs):
            bodies.append(dict(kwargs['json']))
            if 'image' in kwargs['json']:
                return httpx.Response(500, json={'error': 'internal'}, request=request)
            return httpx.Response(200, json={'video_id': 'video_1', 'status': 'completed', 'url': 'https://c/v.mp4'}, request=request)

        with mock.patch('httpx.post', fake_post), \
                mock.patch('httpx.get', lambda url, **kw: httpx.Response(200, content=b'V', request=request)):
            clip, _mime = AgnesVideoProvider().generate_video_clip(image_bytes=b'x', mime_type='image/png', prompt='p')
        self.assertEqual(clip, b'V')
        self.assertEqual(['image' in body for body in bodies], [True, False])


class SharperRenderTests(SimpleTestCase):
    """A real (tiny) FFmpeg render - skipped where FFmpeg isn't installed."""

    def setUp(self):
        if not rendering.find_ffmpeg():
            self.skipTest('FFmpeg is not installed')

    def test_music_is_mixed_into_the_video_and_the_zoom_is_centred(self):
        buffer = io.BytesIO()
        picture = Image.new('RGB', (512, 512), (240, 240, 240))
        picture.paste(Image.new('RGB', (64, 64), (200, 20, 20)), (224, 224))  # a red subject in the centre
        picture.save(buffer, format='JPEG')
        with tempfile.TemporaryDirectory() as folder:
            image_path = os.path.join(folder, 'scene.jpg')
            with open(image_path, 'wb') as f:
                f.write(buffer.getvalue())
            scene = SimpleNamespace(
                scene_number=1, duration_seconds=1.5, video_clip=None, voice_over_audio=None,
                image=SimpleNamespace(path=image_path, name='scene.jpg'),
            )
            video, _thumb, _duration, resolution = rendering.render_video(
                scenes=[scene], aspect_ratio='9:16', builtin_music=True, music_seed=1,
            )
            self.assertEqual(resolution, '1080x1920')
            out = os.path.join(folder, 'out.mp4')
            with open(out, 'wb') as f:
                f.write(video)
            # Decode the audio track: it must carry the music bed, not silence.
            import subprocess

            pcm = subprocess.run(
                [rendering.find_ffmpeg(), '-v', 'error', '-i', out, '-f', 's16le', '-ac', '1', '-ar', '8000', '-'],
                capture_output=True, check=True,
            ).stdout
            peak = max(abs(int.from_bytes(pcm[i:i + 2], 'little', signed=True)) for i in range(0, len(pcm) - 1, 2))
            self.assertGreater(peak, 500)
            # The last frame of the slow zoom still has the red subject in the middle of the frame.
            frame = subprocess.run(
                [rendering.find_ffmpeg(), '-v', 'error', '-sseof', '-0.2', '-i', out, '-frames:v', '1',
                 '-f', 'image2pipe', '-vcodec', 'png', '-'],
                capture_output=True, check=True,
            ).stdout
            last = Image.open(io.BytesIO(frame)).convert('RGB')
            red, green, blue = last.getpixel((540, 960))
            self.assertGreater(red, 150)
            self.assertLess(green, 90)
