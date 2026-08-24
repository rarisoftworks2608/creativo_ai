import datetime
from unittest.mock import patch

from django.core import mail
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.authentication.models import User
from apps.companies.models import ClientProfile, Company
from apps.content_calendar.models import ContentCalendarItem
from apps.notifications.models import Notification
from apps.notifications.services import notify
from apps.notifications.tasks import send_content_reminders
from config.celery import app as celery_app


class BaseNotificationsTestCase(APITestCase):
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
        return response


class NotificationApiTests(BaseNotificationsTestCase):
    def test_user_only_sees_their_own_notifications(self):
        notify(self.admin, Notification.NotificationType.REMINDER, 'For admin')
        notify(self.client_user, Notification.NotificationType.CONTENT_GENERATED, 'For client')

        self.authenticate_as('client@example.com', 'StrongPass123!')
        response = self.client.get(reverse('notifications:list'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 1)
        self.assertEqual(response.data['results'][0]['title'], 'For client')

    def test_unread_count(self):
        notify(self.admin, Notification.NotificationType.REMINDER, 'One')
        notify(self.admin, Notification.NotificationType.REMINDER, 'Two')
        self.authenticate_as('admin@example.com', 'StrongPass123!')

        response = self.client.get(reverse('notifications:unread-count'))
        self.assertEqual(response.data['count'], 2)

    def test_mark_one_read(self):
        n = notify(self.admin, Notification.NotificationType.REMINDER, 'One')
        self.authenticate_as('admin@example.com', 'StrongPass123!')

        response = self.client.post(reverse('notifications:mark-read', kwargs={'pk': n.pk}))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        n.refresh_from_db()
        self.assertTrue(n.is_read)
        self.assertIsNotNone(n.read_at)

    def test_cannot_mark_another_users_notification_read(self):
        n = notify(self.client_user, Notification.NotificationType.REMINDER, 'Not yours')
        self.authenticate_as('admin@example.com', 'StrongPass123!')

        response = self.client.post(reverse('notifications:mark-read', kwargs={'pk': n.pk}))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_mark_all_read(self):
        notify(self.admin, Notification.NotificationType.REMINDER, 'One')
        notify(self.admin, Notification.NotificationType.REMINDER, 'Two')
        notify(self.admin, Notification.NotificationType.REMINDER, 'Three')
        self.authenticate_as('admin@example.com', 'StrongPass123!')

        response = self.client.post(reverse('notifications:mark-all-read'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['updated'], 3)
        self.assertEqual(Notification.objects.filter(recipient=self.admin, is_read=False).count(), 0)

    def test_unauthenticated_rejected(self):
        response = self.client.get(reverse('notifications:list'))
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class WelcomeEmailTests(BaseNotificationsTestCase):
    def test_creating_a_client_via_auth_endpoint_sends_welcome_email(self):
        self.authenticate_as('admin@example.com', 'StrongPass123!')
        response = self.client.post(reverse('authentication:user-list-create'), {
            'email': 'newclient@example.com', 'first_name': 'New',
        })
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        self.assertEqual(len(mail.outbox), 1)
        sent = mail.outbox[0]
        self.assertEqual(sent.to, ['newclient@example.com'])
        self.assertIn('Temporary password', sent.body)
        self.assertIn(response.data['generated_password'], sent.body)

    def test_creating_a_new_client_via_company_endpoint_sends_welcome_email(self):
        self.authenticate_as('admin@example.com', 'StrongPass123!')
        url = reverse('companies:company-client-list-create', kwargs={'company_id': self.company.pk})
        response = self.client.post(url, {'email': 'brandnew@example.com', 'first_name': 'Brand'})
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ['brandnew@example.com'])

    def test_assigning_an_existing_client_does_not_send_a_welcome_email(self):
        standalone = User.objects.create_user(
            email='standalone@example.com', password='StrongPass123!', role=User.Role.CLIENT,
        )
        self.authenticate_as('admin@example.com', 'StrongPass123!')
        url = reverse('companies:company-client-list-create', kwargs={'company_id': self.company.pk})
        response = self.client.post(url, {'user_id': standalone.pk})
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(len(mail.outbox), 0)


class OnboardingNotificationTests(BaseNotificationsTestCase):
    """Company/client creation notifies the admin team, in addition to the
    welcome email covered by WelcomeEmailTests."""

    def setUp(self):
        super().setUp()
        self.other_admin = User.objects.create_superuser(email='admin2@example.com', password='StrongPass123!')

    def test_creating_a_company_notifies_other_admins_not_the_creator(self):
        self.authenticate_as('admin@example.com', 'StrongPass123!')
        response = self.client.post(reverse('companies:company-list-create'), {'name': 'New Co'})
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        notifications = Notification.objects.filter(notification_type=Notification.NotificationType.COMPANY_CREATED)
        recipients = set(notifications.values_list('recipient_id', flat=True))
        self.assertEqual(recipients, {self.other_admin.id})

    def test_adding_a_new_client_notifies_other_admins_and_the_client(self):
        self.authenticate_as('admin@example.com', 'StrongPass123!')
        url = reverse('companies:company-client-list-create', kwargs={'company_id': self.company.pk})
        response = self.client.post(url, {'email': 'brandnew@example.com', 'first_name': 'Brand'})
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        new_user = User.objects.get(email='brandnew@example.com')

        notifications = Notification.objects.filter(notification_type=Notification.NotificationType.CLIENT_ADDED)
        recipients = set(notifications.values_list('recipient_id', flat=True))
        self.assertEqual(recipients, {self.other_admin.id, new_user.id})

    def test_adding_a_new_admin_notifies_other_admins_and_the_new_admin(self):
        self.authenticate_as('admin@example.com', 'StrongPass123!')
        response = self.client.post(reverse('authentication:user-list-create'), {
            'email': 'newadmin@example.com', 'first_name': 'New', 'role': 'admin',
        })
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        new_admin = User.objects.get(email='newadmin@example.com')

        notifications = Notification.objects.filter(notification_type=Notification.NotificationType.ADMIN_ADDED)
        recipients = set(notifications.values_list('recipient_id', flat=True))
        self.assertEqual(recipients, {self.other_admin.id, new_admin.id})

    def test_assigning_an_existing_client_still_notifies(self):
        standalone = User.objects.create_user(
            email='standalone@example.com', password='StrongPass123!', role=User.Role.CLIENT,
        )
        self.authenticate_as('admin@example.com', 'StrongPass123!')
        url = reverse('companies:company-client-list-create', kwargs={'company_id': self.company.pk})
        response = self.client.post(url, {'user_id': standalone.pk})
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        notifications = Notification.objects.filter(notification_type=Notification.NotificationType.CLIENT_ADDED)
        recipients = set(notifications.values_list('recipient_id', flat=True))
        self.assertEqual(recipients, {self.other_admin.id, standalone.id})


class ContentGeneratedNotificationTests(BaseNotificationsTestCase):
    """Confirms the AI generation tasks actually create notifications - not
    just that they store the flag, since that's the part a refactor could
    silently break."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._original_eager = celery_app.conf.task_always_eager
        cls._original_propagates = celery_app.conf.task_eager_propagates
        celery_app.conf.task_always_eager = True
        celery_app.conf.task_eager_propagates = True

    @classmethod
    def tearDownClass(cls):
        celery_app.conf.task_always_eager = cls._original_eager
        celery_app.conf.task_eager_propagates = cls._original_propagates
        super().tearDownClass()

    @patch('apps.creative_generation.tasks.get_text_provider')
    @patch('apps.creative_generation.tasks.get_image_provider')
    def test_creative_generation_success_notifies_admin_and_client(self, mock_image, mock_text):
        class FakeImage:
            model = 'gemini-3.1-flash-image'

            def generate_image(self, *, prompt, reference_images=None):
                return b'\x89PNG\r\n\x1a\n' + b'0' * 32, 'image/png'

        class FakeText:
            model = 'claude-opus-5'

            def generate_json(self, *, system, prompt, json_schema):
                return {
                    'caption': 'c', 'headline': 'h', 'description': 'd',
                    'cta': 'Shop now', 'hashtags': ['#x'], 'keywords': ['x'],
                }

        mock_image.return_value = FakeImage()
        mock_text.return_value = FakeText()

        self.authenticate_as('admin@example.com', 'StrongPass123!')
        url = reverse('creative_generation:request-list-create', kwargs={'company_id': self.company.pk})
        response = self.client.post(url, {'creative_type': 'instagram_post'}, format='json')
        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)

        notifications = Notification.objects.filter(notification_type=Notification.NotificationType.CONTENT_GENERATED)
        recipients = set(notifications.values_list('recipient_id', flat=True))
        self.assertEqual(recipients, {self.admin.id, self.client_user.id})


class ReminderTaskTests(BaseNotificationsTestCase):
    def test_reminds_admin_about_draft_content_due_soon(self):
        ContentCalendarItem.objects.create(
            company=self.company, topic='Due tomorrow', content_type='Reel',
            platforms=[ContentCalendarItem.Platform.INSTAGRAM],
            scheduled_date=datetime.date.today() + datetime.timedelta(days=1),
            status=ContentCalendarItem.Status.DRAFT,
        )

        sent = send_content_reminders()
        self.assertEqual(sent, 1)
        self.assertEqual(
            Notification.objects.filter(recipient=self.admin, notification_type=Notification.NotificationType.REMINDER).count(),
            1,
        )

    def test_does_not_remind_twice_for_the_same_item(self):
        ContentCalendarItem.objects.create(
            company=self.company, topic='Due tomorrow', content_type='Reel',
            platforms=[ContentCalendarItem.Platform.INSTAGRAM],
            scheduled_date=datetime.date.today() + datetime.timedelta(days=1),
            status=ContentCalendarItem.Status.DRAFT,
        )

        send_content_reminders()
        second_run_count = send_content_reminders()
        self.assertEqual(second_run_count, 0)
        self.assertEqual(
            Notification.objects.filter(notification_type=Notification.NotificationType.REMINDER).count(), 1,
        )

    def test_ignores_items_already_generated(self):
        ContentCalendarItem.objects.create(
            company=self.company, topic='Already done', content_type='Reel',
            platforms=[ContentCalendarItem.Platform.INSTAGRAM],
            scheduled_date=datetime.date.today() + datetime.timedelta(days=1),
            status=ContentCalendarItem.Status.GENERATED,
        )
        sent = send_content_reminders()
        self.assertEqual(sent, 0)

    def test_ignores_items_too_far_in_the_future(self):
        ContentCalendarItem.objects.create(
            company=self.company, topic='Later', content_type='Reel',
            platforms=[ContentCalendarItem.Platform.INSTAGRAM],
            scheduled_date=datetime.date.today() + datetime.timedelta(days=10),
            status=ContentCalendarItem.Status.DRAFT,
        )
        sent = send_content_reminders()
        self.assertEqual(sent, 0)
