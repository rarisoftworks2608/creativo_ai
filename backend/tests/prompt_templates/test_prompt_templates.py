from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.authentication.models import User
from apps.companies.models import ClientProfile, Company
from apps.prompt_templates.models import PromptTemplate
from apps.prompt_templates.services import activate_version, create_new_version, deactivate_version, get_active_guidance


class PromptTemplateServicesTests(TestCase):
    def setUp(self):
        self.template = PromptTemplate.objects.create(
            slug='luxury-real-estate-image', category=PromptTemplate.Category.IMAGE,
            name='Luxury Real Estate', body='Emphasize marble and gold accents.',
        )

    def test_create_new_version_increments_and_keeps_old_version_untouched(self):
        v2 = create_new_version(self.template, body='Emphasize glass and steel instead.')

        self.assertEqual(v2.version, 2)
        self.assertEqual(v2.slug, self.template.slug)
        self.assertFalse(v2.is_active)
        self.template.refresh_from_db()
        self.assertEqual(self.template.body, 'Emphasize marble and gold accents.')

    def test_activate_deactivates_sibling_versions(self):
        v2 = create_new_version(self.template, body='v2 body')
        activate_version(self.template)
        activate_version(v2)

        self.template.refresh_from_db()
        v2.refresh_from_db()
        self.assertFalse(self.template.is_active)
        self.assertTrue(v2.is_active)

    def test_deactivate_turns_off_active_version(self):
        activate_version(self.template)
        deactivate_version(self.template)
        self.template.refresh_from_db()
        self.assertFalse(self.template.is_active)

    def test_get_active_guidance_returns_empty_when_nothing_active(self):
        self.assertEqual(get_active_guidance(PromptTemplate.Category.IMAGE), '')

    def test_get_active_guidance_prefers_most_specific_match(self):
        activate_version(self.template)  # category-wide, no platform/creative_type
        specific = PromptTemplate.objects.create(
            slug='luxury-real-estate-image-instagram', category=PromptTemplate.Category.IMAGE,
            platform='instagram', name='Instagram-specific', body='Square-friendly composition.',
        )
        activate_version(specific)

        general_match = get_active_guidance(PromptTemplate.Category.IMAGE, platform='facebook')
        specific_match = get_active_guidance(PromptTemplate.Category.IMAGE, platform='instagram')

        self.assertEqual(general_match, 'Emphasize marble and gold accents.')
        self.assertEqual(specific_match, 'Square-friendly composition.')

    def test_get_active_guidance_ignores_inactive_versions(self):
        create_new_version(self.template, body='not active')
        self.assertEqual(get_active_guidance(PromptTemplate.Category.IMAGE), '')


class PromptTemplateApiTests(APITestCase):
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

    def test_client_cannot_manage_prompt_templates(self):
        self.authenticate_as('client@example.com', 'StrongPass123!')
        response = self.client.get(reverse('prompt_templates:list-create'))
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_admin_can_create_a_template(self):
        self.authenticate_as('admin@example.com', 'StrongPass123!')
        payload = {
            'slug': 'festival-hashtags', 'category': PromptTemplate.Category.HASHTAG,
            'name': 'Festival Hashtags', 'body': 'Always include #FestiveSeason.',
        }
        response = self.client.post(reverse('prompt_templates:list-create'), payload)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['version'], 1)
        self.assertFalse(response.data['is_active'])

    def test_duplicate_slug_is_rejected(self):
        PromptTemplate.objects.create(
            slug='festival-hashtags', category=PromptTemplate.Category.HASHTAG,
            name='Festival Hashtags', body='v1',
        )
        self.authenticate_as('admin@example.com', 'StrongPass123!')
        response = self.client.post(reverse('prompt_templates:list-create'), {
            'slug': 'festival-hashtags', 'category': PromptTemplate.Category.HASHTAG,
            'name': 'Dup', 'body': 'dup',
        })
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_list_returns_only_latest_version_per_slug(self):
        v1 = PromptTemplate.objects.create(
            slug='campaign-diwali', category=PromptTemplate.Category.CAMPAIGN, name='Diwali', body='v1', version=1,
        )
        create_new_version(v1, body='v2')

        self.authenticate_as('admin@example.com', 'StrongPass123!')
        response = self.client.get(reverse('prompt_templates:list-create'))
        matching = [row for row in response.data['results'] if row['slug'] == 'campaign-diwali']
        self.assertEqual(len(matching), 1)
        self.assertEqual(matching[0]['version'], 2)

    def test_history_lists_every_version_newest_first(self):
        v1 = PromptTemplate.objects.create(
            slug='campaign-diwali', category=PromptTemplate.Category.CAMPAIGN, name='Diwali', body='v1', version=1,
        )
        create_new_version(v1, body='v2')

        self.authenticate_as('admin@example.com', 'StrongPass123!')
        response = self.client.get(reverse('prompt_templates:history', kwargs={'slug': 'campaign-diwali'}))
        self.assertEqual([row['version'] for row in response.data['results']], [2, 1])

    def test_new_version_endpoint(self):
        template = PromptTemplate.objects.create(
            slug='campaign-diwali', category=PromptTemplate.Category.CAMPAIGN, name='Diwali', body='v1', version=1,
        )
        self.authenticate_as('admin@example.com', 'StrongPass123!')
        response = self.client.post(
            reverse('prompt_templates:new-version', kwargs={'pk': template.pk}), {'body': 'v2 body'},
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['version'], 2)

    def test_activate_and_deactivate_endpoints(self):
        template = PromptTemplate.objects.create(
            slug='campaign-diwali', category=PromptTemplate.Category.CAMPAIGN, name='Diwali', body='v1',
        )
        self.authenticate_as('admin@example.com', 'StrongPass123!')

        response = self.client.post(reverse('prompt_templates:activate', kwargs={'pk': template.pk}))
        self.assertTrue(response.data['is_active'])

        response = self.client.post(reverse('prompt_templates:deactivate', kwargs={'pk': template.pk}))
        self.assertFalse(response.data['is_active'])

    def test_cannot_delete_an_active_version(self):
        template = PromptTemplate.objects.create(
            slug='campaign-diwali', category=PromptTemplate.Category.CAMPAIGN, name='Diwali', body='v1',
            is_active=True,
        )
        self.authenticate_as('admin@example.com', 'StrongPass123!')
        response = self.client.delete(reverse('prompt_templates:detail', kwargs={'pk': template.pk}))
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_can_delete_an_inactive_version(self):
        template = PromptTemplate.objects.create(
            slug='campaign-diwali', category=PromptTemplate.Category.CAMPAIGN, name='Diwali', body='v1',
        )
        self.authenticate_as('admin@example.com', 'StrongPass123!')
        response = self.client.delete(reverse('prompt_templates:detail', kwargs={'pk': template.pk}))
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
