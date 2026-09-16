from unittest.mock import patch

from django.core.cache import cache
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.authentication.models import User
from apps.companies.models import ClientProfile, Company
from apps.creative_generation.models import GenerationRequest
from apps.video_generation.models import VideoGenerationRequest


class JobQueueTests(APITestCase):
    def setUp(self):
        cache.clear()  # ScopedRateThrottle counters on the login endpoint persist across tests otherwise.
        self.admin = User.objects.create_superuser(email='admin@example.com', password='StrongPass123!')
        self.company = Company.objects.create(name='Acme Retail', created_by=self.admin)
        self.client_user = User.objects.create_user(
            email='client@example.com', password='StrongPass123!', role=User.Role.CLIENT,
        )
        ClientProfile.objects.create(user=self.client_user, company=self.company)

        self.creative_job = GenerationRequest.objects.create(
            company=self.company, creative_type=GenerationRequest.CreativeType.POST,
            status=GenerationRequest.Status.PENDING,
        )
        self.video_job = VideoGenerationRequest.objects.create(
            company=self.company, video_type=VideoGenerationRequest.VideoType.INSTAGRAM_REEL,
            status=VideoGenerationRequest.Status.QUEUED, celery_task_id='fake-task-id',
        )

    def authenticate_as(self, email, password):
        response = self.client.post(reverse('authentication:login'), {'email': email, 'password': password})
        access = response.data['access']
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {access}')

    def test_client_cannot_list_jobs(self):
        self.authenticate_as('client@example.com', 'StrongPass123!')
        response = self.client.get(reverse('companies:job-queue'))
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_admin_sees_both_job_types(self):
        self.authenticate_as('admin@example.com', 'StrongPass123!')
        response = self.client.get(reverse('companies:job-queue'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        types = {row['type'] for row in response.data['results']}
        self.assertEqual(types, {'creative', 'video'})

    def test_can_filter_by_type(self):
        self.authenticate_as('admin@example.com', 'StrongPass123!')
        response = self.client.get(reverse('companies:job-queue'), {'type': 'video'})
        types = {row['type'] for row in response.data['results']}
        self.assertEqual(types, {'video'})

    def test_can_filter_by_status(self):
        self.authenticate_as('admin@example.com', 'StrongPass123!')
        response = self.client.get(reverse('companies:job-queue'), {'status': 'pending'})
        ids = {(row['type'], row['id']) for row in response.data['results']}
        self.assertEqual(ids, {('creative', self.creative_job.id)})

    def test_cancel_pending_creative_job(self):
        self.authenticate_as('admin@example.com', 'StrongPass123!')
        response = self.client.post(
            reverse('companies:job-cancel', kwargs={'job_type': 'creative', 'job_id': self.creative_job.id}),
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.creative_job.refresh_from_db()
        self.assertEqual(self.creative_job.status, GenerationRequest.Status.FAILED)
        self.assertIn('Cancelled', self.creative_job.error_message)

    @patch('config.celery.app.control.revoke')
    def test_cancel_queued_video_job_revokes_celery_task(self, mock_revoke):
        self.authenticate_as('admin@example.com', 'StrongPass123!')
        response = self.client.post(
            reverse('companies:job-cancel', kwargs={'job_type': 'video', 'job_id': self.video_job.id}),
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        mock_revoke.assert_called_once_with('fake-task-id')
        self.video_job.refresh_from_db()
        self.assertEqual(self.video_job.status, VideoGenerationRequest.Status.FAILED)

    def test_cannot_cancel_a_succeeded_job(self):
        self.creative_job.status = GenerationRequest.Status.SUCCEEDED
        self.creative_job.save(update_fields=['status'])
        self.authenticate_as('admin@example.com', 'StrongPass123!')
        response = self.client.post(
            reverse('companies:job-cancel', kwargs={'job_type': 'creative', 'job_id': self.creative_job.id}),
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_unknown_job_type_404s(self):
        self.authenticate_as('admin@example.com', 'StrongPass123!')
        response = self.client.post(
            reverse('companies:job-cancel', kwargs={'job_type': 'publishing', 'job_id': 1}),
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
