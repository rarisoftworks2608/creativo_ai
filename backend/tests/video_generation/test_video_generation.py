import datetime
from unittest.mock import patch

from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.authentication.models import User
from apps.companies.models import ClientProfile, Company
from apps.content_calendar.models import ContentCalendarItem
from apps.video_generation import rendering, subtitles
from apps.video_generation.models import VideoGenerationRequest
from apps.video_generation.voice_client import AIProviderError, AIProviderNotConfigured
from config.celery import app as celery_app

SCRIPT_RESULT = {
    'scenes': [
        {'narration': 'Meet the new collection.', 'visual_description': 'Product hero shot.', 'duration_seconds': 4},
        {'narration': 'Built for everyday life.', 'visual_description': 'Lifestyle shot.', 'duration_seconds': 4},
        {'narration': 'Shop it today.', 'visual_description': 'Logo end card.', 'duration_seconds': 3},
    ],
}


def fake_png_bytes():
    return b'\x89PNG\r\n\x1a\n' + b'0' * 32


def fake_mp3_bytes():
    return b'ID3' + b'0' * 32


class FakeTextProvider:
    model = 'claude-opus-5'

    def __init__(self, result=None, error=None):
        self.result = result if result is not None else SCRIPT_RESULT
        self.error = error

    def generate_json(self, *, system, prompt, json_schema):
        if self.error:
            raise self.error
        return self.result


class FakeImageProvider:
    model = 'gemini-3.1-flash-image'

    def __init__(self, result=None, error=None):
        self.result = result or (fake_png_bytes(), 'image/png')
        self.error = error

    def generate_image(self, *, prompt, reference_images=None):
        if self.error:
            raise self.error
        return self.result


class FakeVoiceProvider:
    def __init__(self, result=None, error=None):
        self.result = result or (fake_mp3_bytes(), 'audio/mpeg')
        self.error = error

    def synthesize_speech(self, *, text, voice=''):
        if self.error:
            raise self.error
        return self.result


def fake_render_result():
    return (b'FAKE_MP4_BYTES', b'FAKE_THUMBNAIL_BYTES', 11.0, '1080x1920')


