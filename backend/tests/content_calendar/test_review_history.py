import datetime
from unittest.mock import patch

from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from apps.content_calendar.models import ContentCalendarItem, ContentReviewEvent
from apps.content_calendar.services import submitted_for_review
from apps.notifications.models import Notification
from apps.notifications.tasks import send_approval_reminders
from tests.helpers import PlatformFixturesMixin, TempMediaMixin


class ReviewHistoryTests(TempMediaMixin, PlatformFixturesMixin, APITestCase):
    def setUp(self):
        super().setUp()
        self.item = self.make_item(status=ContentCalendarItem.Status.PENDING_APPROVAL)
        self.creative, self.variations = self.add_creative(self.item, variations=3)

    def url(self, name, pk=None):
        return reverse(f'content_calendar:{name}', kwargs={'company_id': self.company.pk, 'pk': pk or self.item.pk})

    def test_approve_locks_in_the_chosen_variation_and_records_history(self):
        self.login(self.client_user)
        response = self.client.post(self.url('item-approve'), {'variation_id': self.variations[1].id, 'note': 'Love it'}, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.variations[1].refresh_from_db()
        self.assertTrue(self.variations[1].is_selected)
        event = self.item.review_events.get(action=ContentReviewEvent.Action.APPROVED)
        self.assertEqual(event.actor, self.client_user)
        self.assertEqual(event.actor_role, ContentReviewEvent.ActorRole.CLIENT)
        self.assertEqual(event.metadata['variation_id'], self.variations[1].id)
        self.assertEqual(event.feedback, 'Love it')

    def test_approve_without_choice_defaults_to_first_variation(self):
        self.login(self.client_user)
        self.client.post(self.url('item-approve'))
        self.variations[0].refresh_from_db()
        self.assertTrue(self.variations[0].is_selected)

    def test_variation_from_another_item_is_rejected(self):
        other = self.make_item(status=ContentCalendarItem.Status.PENDING_APPROVAL)
        _, other_variations = self.add_creative(other)
        self.login(self.client_user)
        response = self.client.post(self.url('item-approve'), {'variation_id': other_variations[0].id}, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_reject_records_rejection_and_regeneration_request(self):
        self.login(self.client_user)
        with patch('apps.content_calendar.tasks._enqueue_creative'):
            response = self.client.post(self.url('item-reject'), {'feedback': 'Use a warmer palette'}, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        actions = list(self.item.review_events.values_list('action', flat=True))
        self.assertIn(ContentReviewEvent.Action.REJECTED, actions)
        self.assertIn(ContentReviewEvent.Action.REGENERATION_REQUESTED, actions)

    def test_history_endpoint_returns_events_and_generations(self):
        submitted_for_review(self.item.id, kind='creative', request_id=self.creative.id)
        self.login(self.client_user)
        response = self.client.get(self.url('item-history'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['events'][0]['action'], ContentReviewEvent.Action.GENERATED)
        self.assertEqual(len(response.data['generations']), 1)
        self.assertEqual(len(response.data['generations'][0]['request']['variations']), 3)

    def test_approval_queue_is_admin_only_and_filters_by_status(self):
        self.login(self.admin)
        queue = self.client.get(reverse('approvals:queue'))
        self.assertEqual(queue.status_code, status.HTTP_200_OK)
        self.assertEqual(queue.data['count'], 1)
        self.assertEqual(queue.data['results'][0]['company_name'], 'Acme Retail')
        stats = self.client.get(reverse('approvals:stats'))
        self.assertEqual(stats.data['pending_approval'], 1)

        self.login(self.client_user)
        self.assertEqual(self.client.get(reverse('approvals:queue')).status_code, status.HTTP_403_FORBIDDEN)


class ApprovalReminderTests(PlatformFixturesMixin, APITestCase):
    def test_reminds_clients_once_per_review_round(self):
        item = self.make_item(status=ContentCalendarItem.Status.PENDING_APPROVAL)
        event = submitted_for_review(item.id)
        ContentReviewEvent.objects.filter(pk=event.pk).update(created_at=timezone.now() - datetime.timedelta(hours=30))

        self.assertEqual(send_approval_reminders(), 1)
        self.assertEqual(send_approval_reminders(), 0)
        reminders = Notification.objects.filter(recipient=self.client_user, notification_type=Notification.NotificationType.REMINDER)
        self.assertEqual(reminders.count(), 1)

    def test_recent_submissions_are_not_reminded(self):
        item = self.make_item(status=ContentCalendarItem.Status.PENDING_APPROVAL)
        submitted_for_review(item.id)
        self.assertEqual(send_approval_reminders(), 0)
