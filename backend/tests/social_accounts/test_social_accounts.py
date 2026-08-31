from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.authentication.models import User
from apps.companies.models import ClientProfile, Company
from apps.social_accounts.models import SocialAccount


class SocialAccountTests(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(email='admin@example.com', password='StrongPass123!')
        self.company = Company.objects.create(name='Acme Retail', created_by=self.admin)
        self.other_company = Company.objects.create(name='Other Co', created_by=self.admin)

        self.client_user = User.objects.create_user(
            email='client@example.com', password='StrongPass123!', role=User.Role.CLIENT,
        )
        ClientProfile.objects.create(user=self.client_user, company=self.company)

    def authenticate_as(self, email, password):
        response = self.client.post(reverse('authentication:login'), {'email': email, 'password': password})
        access = response.data['access']
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {access}')

    def list_url(self, company_id=None):
        return reverse('social_accounts:account-list-create', kwargs={'company_id': company_id or self.company.pk})

    def detail_url(self, pk, company_id=None):
        return reverse('social_accounts:account-detail', kwargs={'company_id': company_id or self.company.pk, 'pk': pk})

    def disconnect_url(self, pk, company_id=None):
        return reverse('social_accounts:account-disconnect', kwargs={'company_id': company_id or self.company.pk, 'pk': pk})

    def test_admin_can_connect_an_account(self):
        self.authenticate_as('admin@example.com', 'StrongPass123!')
        payload = {
            'platform': SocialAccount.Platform.INSTAGRAM, 'account_name': 'Acme IG',
            'account_id': '12345', 'access_token': 'super-secret-token',
        }
        response = self.client.post(self.list_url(), payload)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertNotIn('access_token', response.data)
        self.assertTrue(response.data['has_token'])
        self.assertEqual(response.data['token_masked'], '••••oken')

        account = SocialAccount.objects.get(pk=response.data['id'])
        self.assertNotEqual(account.access_token, 'super-secret-token')
        self.assertEqual(account.connected_by, self.admin)

    def test_client_cannot_connect_an_account(self):
        self.authenticate_as('client@example.com', 'StrongPass123!')
        payload = {'platform': SocialAccount.Platform.FACEBOOK, 'account_name': 'Acme FB', 'access_token': 'x'}
        response = self.client.post(self.list_url(), payload)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_client_cannot_list_accounts(self):
        self.authenticate_as('client@example.com', 'StrongPass123!')
        self.assertEqual(self.client.get(self.list_url()).status_code, status.HTTP_403_FORBIDDEN)

    def test_admin_from_another_company_context_still_sees_only_that_companys_accounts(self):
        self.authenticate_as('admin@example.com', 'StrongPass123!')
        self.client.post(self.list_url(), {
            'platform': SocialAccount.Platform.LINKEDIN, 'account_name': 'Acme LI', 'access_token': 'tok',
        })
        response = self.client.get(self.list_url(company_id=self.other_company.pk))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 0)

    def test_admin_can_update_account_and_replace_token(self):
        account = SocialAccount.objects.create(
            company=self.company, platform=SocialAccount.Platform.INSTAGRAM, account_name='Old name',
        )
        self.authenticate_as('admin@example.com', 'StrongPass123!')
        response = self.client.patch(self.detail_url(account.pk), {'account_name': 'New name', 'access_token': 'fresh-token'})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertNotIn('access_token', response.data)
        account.refresh_from_db()
        self.assertEqual(account.account_name, 'New name')
        self.assertNotEqual(account.access_token, 'fresh-token')
        self.assertTrue(account.access_token)

    def test_disconnect_wipes_token_and_marks_disconnected(self):
        account = SocialAccount.objects.create(
            company=self.company, platform=SocialAccount.Platform.FACEBOOK, account_name='Acme FB',
            access_token='ciphertext-stand-in', status=SocialAccount.Status.CONNECTED,
        )
        self.authenticate_as('admin@example.com', 'StrongPass123!')
        response = self.client.post(self.disconnect_url(account.pk))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        account.refresh_from_db()
        self.assertEqual(account.status, SocialAccount.Status.DISCONNECTED)
        self.assertEqual(account.access_token, '')

    def test_client_cannot_reach_any_companys_accounts(self):
        # Social account management is admin-only (Epic 10), so IsAdmin rejects a
        # client before company-scoping even runs - even for their own company.
        account = SocialAccount.objects.create(
            company=self.company, platform=SocialAccount.Platform.INSTAGRAM, account_name='Acme IG',
        )
        self.authenticate_as('client@example.com', 'StrongPass123!')
        response = self.client.get(self.detail_url(account.pk))
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
