from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.authentication.models import User
from apps.companies.models import ClientProfile, Company


class BaseCompanyTestCase(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(email='admin@example.com', password='StrongPass123!')
        self.other_admin = User.objects.create_superuser(email='admin2@example.com', password='StrongPass123!')
        self.standalone_client = User.objects.create_user(
            email='freeclient@example.com', password='StrongPass123!', role=User.Role.CLIENT,
        )

        self.company = Company.objects.create(name='Acme Retail', created_by=self.admin)
        self.company_user = User.objects.create_user(
            email='acmeclient@example.com', password='StrongPass123!', role=User.Role.CLIENT,
        )
        self.company_profile = ClientProfile.objects.create(
            user=self.company_user, company=self.company, is_primary_contact=True,
        )

    def authenticate_as(self, email, password):
        response = self.client.post(reverse('authentication:login'), {'email': email, 'password': password})
        access = response.data['access']
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {access}')
        return response


class CompanyCrudTests(BaseCompanyTestCase):
    def test_admin_can_create_company(self):
        self.authenticate_as('admin@example.com', 'StrongPass123!')
        response = self.client.post(reverse('companies:company-list-create'), {
            'name': 'New Co',
            'industry': 'Retail',
            'products': ['Widget A', 'Widget B'],
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        company = Company.objects.get(name='New Co')
        self.assertEqual(company.created_by, self.admin)
        self.assertEqual(company.products, ['Widget A', 'Widget B'])
        self.assertEqual(company.status, Company.Status.ACTIVE)

    def test_client_cannot_create_company(self):
        self.authenticate_as('acmeclient@example.com', 'StrongPass123!')
        response = self.client.post(reverse('companies:company-list-create'), {'name': 'New Co'})
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_client_cannot_list_all_companies(self):
        self.authenticate_as('acmeclient@example.com', 'StrongPass123!')
        response = self.client.get(reverse('companies:company-list-create'))
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_admin_can_edit_company(self):
        self.authenticate_as('admin@example.com', 'StrongPass123!')
        url = reverse('companies:company-detail', kwargs={'pk': self.company.pk})
        response = self.client.patch(url, {'industry': 'E-commerce'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.company.refresh_from_db()
        self.assertEqual(self.company.industry, 'E-commerce')

    def test_client_cannot_edit_own_company(self):
        self.authenticate_as('acmeclient@example.com', 'StrongPass123!')
        url = reverse('companies:company-detail', kwargs={'pk': self.company.pk})
        response = self.client.patch(url, {'industry': 'Hacked'})
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_client_can_view_own_company(self):
        self.authenticate_as('acmeclient@example.com', 'StrongPass123!')
        url = reverse('companies:company-detail', kwargs={'pk': self.company.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['name'], 'Acme Retail')

    def test_client_cannot_view_other_company(self):
        other_company = Company.objects.create(name='Other Co', created_by=self.admin)
        self.authenticate_as('acmeclient@example.com', 'StrongPass123!')
        url = reverse('companies:company-detail', kwargs={'pk': other_company.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_admin_can_deactivate_and_reactivate_company(self):
        self.authenticate_as('admin@example.com', 'StrongPass123!')
        deactivate_url = reverse('companies:company-deactivate', kwargs={'pk': self.company.pk})
        response = self.client.post(deactivate_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.company.refresh_from_db()
        self.assertEqual(self.company.status, Company.Status.INACTIVE)

        activate_url = reverse('companies:company-activate', kwargs={'pk': self.company.pk})
        response = self.client.post(activate_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.company.refresh_from_db()
        self.assertEqual(self.company.status, Company.Status.ACTIVE)

    def test_search_and_status_filters(self):
        Company.objects.create(name='Zeta Corp', status=Company.Status.INACTIVE, created_by=self.admin)
        self.authenticate_as('admin@example.com', 'StrongPass123!')

        response = self.client.get(reverse('companies:company-list-create'), {'search': 'Zeta'})
        self.assertEqual(response.data['count'], 1)

        response = self.client.get(reverse('companies:company-list-create'), {'status': 'inactive'})
        self.assertEqual(response.data['count'], 1)


class MyCompanyTests(BaseCompanyTestCase):
    def test_client_can_view_my_company(self):
        self.authenticate_as('acmeclient@example.com', 'StrongPass123!')
        response = self.client.get(reverse('companies:my-company'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['name'], 'Acme Retail')

    def test_unassigned_client_gets_404_for_my_company(self):
        self.authenticate_as('freeclient@example.com', 'StrongPass123!')
        response = self.client.get(reverse('companies:my-company'))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class OnboardingTests(BaseCompanyTestCase):
    def test_onboarding_incomplete_for_bare_company(self):
        self.authenticate_as('admin@example.com', 'StrongPass123!')
        url = reverse('companies:company-detail', kwargs={'pk': self.company.pk})
        response = self.client.get(url)
        self.assertFalse(response.data['onboarding']['is_complete'])
        self.assertIn('industry', response.data['onboarding']['missing_fields'])

    def test_onboarding_complete_once_required_fields_and_client_exist(self):
        self.company.industry = 'Retail'
        self.company.description = 'A retail business.'
        self.company.contact_email = 'contact@acme.com'
        self.company.contact_phone = '1234567890'
        self.company.address = '123 Main St'
        self.company.target_market = 'Local shoppers'
        self.company.target_audience = 'Young adults'
        self.company.usp = 'Fast delivery'
        self.company.save()

        self.authenticate_as('admin@example.com', 'StrongPass123!')
        url = reverse('companies:company-detail', kwargs={'pk': self.company.pk})
        response = self.client.get(url)
        self.assertTrue(response.data['onboarding']['is_complete'])
        self.assertEqual(response.data['onboarding']['completion_percentage'], 100)


class ClientAssignmentTests(BaseCompanyTestCase):
    def test_admin_can_create_new_client_under_company(self):
        self.authenticate_as('admin@example.com', 'StrongPass123!')
        url = reverse('companies:company-client-list-create', kwargs={'company_id': self.company.pk})
        response = self.client.post(url, {
            'email': 'brandnew@example.com',
            'first_name': 'Brand',
            'last_name': 'New',
            'designation': 'Marketing Manager',
        })
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(response.data['generated_password'])
        new_user = User.objects.get(email='brandnew@example.com')
        self.assertEqual(new_user.role, User.Role.CLIENT)
        self.assertEqual(new_user.client_profile.company, self.company)

    def test_admin_can_assign_existing_standalone_client(self):
        self.authenticate_as('admin@example.com', 'StrongPass123!')
        url = reverse('companies:company-client-list-create', kwargs={'company_id': self.company.pk})
        response = self.client.post(url, {'user_id': self.standalone_client.pk})
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.standalone_client.refresh_from_db()
        self.assertEqual(self.standalone_client.client_profile.company, self.company)

    def test_cannot_assign_client_already_at_a_company(self):
        self.authenticate_as('admin@example.com', 'StrongPass123!')
        other_company = Company.objects.create(name='Other Co', created_by=self.admin)
        url = reverse('companies:company-client-list-create', kwargs={'company_id': other_company.pk})
        response = self.client.post(url, {'user_id': self.company_user.pk})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_requires_either_user_id_or_email(self):
        self.authenticate_as('admin@example.com', 'StrongPass123!')
        url = reverse('companies:company-client-list-create', kwargs={'company_id': self.company.pk})
        response = self.client.post(url, {'designation': 'No identifying info'})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_client_cannot_add_clients(self):
        self.authenticate_as('acmeclient@example.com', 'StrongPass123!')
        url = reverse('companies:company-client-list-create', kwargs={'company_id': self.company.pk})
        response = self.client.post(url, {'email': 'x@example.com'})
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_admin_can_list_company_clients(self):
        self.authenticate_as('admin@example.com', 'StrongPass123!')
        url = reverse('companies:company-client-list-create', kwargs={'company_id': self.company.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 1)

    def test_admin_can_update_client_designation(self):
        self.authenticate_as('admin@example.com', 'StrongPass123!')
        url = reverse('companies:company-client-detail', kwargs={
            'company_id': self.company.pk, 'pk': self.company_profile.pk,
        })
        response = self.client.patch(url, {'designation': 'CEO'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.company_profile.refresh_from_db()
        self.assertEqual(self.company_profile.designation, 'CEO')

    def test_admin_can_remove_client_from_company(self):
        self.authenticate_as('admin@example.com', 'StrongPass123!')
        url = reverse('companies:company-client-detail', kwargs={
            'company_id': self.company.pk, 'pk': self.company_profile.pk,
        })
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(ClientProfile.objects.filter(pk=self.company_profile.pk).exists())
        # The underlying login should still exist, just unlinked from the company.
        self.assertTrue(User.objects.filter(pk=self.company_user.pk).exists())
