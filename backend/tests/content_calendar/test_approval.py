from unittest.mock import patch

from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.authentication.models import User
from apps.companies.models import ClientProfile, Company
from apps.content_calendar.models import ContentCalendarItem
from apps.creative_generation.models import GenerationRequest
from apps.notifications.models import Notification


class ApprovalWorkflowTests(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(email='admin@example.com', password='StrongPass123!')
        self.company = Company.objects.create(name='Acme Retail', created_by=self.admin)
        self.other_company = Company.objects.create(name='Other Co', created_by=self.admin)

        self.client_user = User.objects.create_user(
            email='client@example.com', password='StrongPass123!', role=User.Role.CLIENT,
        )
        ClientProfile.objects.create(user=self.client_user, company=self.company)

        self.other_client = User.objects.create_user(
            email='other@example.com', password='StrongPass123!', role=User.Role.CLIENT,
        )
        ClientProfile.objects.create(user=self.other_client, company=self.other_company)

        self.item = ContentCalendarItem.objects.create(
            company=self.company, topic='Diwali sale post', content_type='Static Post',
            platforms=['instagram'], scheduled_date='2026-09-01',
            status=ContentCalendarItem.Status.PENDING_APPROVAL, created_by=self.admin,
        )
        self.generation_request = GenerationRequest.objects.create(
            company=self.company, content_calendar_item=self.item,
            creative_type=GenerationRequest.CreativeType.INSTAGRAM_POST,
            prompt_brief='Diwali sale post', status=GenerationRequest.Status.SUCCEEDED,
        )

    def authenticate_as(self, email, password):
        response = self.client.post(reverse('authentication:login'), {'email': email, 'password': password})
        access = response.data['access']
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {access}')

    def approve_url(self, pk=None, company_id=None):
        return reverse('content_calendar:item-approve', kwargs={'company_id': company_id or self.company.pk, 'pk': pk or self.item.pk})

    def reject_url(self, pk=None, company_id=None):
        return reverse('content_calendar:item-reject', kwargs={'company_id': company_id or self.company.pk, 'pk': pk or self.item.pk})

    def test_client_can_approve_pending_item(self):
        self.authenticate_as('client@example.com', 'StrongPass123!')
        response = self.client.post(self.approve_url())

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.item.refresh_from_db()
        self.assertEqual(self.item.status, ContentCalendarItem.Status.APPROVED)

    def test_approving_notifies_admins(self):
        self.authenticate_as('client@example.com', 'StrongPass123!')
        self.client.post(self.approve_url())

        notification = Notification.objects.get(recipient=self.admin, notification_type=Notification.NotificationType.CONTENT_APPROVED)
        self.assertIn('Diwali sale post', notification.title)

    def test_admin_can_also_approve(self):
        self.authenticate_as('admin@example.com', 'StrongPass123!')
        response = self.client.post(self.approve_url())
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_cannot_approve_item_not_pending(self):
        self.item.status = ContentCalendarItem.Status.DRAFT
        self.item.save(update_fields=['status'])
        self.authenticate_as('client@example.com', 'StrongPass123!')

        response = self.client.post(self.approve_url())

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_client_from_another_company_cannot_approve(self):
        self.authenticate_as('other@example.com', 'StrongPass123!')
        response = self.client.post(self.approve_url())
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_reject_requires_feedback(self):
        self.authenticate_as('client@example.com', 'StrongPass123!')
        response = self.client.post(self.reject_url(), {})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.item.refresh_from_db()
        self.assertEqual(self.item.status, ContentCalendarItem.Status.PENDING_APPROVAL)

    @patch('apps.content_calendar.tasks._enqueue_creative')
    def test_reject_with_feedback_stores_it_and_triggers_one_regeneration(self, mock_enqueue):
        self.authenticate_as('client@example.com', 'StrongPass123!')

        response = self.client.post(self.reject_url(), {'feedback': 'Make the background less busy.'})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.item.refresh_from_db()
        self.assertEqual(self.item.client_feedback, 'Make the background less busy.')
        self.assertEqual(self.item.regeneration_count, 1)
        self.assertEqual(self.item.status, ContentCalendarItem.Status.GENERATING)

        new_request = GenerationRequest.objects.exclude(pk=self.generation_request.pk).get(content_calendar_item=self.item)
        self.assertIn('Make the background less busy.', new_request.prompt_brief)
        mock_enqueue.assert_called_once_with(new_request)

    @patch('apps.content_calendar.tasks._enqueue_creative')
    def test_rejecting_notifies_admins_with_feedback(self, mock_enqueue):
        self.authenticate_as('client@example.com', 'StrongPass123!')
        self.client.post(self.reject_url(), {'feedback': 'Too much text.'})

        notification = Notification.objects.get(recipient=self.admin, notification_type=Notification.NotificationType.CONTENT_REJECTED)
        self.assertEqual(notification.message, 'Too much text.')

    @patch('apps.content_calendar.tasks._enqueue_creative')
    def test_second_rejection_does_not_auto_regenerate_again(self, mock_enqueue):
        self.item.regeneration_count = 1
        self.item.status = ContentCalendarItem.Status.PENDING_APPROVAL
        self.item.save(update_fields=['regeneration_count', 'status'])
        self.authenticate_as('client@example.com', 'StrongPass123!')

        response = self.client.post(self.reject_url(), {'feedback': 'Still not right.'})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.item.refresh_from_db()
        self.assertEqual(self.item.status, ContentCalendarItem.Status.REJECTED)
        self.assertEqual(self.item.regeneration_count, 1)
        mock_enqueue.assert_not_called()


class LongTopicNotificationTests(APITestCase):
    """A topic can be a whole design brief (the full 255 characters). Notification titles quote the topic, so
    they must be shortened - Postgres rejects an over-long title and the approval request failed with a 500."""

    LONG = (
        'Create a **premium, minimal, ultra-realistic Ganesh Chaturthi social media creative** in Instagram '
        'portrait size **1080 x 1350 px (4:5)**. **Layout:** * Use a clean, soft **ivory, warm cream, or light '
        'beige background** with a luxurious and elegant feel'
    )[:255]

    # Same company, users and pending item as the workflow tests - without inheriting their test methods.
    authenticate_as = ApprovalWorkflowTests.authenticate_as
    approve_url = ApprovalWorkflowTests.approve_url
    reject_url = ApprovalWorkflowTests.reject_url

    def setUp(self):
        ApprovalWorkflowTests.setUp(self)
        self.item.topic = self.LONG
        self.item.save(update_fields=['topic'])

    def test_approving_an_item_with_a_brief_as_its_topic_succeeds_and_notifies_with_a_short_title(self):
        self.authenticate_as('client@example.com', 'StrongPass123!')
        response = self.client.post(self.approve_url())
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        notification = Notification.objects.get(
            recipient=self.admin, notification_type=Notification.NotificationType.CONTENT_APPROVED,
        )
        self.assertLessEqual(len(notification.title), 120)
        self.assertTrue(notification.title.startswith('"Create a premium, minimal, ultra-realistic Ganesh'))
        self.assertIn('…" was approved', notification.title)
        self.assertNotIn('**', notification.title)

    def test_rejecting_it_also_fits(self):
        self.authenticate_as('client@example.com', 'StrongPass123!')
        response = self.client.post(self.reject_url(), {'feedback': 'Make the background warmer.'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        for notification in Notification.objects.all():
            self.assertLessEqual(len(notification.title), 255)

    def test_every_title_fits_the_column_even_without_quotes(self):
        from apps.notifications.services import notify

        notification = notify(self.admin, Notification.NotificationType.CONTENT_APPROVED, 'x' * 400)
        self.assertEqual(len(notification.title), 255)
        self.assertTrue(notification.title.endswith('…'))
