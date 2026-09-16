from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.activity_log.models import ActivityLog
from apps.activity_log.services import log_activity
from apps.authentication.models import User
from apps.companies.models import ClientProfile, Company


class LogActivityServiceTests(TestCase):
    def test_creates_an_entry_with_the_given_fields(self):
        user = User.objects.create_user(email='a@example.com', password='StrongPass123!')

        entry = log_activity(module=ActivityLog.Module.COMPANY, action='Company created', description='Acme', user=user)

        self.assertEqual(ActivityLog.objects.count(), 1)
        self.assertEqual(entry.module, ActivityLog.Module.COMPANY)
        self.assertEqual(entry.action, 'Company created')
        self.assertEqual(entry.user, user)

    def test_extracts_user_and_ip_from_request_when_not_given_explicitly(self):
        user = User.objects.create_user(email='b@example.com', password='StrongPass123!')

        class FakeRequest:
            META = {'REMOTE_ADDR': '203.0.113.9'}

            def __init__(self, u):
                self.user = u

        entry = log_activity(module=ActivityLog.Module.AUTH, action='Logged in', request=FakeRequest(user))

        self.assertEqual(entry.user, user)
        self.assertEqual(entry.ip_address, '203.0.113.9')


class ActivityLogApiTests(APITestCase):
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

    def test_client_cannot_list_activity_log(self):
        self.authenticate_as('client@example.com', 'StrongPass123!')
        response = self.client.get(reverse('activity_log:list'))
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_admin_creating_a_company_is_recorded(self):
        self.authenticate_as('admin@example.com', 'StrongPass123!')
        self.client.post(reverse('companies:company-list-create'), {'name': 'New Co'})

        response = self.client.get(reverse('activity_log:list'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        actions = [row['action'] for row in response.data['results']]
        self.assertIn('Company created', actions)

    def test_can_filter_by_module(self):
        self.authenticate_as('admin@example.com', 'StrongPass123!')
        log_activity(module=ActivityLog.Module.SOCIAL, action='Social account connected', company=self.company)
        log_activity(module=ActivityLog.Module.CALENDAR, action='Calendar item created', company=self.company)

        response = self.client.get(reverse('activity_log:list'), {'module': ActivityLog.Module.SOCIAL})
        modules = {row['module'] for row in response.data['results']}
        self.assertEqual(modules, {ActivityLog.Module.SOCIAL})

    def test_login_is_recorded(self):
        self.authenticate_as('admin@example.com', 'StrongPass123!')
        response = self.client.get(reverse('activity_log:list'), {'module': ActivityLog.Module.AUTH})
        actions = [row['action'] for row in response.data['results']]
        self.assertIn('Logged in', actions)
