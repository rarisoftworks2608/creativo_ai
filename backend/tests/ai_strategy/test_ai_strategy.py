from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.ai_strategy.ai_client import AIProviderError, AIProviderNotConfigured, AnthropicProvider
from apps.ai_strategy.models import BrandContext, StrategyOutput
from apps.authentication.models import User
from apps.companies.models import ClientProfile, Company

BRAND_CONTEXT_RESULT = {
    'business_analysis': 'A retail business selling premium widgets.',
    'brand_guidelines_analysis': 'Confident, warm tone; avoids discount language.',
    'products_services_analysis': 'Widget A and Widget B are flagship products.',
    'audience_analysis': 'Young professionals seeking quality over price.',
    'summary': 'Acme Retail is a premium widget brand for discerning young professionals.',
}

CONTENT_IDEAS_RESULT = {
    'items': [
        {
            'title': 'Behind the widget',
            'description': 'Show the making of Widget A.',
            'content_type': 'Reel',
            'rationale': 'Builds trust through transparency.',
        },
    ],
}


class FakeProvider:
    model = 'claude-opus-5'

    def __init__(self, result):
        self.result = result

    def generate_json(self, *, system, prompt, json_schema):
        return self.result


class BaseAiStrategyTestCase(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(email='admin@example.com', password='StrongPass123!')
        self.company = Company.objects.create(name='Acme Retail', created_by=self.admin)
        self.company_user = User.objects.create_user(
            email='acmeclient@example.com', password='StrongPass123!', role=User.Role.CLIENT,
        )
        ClientProfile.objects.create(user=self.company_user, company=self.company, is_primary_contact=True)

    def authenticate_as(self, email, password):
        response = self.client.post(reverse('authentication:login'), {'email': email, 'password': password})
        access = response.data['access']
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {access}')
        return response


class BrandContextTests(BaseAiStrategyTestCase):
    def test_view_404s_before_generation(self):
        self.authenticate_as('admin@example.com', 'StrongPass123!')
        url = reverse('ai_strategy:brand-context', kwargs={'company_id': self.company.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    @patch('apps.ai_strategy.views.get_provider')
    def test_admin_can_generate_brand_context(self, mock_get_provider):
        mock_get_provider.return_value = FakeProvider(BRAND_CONTEXT_RESULT)
        self.authenticate_as('admin@example.com', 'StrongPass123!')

        url = reverse('ai_strategy:brand-context-generate', kwargs={'company_id': self.company.pk})
        response = self.client.post(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['summary'], BRAND_CONTEXT_RESULT['summary'])
        self.assertEqual(response.data['model_used'], 'claude-opus-5')

        context = BrandContext.objects.get(company=self.company)
        self.assertEqual(context.generated_by, self.admin)

        get_url = reverse('ai_strategy:brand-context', kwargs={'company_id': self.company.pk})
        get_response = self.client.get(get_url)
        self.assertEqual(get_response.status_code, status.HTTP_200_OK)

    @patch('apps.ai_strategy.views.get_provider')
    def test_regenerating_overwrites_existing_context(self, mock_get_provider):
        mock_get_provider.return_value = FakeProvider(BRAND_CONTEXT_RESULT)
        self.authenticate_as('admin@example.com', 'StrongPass123!')
        url = reverse('ai_strategy:brand-context-generate', kwargs={'company_id': self.company.pk})

        self.client.post(url)
        self.assertEqual(BrandContext.objects.filter(company=self.company).count(), 1)

        mock_get_provider.return_value = FakeProvider({**BRAND_CONTEXT_RESULT, 'summary': 'Updated summary.'})
        self.client.post(url)

        self.assertEqual(BrandContext.objects.filter(company=self.company).count(), 1)
        self.assertEqual(BrandContext.objects.get(company=self.company).summary, 'Updated summary.')

    def test_client_cannot_generate_brand_context(self):
        self.authenticate_as('acmeclient@example.com', 'StrongPass123!')
        url = reverse('ai_strategy:brand-context-generate', kwargs={'company_id': self.company.pk})
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    @patch('apps.ai_strategy.views.get_provider')
    def test_provider_not_configured_returns_503(self, mock_get_provider):
        class BrokenProvider:
            model = 'claude-opus-5'

            def generate_json(self, **kwargs):
                raise AIProviderNotConfigured('Anthropic API credentials are not configured.')

        mock_get_provider.return_value = BrokenProvider()
        self.authenticate_as('admin@example.com', 'StrongPass123!')
        url = reverse('ai_strategy:brand-context-generate', kwargs={'company_id': self.company.pk})
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)

    @patch('apps.ai_strategy.views.get_provider')
    def test_generic_provider_error_returns_502(self, mock_get_provider):
        class BrokenProvider:
            model = 'claude-opus-5'

            def generate_json(self, **kwargs):
                raise AIProviderError('The AI provider is rate-limiting requests.')

        mock_get_provider.return_value = BrokenProvider()
        self.authenticate_as('admin@example.com', 'StrongPass123!')
        url = reverse('ai_strategy:brand-context-generate', kwargs={'company_id': self.company.pk})
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_502_BAD_GATEWAY)


class StrategyOutputTests(BaseAiStrategyTestCase):
    def generate_brand_context(self):
        with patch('apps.ai_strategy.views.get_provider') as mock_get_provider:
            mock_get_provider.return_value = FakeProvider(BRAND_CONTEXT_RESULT)
            url = reverse('ai_strategy:brand-context-generate', kwargs={'company_id': self.company.pk})
            self.client.post(url)

    def test_requires_brand_context_first(self):
        self.authenticate_as('admin@example.com', 'StrongPass123!')
        url = reverse('ai_strategy:output-generate', kwargs={'company_id': self.company.pk, 'kind': 'content_ideas'})
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_unknown_kind_404s(self):
        self.authenticate_as('admin@example.com', 'StrongPass123!')
        url = reverse('ai_strategy:output-generate', kwargs={'company_id': self.company.pk, 'kind': 'not-a-real-kind'})
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    @patch('apps.ai_strategy.views.get_provider')
    def test_admin_can_generate_content_ideas(self, mock_get_provider):
        self.authenticate_as('admin@example.com', 'StrongPass123!')
        self.generate_brand_context()

        mock_get_provider.return_value = FakeProvider(CONTENT_IDEAS_RESULT)
        url = reverse('ai_strategy:output-generate', kwargs={'company_id': self.company.pk, 'kind': 'content_ideas'})
        response = self.client.post(url, {'notes': 'Focus on summer.'}, format='json')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['kind'], 'content_ideas')
        self.assertEqual(response.data['result'], CONTENT_IDEAS_RESULT)
        self.assertEqual(response.data['notes'], 'Focus on summer.')

        output = StrategyOutput.objects.get(company=self.company, kind='content_ideas')
        self.assertEqual(output.created_by, self.admin)

    @patch('apps.ai_strategy.views.get_provider')
    def test_list_can_filter_by_kind(self, mock_get_provider):
        self.authenticate_as('admin@example.com', 'StrongPass123!')
        self.generate_brand_context()

        mock_get_provider.return_value = FakeProvider(CONTENT_IDEAS_RESULT)
        gen_url = reverse('ai_strategy:output-generate', kwargs={'company_id': self.company.pk, 'kind': 'content_ideas'})
        self.client.post(gen_url)

        mock_get_provider.return_value = FakeProvider({'items': [{'topic': 'Sustainability', 'why_relevant': 'On brand.'}]})
        gen_url2 = reverse('ai_strategy:output-generate', kwargs={'company_id': self.company.pk, 'kind': 'topic_suggestions'})
        self.client.post(gen_url2)

        list_url = reverse('ai_strategy:output-list', kwargs={'company_id': self.company.pk})
        response = self.client.get(list_url, {'kind': 'content_ideas'})
        self.assertEqual(response.data['count'], 1)
        self.assertEqual(response.data['results'][0]['kind'], 'content_ideas')

        response_all = self.client.get(list_url)
        self.assertEqual(response_all.data['count'], 2)

    def test_client_cannot_generate_or_list(self):
        self.authenticate_as('acmeclient@example.com', 'StrongPass123!')
        gen_url = reverse('ai_strategy:output-generate', kwargs={'company_id': self.company.pk, 'kind': 'content_ideas'})
        self.assertEqual(self.client.post(gen_url).status_code, status.HTTP_403_FORBIDDEN)

        list_url = reverse('ai_strategy:output-list', kwargs={'company_id': self.company.pk})
        self.assertEqual(self.client.get(list_url).status_code, status.HTTP_403_FORBIDDEN)


class AnthropicProviderTests(TestCase):
    """Exercises the real SDK wrapper (no network) to make sure every client-side failure
    mode maps to AIProviderError/AIProviderNotConfigured rather than an uncaught exception.
    """

    def test_missing_credentials_raises_not_configured_not_a_bare_exception(self):
        import os
        old_key = os.environ.pop('ANTHROPIC_API_KEY', None)
        old_token = os.environ.pop('ANTHROPIC_AUTH_TOKEN', None)
        try:
            provider = AnthropicProvider(model='claude-opus-5')
            with self.assertRaises(AIProviderNotConfigured):
                provider.generate_json(system='sys', prompt='hello', json_schema={'type': 'object'})
        finally:
            if old_key is not None:
                os.environ['ANTHROPIC_API_KEY'] = old_key
            if old_token is not None:
                os.environ['ANTHROPIC_AUTH_TOKEN'] = old_token