class BaseVideoGenerationTestCase(APITestCase):
    """Forces Celery into eager (synchronous) mode - see the identical setup in
    tests/creative_generation/test_creative_generation.py for why `override_settings`
    alone doesn't work here (config/celery.py snapshots settings once at import)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._original_eager = celery_app.conf.task_always_eager
        cls._original_propagates = celery_app.conf.task_eager_propagates
        celery_app.conf.task_always_eager = True
        celery_app.conf.task_eager_propagates = True

    @classmethod
    def tearDownClass(cls):
        celery_app.conf.task_always_eager = cls._original_eager
        celery_app.conf.task_eager_propagates = cls._original_propagates
        super().tearDownClass()

    def setUp(self):
        self.admin = User.objects.create_superuser(email='admin@example.com', password='StrongPass123!')
        self.company = Company.objects.create(name='Acme Retail', created_by=self.admin)
        self.other_company = Company.objects.create(name='Other Co', created_by=self.admin)
        self.company_user = User.objects.create_user(
            email='acmeclient@example.com', password='StrongPass123!', role=User.Role.CLIENT,
        )
        ClientProfile.objects.create(user=self.company_user, company=self.company, is_primary_contact=True)

        self.calendar_item = ContentCalendarItem.objects.create(
            company=self.company,
            topic='Summer Launch',
            content_type='Reel',
            platforms=[ContentCalendarItem.Platform.INSTAGRAM],
            scheduled_date=datetime.date(2026, 6, 1),
        )

    def authenticate_as(self, email, password):
        response = self.client.post(reverse('authentication:login'), {'email': email, 'password': password})
        access = response.data['access']
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {access}')
        return response

    def create_request(self, **overrides):
        self.authenticate_as('admin@example.com', 'StrongPass123!')
        url = reverse('video_generation:request-list-create', kwargs={'company_id': self.company.pk})
        payload = {'video_type': VideoGenerationRequest.VideoType.INSTAGRAM_REEL, 'prompt_brief': 'Bright summer vibe'}
        payload.update(overrides)
        return self.client.post(url, payload, format='json')


class VideoGenerationCreateTests(BaseVideoGenerationTestCase):
    @patch('apps.video_generation.tasks.rendering.render_video', return_value=fake_render_result())
    @patch('apps.video_generation.tasks.get_voice_provider', return_value=FakeVoiceProvider())
    @patch('apps.video_generation.tasks.get_image_provider', return_value=FakeImageProvider())
    @patch('apps.video_generation.tasks.get_text_provider', return_value=FakeTextProvider())
    def test_admin_can_generate_a_video(self, mock_text, mock_image, mock_voice, mock_render):
        response = self.create_request(content_calendar_item=self.calendar_item.pk)

        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        request_obj = VideoGenerationRequest.objects.get(pk=response.data['id'])
        self.assertEqual(request_obj.status, VideoGenerationRequest.Status.SUCCEEDED)
        self.assertEqual(request_obj.created_by, self.admin)
        self.assertEqual(request_obj.scenes.count(), 3)
        self.assertTrue(request_obj.video_file)
        self.assertTrue(request_obj.thumbnail)
        self.assertEqual(request_obj.resolution, '1080x1920')
        self.assertEqual(request_obj.duration_seconds, 11.0)
        self.assertTrue(request_obj.subtitles_srt)
        self.assertTrue(all(scene.voice_over_audio for scene in request_obj.scenes.all()))

        self.calendar_item.refresh_from_db()
        self.assertEqual(self.calendar_item.status, ContentCalendarItem.Status.GENERATED)

    @patch('apps.video_generation.tasks.rendering.render_video', return_value=fake_render_result())
    @patch('apps.video_generation.tasks.get_voice_provider')
    @patch('apps.video_generation.tasks.get_image_provider', return_value=FakeImageProvider())
    @patch('apps.video_generation.tasks.get_text_provider', return_value=FakeTextProvider())
    def test_voice_over_disabled_skips_voice_generation(self, mock_text, mock_image, mock_voice, mock_render):
        response = self.create_request(voice_over_enabled=False)

        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        mock_voice.assert_not_called()
        request_obj = VideoGenerationRequest.objects.get(pk=response.data['id'])
        self.assertEqual(request_obj.status, VideoGenerationRequest.Status.SUCCEEDED)
        self.assertFalse(any(scene.voice_over_audio for scene in request_obj.scenes.all()))

    @patch('apps.video_generation.tasks.get_text_provider')
    def test_script_provider_not_configured_marks_failed(self, mock_text):
        mock_text.return_value = FakeTextProvider(error=AIProviderNotConfigured('Anthropic API key is missing.'))

        response = self.create_request()
        request_obj = VideoGenerationRequest.objects.get(pk=response.data['id'])
        self.assertEqual(request_obj.status, VideoGenerationRequest.Status.FAILED)
        self.assertIn('missing', request_obj.error_message)
        self.assertEqual(request_obj.scenes.count(), 0)

    @patch('apps.video_generation.tasks.get_voice_provider', return_value=FakeVoiceProvider())
    @patch('apps.video_generation.tasks.get_image_provider')
    @patch('apps.video_generation.tasks.get_text_provider', return_value=FakeTextProvider())
    def test_image_provider_failure_marks_failed(self, mock_text, mock_image, mock_voice):
        mock_image.return_value = FakeImageProvider(error=AIProviderError('boom'))

        response = self.create_request(content_calendar_item=self.calendar_item.pk)
        request_obj = VideoGenerationRequest.objects.get(pk=response.data['id'])
        self.assertEqual(request_obj.status, VideoGenerationRequest.Status.FAILED)
        self.assertIn('scene 1', request_obj.error_message)

        self.calendar_item.refresh_from_db()
        self.assertEqual(self.calendar_item.status, ContentCalendarItem.Status.FAILED)

    @patch('apps.video_generation.tasks.get_voice_provider')
    @patch('apps.video_generation.tasks.get_image_provider', return_value=FakeImageProvider())
    @patch('apps.video_generation.tasks.get_text_provider', return_value=FakeTextProvider())
    def test_voice_provider_failure_marks_failed(self, mock_text, mock_image, mock_voice):
        mock_voice.return_value = FakeVoiceProvider(error=AIProviderError('tts down'))

        response = self.create_request()
        request_obj = VideoGenerationRequest.objects.get(pk=response.data['id'])
        self.assertEqual(request_obj.status, VideoGenerationRequest.Status.FAILED)
        self.assertIn('Voice-over', request_obj.error_message)

    @patch('apps.video_generation.tasks.get_voice_provider', return_value=FakeVoiceProvider())
    @patch('apps.video_generation.tasks.get_image_provider', return_value=FakeImageProvider())
    @patch('apps.video_generation.tasks.get_text_provider', return_value=FakeTextProvider())
    def test_rendering_failure_marks_failed(self, mock_text, mock_image, mock_voice):
        with patch('apps.video_generation.tasks.rendering.render_video', side_effect=AIProviderError('ffmpeg exploded')):
            response = self.create_request()
        request_obj = VideoGenerationRequest.objects.get(pk=response.data['id'])
        self.assertEqual(request_obj.status, VideoGenerationRequest.Status.FAILED)
        self.assertIn('ffmpeg exploded', request_obj.error_message)

    def test_client_cannot_create(self):
        self.authenticate_as('acmeclient@example.com', 'StrongPass123!')
        url = reverse('video_generation:request-list-create', kwargs={'company_id': self.company.pk})
        response = self.client.post(url, {'video_type': 'instagram_reel'})
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_rejects_calendar_item_from_other_company(self):
        other_item = ContentCalendarItem.objects.create(
            company=self.other_company, topic='X', content_type='Reel',
            platforms=[ContentCalendarItem.Platform.INSTAGRAM], scheduled_date=datetime.date(2026, 6, 1),
        )
        response = self.create_request(content_calendar_item=other_item.pk)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_target_duration_must_be_reasonable(self):
        response = self.create_request(target_duration_seconds=1)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        response = self.create_request(target_duration_seconds=999)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class RetryTests(BaseVideoGenerationTestCase):
    @patch('apps.video_generation.tasks.rendering.render_video', return_value=fake_render_result())
    @patch('apps.video_generation.tasks.get_voice_provider', return_value=FakeVoiceProvider())
    @patch('apps.video_generation.tasks.get_image_provider', return_value=FakeImageProvider())
    @patch('apps.video_generation.tasks.get_text_provider', return_value=FakeTextProvider())
    def test_can_only_retry_failed_requests(self, mock_text, mock_image, mock_voice, mock_render):
        response = self.create_request()
        request_id = response.data['id']  # succeeded

        retry_url = reverse('video_generation:request-retry', kwargs={'company_id': self.company.pk, 'pk': request_id})
        retry_response = self.client.post(retry_url)
        self.assertEqual(retry_response.status_code, status.HTTP_400_BAD_REQUEST)

    @patch('apps.video_generation.tasks.get_voice_provider', return_value=FakeVoiceProvider())
    @patch('apps.video_generation.tasks.get_image_provider', return_value=FakeImageProvider())
    @patch('apps.video_generation.tasks.get_text_provider', return_value=FakeTextProvider())
    def test_retry_regenerates_a_failed_request(self, mock_text, mock_image, mock_voice):
        with patch('apps.video_generation.tasks.rendering.render_video', side_effect=AIProviderError('boom')):
            response = self.create_request()
        request_id = response.data['id']
        request_obj = VideoGenerationRequest.objects.get(pk=request_id)
        self.assertEqual(request_obj.status, VideoGenerationRequest.Status.FAILED)

        retry_url = reverse('video_generation:request-retry', kwargs={'company_id': self.company.pk, 'pk': request_id})
        with patch('apps.video_generation.tasks.rendering.render_video', return_value=fake_render_result()):
            retry_response = self.client.post(retry_url)

        self.assertEqual(retry_response.status_code, status.HTTP_200_OK)
        request_obj.refresh_from_db()
        self.assertEqual(request_obj.status, VideoGenerationRequest.Status.SUCCEEDED)
        self.assertEqual(request_obj.retry_count, 1)
        self.assertEqual(request_obj.scenes.count(), 3)


class SubtitlesTests(APITestCase):
    """Pure-local logic, no mocking needed."""

    def test_build_srt_produces_sequential_timestamped_blocks(self):
        class FakeScene:
            def __init__(self, narration, duration_seconds):
                self.narration = narration
                self.duration_seconds = duration_seconds

        scenes = [FakeScene('Hello there.', 2.0), FakeScene('', 1.5), FakeScene('Second line.', 3.0)]
        srt = subtitles.build_srt(scenes)

        self.assertIn('1\n00:00:00,000 --> 00:00:02,000\nHello there.', srt)
        # The blank-narration scene is skipped but still advances the timeline,
        # so the next subtitle starts after both scene 1 and scene 2's durations.
        self.assertIn('2\n00:00:03,500 --> 00:00:06,500\nSecond line.', srt)


class FFmpegAvailabilityTests(BaseVideoGenerationTestCase):
    """Real (unmocked) checks against this environment, which genuinely has no
    ffmpeg binary installed - confirms the "fail clearly, don't crash" contract."""

    def test_check_ffmpeg_available_raises_when_missing(self):
        with self.assertRaises(rendering.FFmpegNotAvailable):
            rendering.check_ffmpeg_available()

    @patch('apps.video_generation.tasks.get_voice_provider', return_value=FakeVoiceProvider())
    @patch('apps.video_generation.tasks.get_image_provider', return_value=FakeImageProvider())
    @patch('apps.video_generation.tasks.get_text_provider', return_value=FakeTextProvider())
    def test_full_pipeline_fails_clearly_without_ffmpeg(self, mock_text, mock_image, mock_voice):
        """End-to-end through script/visuals/voice-over for real, hitting the real
        (missing) ffmpeg only at the render stage - everything up to there is genuine."""
        response = self.create_request()

        request_obj = VideoGenerationRequest.objects.get(pk=response.data['id'])
        self.assertEqual(request_obj.status, VideoGenerationRequest.Status.FAILED)
        self.assertIn('FFmpeg is not installed', request_obj.error_message)
        self.assertEqual(request_obj.scenes.count(), 3)
        self.assertTrue(all(scene.image for scene in request_obj.scenes.all()))
