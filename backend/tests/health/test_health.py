from unittest.mock import patch

from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from tests.helpers import PlatformFixturesMixin, TempMediaMixin


class HealthTests(TempMediaMixin, PlatformFixturesMixin, APITestCase):
    def test_public_health_probe(self):
        response = self.client.get(reverse('health:health'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'ok')

    def test_details_are_admin_only(self):
        self.assertEqual(self.client.get(reverse('health:details')).status_code, status.HTTP_401_UNAUTHORIZED)
        self.login(self.client_user)
        self.assertEqual(self.client.get(reverse('health:details')).status_code, status.HTTP_403_FORBIDDEN)

    @patch('apps.health.views._check_celery', return_value={'ok': False, 'workers': []})
    @patch('apps.health.views._check_redis', return_value={'ok': True})
    def test_details_report_each_dependency(self, mock_redis, mock_celery):
        self.login(self.admin)
        response = self.client.get(reverse('health:details'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'degraded')
        self.assertTrue(response.data['checks']['database']['ok'])
        self.assertIn('text', response.data['ai'])
        self.assertIn('meta', response.data['social_oauth'])
