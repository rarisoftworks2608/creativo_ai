"""Cross-app tests for Epic 01 (Role & Access): a client's ClientProfile.page_permissions
must actually gate each page's API, not just hide the sidebar link - see CompanyScopedMixin
in each of companies/brand/content_calendar/creative_generation/video_generation.
"""
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.authentication.models import User
from apps.companies.models import ClientProfile, Company


class BasePagePermissionTestCase(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(email='admin@example.com', password='StrongPass123!')
        self.company = Company.objects.create(name='Acme Retail', created_by=self.admin)
        self.client_user = User.objects.create_user(
            email='client@example.com', password='StrongPass123!', role=User.Role.CLIENT,
        )
        self.profile = ClientProfile.objects.create(user=self.client_user, company=self.company, page_permissions=[])

    def grant(self, *pages):
        self.profile.page_permissions = list(pages)
        self.profile.save(update_fields=['page_permissions'])

    def authenticate_as(self, email, password):
        response = self.client.post(reverse('authentication:login'), {'email': email, 'password': password})
        access = response.data['access']
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {access}')
        return response


class ClientProfilePagePermissionModelTests(BasePagePermissionTestCase):
    def test_new_client_defaults_to_full_access(self):
        fresh_user = User.objects.create_user(email='fresh@example.com', password='StrongPass123!', role=User.Role.CLIENT)
        fresh_profile = ClientProfile.objects.create(user=fresh_user, company=self.company)
        self.assertEqual(set(fresh_profile.page_permissions), {choice for choice, _ in ClientProfile.Page.choices})

    def test_can_access_checks_membership(self):
        self.grant('brand', 'calendar')
        self.assertTrue(self.profile.can_access('brand'))
        self.assertFalse(self.profile.can_access('dashboard'))


class DashboardPagePermissionTests(BasePagePermissionTestCase):
    def test_client_without_dashboard_access_gets_404(self):
        self.grant('brand')
        self.authenticate_as('client@example.com', 'StrongPass123!')
        response = self.client.get(reverse('companies:my-company'))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_client_with_dashboard_access_succeeds(self):
        self.grant('dashboard')
        self.authenticate_as('client@example.com', 'StrongPass123!')
        response = self.client.get(reverse('companies:my-company'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_admin_bypasses_page_permissions_entirely(self):
        # Admins don't have a client_profile at all - MyCompanyView still 404s them, but
        # for the "no profile" reason, never the page-permission check.
        self.authenticate_as('admin@example.com', 'StrongPass123!')
        response = self.client.get(reverse('companies:my-company'))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class BrandPagePermissionTests(BasePagePermissionTestCase):
    def test_client_without_brand_access_gets_404(self):
        self.grant('dashboard')
        self.authenticate_as('client@example.com', 'StrongPass123!')
        url = reverse('brand:brand-profile', kwargs={'company_id': self.company.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_client_with_brand_access_succeeds(self):
        self.grant('brand')
        self.authenticate_as('client@example.com', 'StrongPass123!')
        url = reverse('brand:brand-profile', kwargs={'company_id': self.company.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_admin_unaffected_by_client_page_permissions(self):
        self.authenticate_as('admin@example.com', 'StrongPass123!')
        url = reverse('brand:brand-profile', kwargs={'company_id': self.company.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)


class CalendarPagePermissionTests(BasePagePermissionTestCase):
    def test_client_without_calendar_access_gets_404(self):
        self.grant('dashboard')
        self.authenticate_as('client@example.com', 'StrongPass123!')
        url = reverse('content_calendar:item-list-create', kwargs={'company_id': self.company.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_client_with_calendar_access_succeeds(self):
        self.grant('calendar')
        self.authenticate_as('client@example.com', 'StrongPass123!')
        url = reverse('content_calendar:item-list-create', kwargs={'company_id': self.company.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)


class CreativeGenerationPagePermissionTests(BasePagePermissionTestCase):
    def test_client_without_creative_generation_access_gets_404(self):
        self.grant('dashboard')
        self.authenticate_as('client@example.com', 'StrongPass123!')
        url = reverse('creative_generation:request-list-create', kwargs={'company_id': self.company.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_client_with_creative_generation_access_succeeds(self):
        self.grant('creative_generation')
        self.authenticate_as('client@example.com', 'StrongPass123!')
        url = reverse('creative_generation:request-list-create', kwargs={'company_id': self.company.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)


class VideoGenerationPagePermissionTests(BasePagePermissionTestCase):
    def test_client_without_video_generation_access_gets_404(self):
        self.grant('dashboard')
        self.authenticate_as('client@example.com', 'StrongPass123!')
        url = reverse('video_generation:request-list-create', kwargs={'company_id': self.company.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_client_with_video_generation_access_succeeds(self):
        self.grant('video_generation')
        self.authenticate_as('client@example.com', 'StrongPass123!')
        url = reverse('video_generation:request-list-create', kwargs={'company_id': self.company.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)


class AiStrategyPagePermissionTests(BasePagePermissionTestCase):
    def test_client_without_ai_strategy_access_gets_404(self):
        self.grant('dashboard')
        self.authenticate_as('client@example.com', 'StrongPass123!')
        url = reverse('ai_strategy:output-list', kwargs={'company_id': self.company.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_client_with_ai_strategy_access_succeeds(self):
        self.grant('ai_strategy')
        self.authenticate_as('client@example.com', 'StrongPass123!')
        url = reverse('ai_strategy:output-list', kwargs={'company_id': self.company.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_admin_unaffected_by_client_page_permissions(self):
        self.authenticate_as('admin@example.com', 'StrongPass123!')
        url = reverse('ai_strategy:output-list', kwargs={'company_id': self.company.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_client_with_ai_strategy_access_cannot_generate(self):
        """Generation stays an admin-only action - a granted client can check their AI
        strategy but not trigger new (costly) generations themselves.
        """
        self.grant('ai_strategy')
        self.authenticate_as('client@example.com', 'StrongPass123!')
        url = reverse('ai_strategy:output-generate', kwargs={'company_id': self.company.pk, 'kind': 'content_ideas'})
        response = self.client.post(url, {'notes': ''}, format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class ClientProfileUpdateSerializerTests(BasePagePermissionTestCase):
    def test_admin_can_update_page_permissions(self):
        self.authenticate_as('admin@example.com', 'StrongPass123!')
        url = reverse('companies:company-client-detail', kwargs={'company_id': self.company.pk, 'pk': self.profile.pk})
        response = self.client.patch(url, {'page_permissions': ['dashboard', 'brand']}, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.profile.refresh_from_db()
        self.assertEqual(set(self.profile.page_permissions), {'dashboard', 'brand'})

    def test_invalid_page_key_is_rejected(self):
        self.authenticate_as('admin@example.com', 'StrongPass123!')
        url = reverse('companies:company-client-detail', kwargs={'company_id': self.company.pk, 'pk': self.profile.pk})
        response = self.client.patch(url, {'page_permissions': ['not-a-real-page']}, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_patch_response_includes_full_representation_not_just_writable_fields(self):
        """Regression test, same class of bug as UserDetailView: the response used to come
        from ClientProfileUpdateSerializer, which omits id/user/company - the Access
        Control page merges this straight into state, so it must be complete.
        """
        self.authenticate_as('admin@example.com', 'StrongPass123!')
        url = reverse('companies:company-client-detail', kwargs={'company_id': self.company.pk, 'pk': self.profile.pk})

        response = self.client.patch(url, {'page_permissions': ['dashboard']}, format='json')

        self.assertEqual(response.data['id'], self.profile.pk)
        self.assertEqual(response.data['user']['id'], self.client_user.pk)
        self.assertIn('company', response.data)

        # A second edit using only the first response's data must still work.
        second = self.client.patch(url, {'page_permissions': ['dashboard', 'brand']}, format='json')
        self.assertEqual(second.status_code, status.HTTP_200_OK)
