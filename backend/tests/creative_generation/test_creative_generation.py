import datetime
import io
from unittest.mock import patch

from django.test import override_settings
from django.urls import reverse
from PIL import Image
from rest_framework import status
from rest_framework.test import APITestCase

from apps.authentication.models import User
from apps.companies.models import ClientProfile, Company
from apps.content_calendar.models import ContentCalendarItem
from apps.creative_generation.image_client import AIProviderError, AIProviderNotConfigured
from apps.creative_generation.models import GenerationRequest, GenerationVariation
from config.celery import app as celery_app

COPY_RESULT = {
    'caption': 'Discover the difference.',
    'headline': 'New Season, New You',
    'description': 'A closer look at our latest collection.',
    'cta': 'Shop now',
    'hashtags': ['#newseason'],
    'keywords': ['seasonal', 'launch'],
}


def fake_png_bytes():
    buffer = io.BytesIO()
    Image.new('RGB', (100, 100), color='teal').save(buffer, format='PNG')
    return buffer.getvalue()


class FakeImageProvider:
    model = 'gemini-3.1-flash-image'

    def __init__(self, result=None, error=None):
        self.result = result or (fake_png_bytes(), 'image/png')
        self.error = error

    def generate_image(self, *, prompt, reference_images=None):
        if self.error:
            raise self.error
        return self.result


class FakeTextProvider:
    model = 'claude-opus-5'

    def __init__(self, result=None, error=None):
        self.result = result or COPY_RESULT
        self.error = error

    def generate_json(self, *, system, prompt, json_schema):
        if self.error:
            raise self.error
        return self.result


class BaseCreativeGenerationTestCase(APITestCase):
    """Forces Celery into eager (synchronous, in-process) mode for these tests.

    `override_settings` alone doesn't work here: `config/celery.py` snapshots
    Django settings into `app.conf` once at process startup via
    `config_from_object`, so changing CELERY_TASK_ALWAYS_EAGER via Django's
    setting-override mechanism never reaches the already-loaded Celery app.
    Mutating `app.conf` directly does.
    """

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
            content_type='Single image',
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
        url = reverse('creative_generation:request-list-create', kwargs={'company_id': self.company.pk})
        payload = {'creative_type': GenerationRequest.CreativeType.INSTAGRAM_POST, 'prompt_brief': 'Bright summer vibe'}
        payload.update(overrides)
        return self.client.post(url, payload, format='json')


