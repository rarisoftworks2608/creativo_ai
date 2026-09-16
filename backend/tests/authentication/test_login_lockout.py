from django.core.cache import cache
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from apps.authentication.models import LoginHistory, User
from apps.notifications.models import Notification


class LoginLockoutTests(APITestCase):
    def setUp(self):
        # ScopedRateThrottle counters live in Django's cache, not the DB, so they
        # survive across test methods (TestCase only rolls back the DB) unless
        # cleared explicitly - without this, later tests here would fail from
        # throttling exhausted by earlier ones rather than from the lockout logic
        # actually under test.
        cache.clear()
        self.user = User.objects.create_user(email='target@example.com', password='CorrectPass123!')
        self.admin = User.objects.create_superuser(email='admin@example.com', password='StrongPass123!')

    def _fail(self, email='target@example.com'):
        return self.client.post(reverse('authentication:login'), {'email': email, 'password': 'WrongPass!'})

    def test_wrong_password_is_rejected_normally_below_threshold(self):
        response = self._fail()
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_locks_out_after_threshold_failures(self):
        for _ in range(5):
            self._fail()

        response = self.client.post(
            reverse('authentication:login'), {'email': 'target@example.com', 'password': 'CorrectPass123!'},
        )
        self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)

    def test_lockout_is_per_email_not_global(self):
        for _ in range(5):
            self._fail('target@example.com')

        other_user = User.objects.create_user(email='other@example.com', password='OtherPass123!')
        response = self.client.post(
            reverse('authentication:login'), {'email': 'other@example.com', 'password': 'OtherPass123!'},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        del other_user

    def test_crossing_threshold_notifies_admins_once(self):
        for _ in range(5):
            self._fail()

        notifications = Notification.objects.filter(
            recipient=self.admin, notification_type=Notification.NotificationType.SUSPICIOUS_LOGIN,
        )
        self.assertEqual(notifications.count(), 1)

    def test_old_failures_outside_window_do_not_count(self):
        old_time = timezone.now() - timezone.timedelta(minutes=30)
        for _ in range(5):
            LoginHistory.objects.create(
                email_attempted='target@example.com', was_successful=False, created_at=old_time,
            )

        response = self.client.post(
            reverse('authentication:login'), {'email': 'target@example.com', 'password': 'CorrectPass123!'},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
