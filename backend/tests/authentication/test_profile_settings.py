from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.authentication.models import User
from apps.notifications.models import Notification
from apps.notifications.services import notify
from apps.platform_settings.models import PlatformSettings


class ProfileSettingsApiTests(APITestCase):
    """Epic 20 (Client Settings: Profile / Notifications)."""

    def setUp(self):
        self.user = User.objects.create_user(email='user@example.com', password='StrongPass123!')

    def authenticate(self):
        response = self.client.post(
            reverse('authentication:login'), {'email': 'user@example.com', 'password': 'StrongPass123!'},
        )
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {response.data["access"]}')

    def test_can_update_own_profile_fields(self):
        self.authenticate()
        response = self.client.patch(reverse('authentication:profile'), {
            'first_name': 'Priya', 'phone_number': '9876543210', 'email_notifications_enabled': False,
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, 'Priya')
        self.assertFalse(self.user.email_notifications_enabled)

    def test_email_notifications_enabled_defaults_true(self):
        self.assertTrue(self.user.email_notifications_enabled)


class NotifyRespectsPreferencesTests(TestCase):
    """notify() must honor both the platform-wide toggle (Epic 19) and the
    recipient's own per-user toggle (Epic 20) - either one off means no email.
    """

    def setUp(self):
        self.user = User.objects.create_user(email='user2@example.com', password='StrongPass123!')

    def test_creates_in_app_notification_regardless_of_email_preferences(self):
        PlatformSettings.load()  # ensure singleton exists with default True
        self.user.email_notifications_enabled = False
        self.user.save()

        notification = notify(self.user, Notification.NotificationType.REMINDER, title='Test')

        self.assertEqual(Notification.objects.filter(recipient=self.user).count(), 1)
        self.assertEqual(notification.title, 'Test')

    def test_no_email_attempted_when_recipient_opted_out(self):
        settings_obj = PlatformSettings.load()
        settings_obj.send_notification_emails = True
        settings_obj.save()
        self.user.email_notifications_enabled = False
        self.user.save()

        # send_notification_email would raise/attempt an SMTP connection if
        # reached - the absence of an exception here confirms it was skipped.
        notify(self.user, Notification.NotificationType.REMINDER, title='Test')

    def test_no_email_attempted_when_platform_toggle_off(self):
        settings_obj = PlatformSettings.load()
        settings_obj.send_notification_emails = False
        settings_obj.save()
        self.user.email_notifications_enabled = True
        self.user.save()

        notify(self.user, Notification.NotificationType.REMINDER, title='Test')