class GenerationRequestCreateTests(BaseCreativeGenerationTestCase):
    @patch('apps.creative_generation.tasks.get_text_provider')
    @patch('apps.creative_generation.tasks.get_image_provider')
    def test_admin_can_generate_three_variations(self, mock_get_image, mock_get_text):
        mock_get_image.return_value = FakeImageProvider()
        mock_get_text.return_value = FakeTextProvider()

        response = self.create_request(content_calendar_item=self.calendar_item.pk)

        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        request_obj = GenerationRequest.objects.get(pk=response.data['id'])
        self.assertEqual(request_obj.status, GenerationRequest.Status.SUCCEEDED)
        self.assertEqual(request_obj.variations.count(), 3)
        self.assertEqual(request_obj.created_by, self.admin)
        self.assertEqual(list(request_obj.variations.values_list('caption', flat=True)), [COPY_RESULT['caption']] * 3)

        self.calendar_item.refresh_from_db()
        self.assertEqual(self.calendar_item.status, ContentCalendarItem.Status.PENDING_APPROVAL)

    @override_settings(AI_IMAGE_COST_PER_IMAGE_USD='0.05')
    @patch('apps.creative_generation.tasks.get_text_provider')
    @patch('apps.creative_generation.tasks.get_image_provider')
    def test_cost_tracking_when_price_configured(self, mock_get_image, mock_get_text):
        mock_get_image.return_value = FakeImageProvider()
        mock_get_text.return_value = FakeTextProvider()

        response = self.create_request()
        request_obj = GenerationRequest.objects.get(pk=response.data['id'])
        self.assertEqual(str(request_obj.cost_usd), '0.1500')
        self.assertEqual(request_obj.usage['images_generated'], 3)

    @patch('apps.creative_generation.tasks.get_text_provider')
    @patch('apps.creative_generation.tasks.get_image_provider')
    def test_image_provider_not_configured_marks_request_failed(self, mock_get_image, mock_get_text):
        mock_get_image.return_value = FakeImageProvider(error=AIProviderNotConfigured('Gemini API credentials are not configured.'))
        mock_get_text.return_value = FakeTextProvider()

        response = self.create_request()
        request_obj = GenerationRequest.objects.get(pk=response.data['id'])
        self.assertEqual(request_obj.status, GenerationRequest.Status.FAILED)
        self.assertIn('not configured', request_obj.error_message)
        self.assertEqual(request_obj.variations.count(), 0)

    @patch('apps.creative_generation.tasks.get_text_provider')
    @patch('apps.creative_generation.tasks.get_image_provider')
    def test_text_provider_failure_marks_request_failed(self, mock_get_image, mock_get_text):
        mock_get_image.return_value = FakeImageProvider()
        mock_get_text.return_value = FakeTextProvider(error=AIProviderError('rate limited'))

        response = self.create_request()
        request_obj = GenerationRequest.objects.get(pk=response.data['id'])
        self.assertEqual(request_obj.status, GenerationRequest.Status.FAILED)

        self.calendar_item.refresh_from_db()
        # No calendar item was linked in this request, so its status should be untouched.
        self.assertEqual(self.calendar_item.status, ContentCalendarItem.Status.DRAFT)

    def test_client_cannot_create(self):
        self.authenticate_as('acmeclient@example.com', 'StrongPass123!')
        url = reverse('creative_generation:request-list-create', kwargs={'company_id': self.company.pk})
        response = self.client.post(url, {'creative_type': 'instagram_post'})
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_client_can_list_and_retrieve_their_own_companys_requests(self):
        created = self.create_request()
        request_id = created.data['id']

        self.authenticate_as('acmeclient@example.com', 'StrongPass123!')
        list_url = reverse('creative_generation:request-list-create', kwargs={'company_id': self.company.pk})
        self.assertEqual(self.client.get(list_url).status_code, status.HTTP_200_OK)

        detail_url = reverse(
            'creative_generation:request-detail', kwargs={'company_id': self.company.pk, 'pk': request_id},
        )
        self.assertEqual(self.client.get(detail_url).status_code, status.HTTP_200_OK)

    def test_client_from_another_company_cannot_list(self):
        other_client = User.objects.create_user(
            email='otherclient@example.com', password='StrongPass123!', role=User.Role.CLIENT,
        )
        ClientProfile.objects.create(user=other_client, company=self.other_company)
        self.authenticate_as('otherclient@example.com', 'StrongPass123!')

        url = reverse('creative_generation:request-list-create', kwargs={'company_id': self.company.pk})
        self.assertEqual(self.client.get(url).status_code, status.HTTP_404_NOT_FOUND)

    @patch('apps.creative_generation.tasks.get_text_provider')
    @patch('apps.creative_generation.tasks.get_image_provider')
    def test_adhoc_generation_is_linked_to_an_auto_created_calendar_item(self, mock_get_image, mock_get_text):
        mock_get_image.return_value = FakeImageProvider()
        mock_get_text.return_value = FakeTextProvider()

        response = self.create_request(prompt_brief='Diwali sale banner')

        request_obj = GenerationRequest.objects.get(pk=response.data['id'])
        self.assertIsNotNone(request_obj.content_calendar_item_id)
        linked_item = request_obj.content_calendar_item
        self.assertEqual(linked_item.source, ContentCalendarItem.Source.AD_HOC)
        self.assertEqual(linked_item.status, ContentCalendarItem.Status.PENDING_APPROVAL)
        self.assertEqual(linked_item.topic, 'Diwali sale banner')

        # And it's now visible to the client the normal, tested way (Epic 09).
        self.authenticate_as('acmeclient@example.com', 'StrongPass123!')
        list_url = reverse('content_calendar:item-list-create', kwargs={'company_id': self.company.pk})
        list_response = self.client.get(list_url, {'status': 'pending_approval'})
        self.assertEqual(list_response.status_code, status.HTTP_200_OK)
        self.assertIn(linked_item.id, [row['id'] for row in list_response.data['results']])

    def test_rejects_calendar_item_from_other_company(self):
        other_item = ContentCalendarItem.objects.create(
            company=self.other_company, topic='X', content_type='Single image',
            platforms=[ContentCalendarItem.Platform.INSTAGRAM], scheduled_date=datetime.date(2026, 6, 1),
        )
        response = self.create_request(content_calendar_item=other_item.pk)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class RetryTests(BaseCreativeGenerationTestCase):
    @patch('apps.creative_generation.tasks.get_text_provider')
    @patch('apps.creative_generation.tasks.get_image_provider')
    def test_can_only_retry_failed_requests(self, mock_get_image, mock_get_text):
        mock_get_image.return_value = FakeImageProvider()
        mock_get_text.return_value = FakeTextProvider()

        response = self.create_request()
        request_id = response.data['id']  # succeeded

        retry_url = reverse('creative_generation:request-retry', kwargs={'company_id': self.company.pk, 'pk': request_id})
        retry_response = self.client.post(retry_url)
        self.assertEqual(retry_response.status_code, status.HTTP_400_BAD_REQUEST)

    @patch('apps.creative_generation.tasks.get_text_provider')
    @patch('apps.creative_generation.tasks.get_image_provider')
    def test_retry_regenerates_a_failed_request(self, mock_get_image, mock_get_text):
        mock_get_image.return_value = FakeImageProvider(error=AIProviderError('boom'))
        mock_get_text.return_value = FakeTextProvider()

        response = self.create_request()
        request_id = response.data['id']
        request_obj = GenerationRequest.objects.get(pk=request_id)
        self.assertEqual(request_obj.status, GenerationRequest.Status.FAILED)

        mock_get_image.return_value = FakeImageProvider()
        retry_url = reverse('creative_generation:request-retry', kwargs={'company_id': self.company.pk, 'pk': request_id})
        retry_response = self.client.post(retry_url)

        self.assertEqual(retry_response.status_code, status.HTTP_200_OK)
        request_obj.refresh_from_db()
        self.assertEqual(request_obj.status, GenerationRequest.Status.SUCCEEDED)
        self.assertEqual(request_obj.retry_count, 1)
        self.assertEqual(request_obj.variations.count(), 3)


