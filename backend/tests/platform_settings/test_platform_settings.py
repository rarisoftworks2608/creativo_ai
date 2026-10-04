from django.test import TestCase, override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.authentication.models import User
from apps.companies.models import ClientProfile, Company
from apps.platform_settings.models import PlatformSettings
from apps.platform_settings.services import check_daily_generation_limit
from common.ai_config import get_model_name, get_provider_name


class PlatformSettingsModelTests(TestCase):
    def test_load_creates_singleton(self):
        settings_obj = PlatformSettings.load()
        self.assertEqual(settings_obj.pk, 1)
        self.assertEqual(PlatformSettings.objects.count(), 1)

    @override_settings(SEND_NOTIFICATION_EMAILS=True)
    def test_load_seeds_email_toggle_from_env_setting_on_first_creation(self):
        self.assertTrue(PlatformSettings.load().send_notification_emails)

    @override_settings(SEND_NOTIFICATION_EMAILS=False)
    def test_load_seeds_email_toggle_off_when_env_setting_is_off(self):
        self.assertFalse(PlatformSettings.load().send_notification_emails)

    def test_load_returns_same_row_on_repeat_calls(self):
        first = PlatformSettings.load()
        first.max_upload_size_mb = 25
        first.save()
        second = PlatformSettings.load()
        self.assertEqual(second.max_upload_size_mb, 25)
        self.assertEqual(PlatformSettings.objects.count(), 1)


class PlatformSettingsApiTests(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(email='admin@example.com', password='StrongPass123!')
        self.company = Company.objects.create(name='Acme Retail', created_by=self.admin)
        self.client_user = User.objects.create_user(
            email='client@example.com', password='StrongPass123!', role=User.Role.CLIENT,
        )
        ClientProfile.objects.create(user=self.client_user, company=self.company)

    def authenticate_as(self, email, password):
        response = self.client.post(reverse('authentication:login'), {'email': email, 'password': password})
        access = response.data['access']
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {access}')

    def test_client_cannot_view_platform_settings(self):
        self.authenticate_as('client@example.com', 'StrongPass123!')
        response = self.client.get(reverse('platform_settings:detail'))
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_admin_can_view_and_update_settings(self):
        self.authenticate_as('admin@example.com', 'StrongPass123!')
        response = self.client.get(reverse('platform_settings:detail'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('environment', response.data)

        response = self.client.patch(
            reverse('platform_settings:detail'), {'daily_generation_limit_per_company': 5},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['daily_generation_limit_per_company'], 5)
        self.assertEqual(PlatformSettings.load().updated_by, self.admin)

    def test_rejects_variation_count_out_of_range(self):
        self.authenticate_as('admin@example.com', 'StrongPass123!')
        response = self.client.patch(reverse('platform_settings:detail'), {'max_variation_count': 5})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_rejects_default_exceeding_max(self):
        self.authenticate_as('admin@example.com', 'StrongPass123!')
        response = self.client.patch(
            reverse('platform_settings:detail'), {'default_variation_count': 3, 'max_variation_count': 2},
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class DailyGenerationLimitTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(email='admin2@example.com', password='StrongPass123!')
        self.company = Company.objects.create(name='Acme Retail', created_by=self.admin)

    def test_no_limit_by_default(self):
        # 0 = unlimited, should never raise regardless of existing request count.
        check_daily_generation_limit(self.company)

    def test_raises_once_limit_reached(self):
        from apps.creative_generation.models import GenerationRequest
        from rest_framework.exceptions import Throttled

        settings_obj = PlatformSettings.load()
        settings_obj.daily_generation_limit_per_company = 1
        settings_obj.save()

        GenerationRequest.objects.create(company=self.company, creative_type=GenerationRequest.CreativeType.POST)

        with self.assertRaises(Throttled):
            check_daily_generation_limit(self.company)

    def test_other_companies_do_not_count_toward_this_companys_limit(self):
        from apps.creative_generation.models import GenerationRequest

        other_company = Company.objects.create(name='Other Co', created_by=self.admin)
        settings_obj = PlatformSettings.load()
        settings_obj.daily_generation_limit_per_company = 1
        settings_obj.save()

        GenerationRequest.objects.create(company=other_company, creative_type=GenerationRequest.CreativeType.POST)

        check_daily_generation_limit(self.company)


class AIProviderResolutionTests(TestCase):
    """Admin Settings overrides vs .env values for the AI provider/model (common/ai_config.py)."""

    def _override(self, **fields):
        settings_obj = PlatformSettings.load()
        for name, value in fields.items():
            setattr(settings_obj, name, value)
        settings_obj.save()

    @override_settings(AI_IMAGE_PROVIDER='cloudflare', AI_IMAGE_MODEL='@cf/black-forest-labs/flux-1-schnell')
    def test_env_values_are_used_without_overrides(self):
        self.assertEqual(get_provider_name('image'), 'cloudflare')
        self.assertEqual(get_model_name('image'), '@cf/black-forest-labs/flux-1-schnell')

    @override_settings(AI_IMAGE_PROVIDER='cloudflare', AI_IMAGE_MODEL='@cf/black-forest-labs/flux-1-schnell')
    def test_provider_override_uses_that_providers_default_model(self):
        self._override(ai_image_provider='openai')

        self.assertEqual(get_provider_name('image'), 'openai')
        self.assertEqual(get_model_name('image'), 'gpt-image-1')

    @override_settings(AI_IMAGE_PROVIDER='cloudflare', AI_IMAGE_MODEL='@cf/black-forest-labs/flux-1-schnell')
    def test_model_override_wins(self):
        self._override(ai_image_provider='openai', ai_image_model='custom-image-model')

        self.assertEqual(get_model_name('image'), 'custom-image-model')

    @override_settings(AI_IMAGE_PROVIDER='openai', AI_IMAGE_MODEL='@cf/black-forest-labs/flux-1-schnell')
    def test_env_provider_switch_ignores_the_previous_providers_default_model(self):
        self.assertEqual(get_model_name('image'), 'gpt-image-1')

    @override_settings(AI_TEXT_PROVIDER='openai', AI_TEXT_MODEL='openai/gpt-oss-120b')
    def test_env_text_provider_switch_ignores_the_groq_default_model(self):
        self.assertEqual(get_model_name('text'), 'gpt-4.1-mini')

    @override_settings(AI_IMAGE_PROVIDER='cloudflare', AI_IMAGE_MODEL='@cf/stabilityai/stable-diffusion-xl-base-1.0')
    def test_custom_env_model_is_kept(self):
        self.assertEqual(get_model_name('image'), '@cf/stabilityai/stable-diffusion-xl-base-1.0')