class VariationSelectTests(BaseCreativeGenerationTestCase):
    @patch('apps.creative_generation.tasks.get_text_provider')
    @patch('apps.creative_generation.tasks.get_image_provider')
    def test_selecting_a_variation_unselects_others(self, mock_get_image, mock_get_text):
        mock_get_image.return_value = FakeImageProvider()
        mock_get_text.return_value = FakeTextProvider()

        response = self.create_request()
        request_id = response.data['id']
        variations = list(GenerationVariation.objects.filter(generation_request_id=request_id).order_by('variation_number'))

        select_url = reverse('creative_generation:variation-select', kwargs={
            'company_id': self.company.pk, 'pk': request_id, 'variation_id': variations[1].pk,
        })
        select_response = self.client.post(select_url)
        self.assertEqual(select_response.status_code, status.HTTP_200_OK)

        variations[0].refresh_from_db()
        variations[1].refresh_from_db()
        variations[2].refresh_from_db()
        self.assertFalse(variations[0].is_selected)
        self.assertTrue(variations[1].is_selected)
        self.assertFalse(variations[2].is_selected)

        # Selecting a different one flips the selection.
        select_url_0 = reverse('creative_generation:variation-select', kwargs={
            'company_id': self.company.pk, 'pk': request_id, 'variation_id': variations[0].pk,
        })
        self.client.post(select_url_0)
        variations[0].refresh_from_db()
        variations[1].refresh_from_db()
        self.assertTrue(variations[0].is_selected)
        self.assertFalse(variations[1].is_selected)

    @patch('apps.creative_generation.tasks.get_text_provider')
    @patch('apps.creative_generation.tasks.get_image_provider')
    def test_client_can_select_their_own_companys_variation(self, mock_get_image, mock_get_text):
        mock_get_image.return_value = FakeImageProvider()
        mock_get_text.return_value = FakeTextProvider()

        response = self.create_request()
        request_id = response.data['id']
        variation = GenerationVariation.objects.filter(generation_request_id=request_id).order_by('variation_number').first()

        self.authenticate_as('acmeclient@example.com', 'StrongPass123!')
        select_url = reverse('creative_generation:variation-select', kwargs={
            'company_id': self.company.pk, 'pk': request_id, 'variation_id': variation.pk,
        })
        select_response = self.client.post(select_url)

        self.assertEqual(select_response.status_code, status.HTTP_200_OK)
        variation.refresh_from_db()
        self.assertTrue(variation.is_selected)

    @patch('apps.creative_generation.tasks.get_text_provider')
    @patch('apps.creative_generation.tasks.get_image_provider')
    def test_client_from_another_company_cannot_select_variation(self, mock_get_image, mock_get_text):
        mock_get_image.return_value = FakeImageProvider()
        mock_get_text.return_value = FakeTextProvider()

        response = self.create_request()
        request_id = response.data['id']
        variation = GenerationVariation.objects.filter(generation_request_id=request_id).order_by('variation_number').first()

        other_client = User.objects.create_user(
            email='otherclient2@example.com', password='StrongPass123!', role=User.Role.CLIENT,
        )
        ClientProfile.objects.create(user=other_client, company=self.other_company)
        self.authenticate_as('otherclient2@example.com', 'StrongPass123!')

        select_url = reverse('creative_generation:variation-select', kwargs={
            'company_id': self.company.pk, 'pk': request_id, 'variation_id': variation.pk,
        })
        self.assertEqual(self.client.post(select_url).status_code, status.HTTP_404_NOT_FOUND)
