import hashlib
import hmac
import json
from unittest.mock import Mock, patch

from django.test import TestCase, override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.whatsapp.models import WhatsAppConfig, WhatsAppMessage, WhatsAppTemplate
from apps.whatsapp.providers import MetaCloudProvider, clean_parameter, normalize_phone
from apps.whatsapp.services import dispatch_event, recipients_for
from tests.helpers import EagerCeleryMixin, PlatformFixturesMixin


class WhatsAppConfigApiTests(PlatformFixturesMixin, APITestCase):
    def url(self, name='whatsapp:config'):
        return reverse(name, kwargs={'company_id': self.company.pk})

    def test_admin_gets_default_config(self):
        self.login(self.admin)
        response = self.client.get(self.url())
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.data['is_enabled'])
        self.assertEqual(len(response.data['available_events']), 8)

    def test_numbers_are_validated_and_normalized(self):
        self.login(self.admin)
        response = self.client.patch(self.url(), {
            'client_numbers': [{'name': 'Owner', 'phone': '+91 98765-11111'}],
            'internal_numbers': [{'name': 'Account manager', 'phone': '00919876522222'}],
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(response.data['client_numbers'][0]['phone'], '+919876511111')
        self.assertEqual(response.data['internal_numbers'][0]['phone'], '+919876522222')

        bad = self.client.patch(self.url(), {'client_numbers': [{'name': 'X', 'phone': '123'}]}, format='json')
        self.assertEqual(bad.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_group_requires_members_then_activates(self):
        self.login(self.admin)
        WhatsAppConfig.objects.create(company=self.company, include_client_users=False)
        self.assertEqual(self.client.post(self.url('whatsapp:group'), {}).status_code, status.HTTP_400_BAD_REQUEST)
        self.client.patch(self.url(), {'internal_numbers': [{'name': 'AM', 'phone': '+919876522222'}]}, format='json')
        response = self.client.post(self.url('whatsapp:group'), {'group_name': 'Acme x Agency'}, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['group_status'], 'active')
        self.assertTrue(response.data['is_enabled'])

    def test_client_cannot_manage_whatsapp(self):
        self.login(self.client_user)
        self.assertEqual(self.client.get(self.url()).status_code, status.HTTP_403_FORBIDDEN)


class WhatsAppDispatchTests(EagerCeleryMixin, PlatformFixturesMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.config = WhatsAppConfig.objects.create(
            company=self.company, is_enabled=True,
            client_numbers=[{'name': 'Owner', 'phone': '+919876511111'}],
            internal_numbers=[{'name': 'AM', 'phone': '+919876522222'}],
        )

    def test_disabled_config_sends_nothing(self):
        self.config.is_enabled = False
        self.config.save()
        self.assertEqual(dispatch_event(self.company, 'approval_required', {'topic': 'X'}), [])

    def test_event_goes_to_client_and_internal_numbers(self):
        messages = dispatch_event(self.company, 'approval_required', {'topic': 'Diwali', 'scheduled_date': '2026-10-20', 'url': '/x'})
        self.assertEqual(len(messages), 2)
        stored = WhatsAppMessage.objects.filter(event='approval_required')
        self.assertEqual(stored.count(), 2)
        self.assertTrue(all(m.status == WhatsAppMessage.Status.SENT for m in stored))  # console provider
        self.assertTrue(all('Diwali' in m.body and 'Acme Retail' in m.body for m in stored))

    def test_internal_only_events_skip_clients(self):
        messages = dispatch_event(self.company, 'publishing_failed', {'topic': 'X', 'platform': 'Instagram', 'error': 'boom'})
        self.assertEqual([m.to_number for m in messages], ['919876522222'])

    def test_switched_off_event_is_not_sent(self):
        self.config.enabled_events = ['content_published']
        self.config.save()
        self.assertEqual(dispatch_event(self.company, 'approval_required', {'topic': 'X'}), [])

    def test_missing_template_is_logged_as_skipped(self):
        WhatsAppTemplate.objects.filter(event='content_approved').delete()
        messages = dispatch_event(self.company, 'content_approved', {'topic': 'X', 'approved_by': 'Sam'})
        self.assertTrue(all(m.status == WhatsAppMessage.Status.SKIPPED for m in messages))

    def test_opted_in_client_users_are_included(self):
        self.client_user.whatsapp_notifications_enabled = True
        self.client_user.save()
        numbers = [r['phone'] for r in recipients_for(self.config, 'approval_required')]
        self.assertIn('919876543210', numbers)


class WhatsAppProviderTests(TestCase):
    def test_phone_and_parameter_cleaning(self):
        self.assertEqual(normalize_phone('+91 (987) 654-3210'), '919876543210')
        self.assertEqual(normalize_phone('12'), '')
        # newline/tab -> space, then any run of 4+ spaces collapses to 3 (Meta's limit)
        self.assertEqual(clean_parameter('line one\nline two\t     spaced'), 'line one line two   spaced')

    @override_settings(WHATSAPP_ACCESS_TOKEN='tok', WHATSAPP_PHONE_NUMBER_ID='PN1', WHATSAPP_API_VERSION='v23.0')
    def test_meta_template_payload(self):
        response = Mock(status_code=200)
        response.json.return_value = {'messages': [{'id': 'wamid.1'}]}
        with patch('apps.whatsapp.providers.httpx.post', return_value=response) as mock_post:
            message_id = MetaCloudProvider().send_template(
                to='919876511111', template_name='content_published', language_code='en', parameters=['A', 'B\nC'],
            )
        self.assertEqual(message_id, 'wamid.1')
        url = mock_post.call_args.args[0]
        payload = mock_post.call_args.kwargs['json']
        self.assertTrue(url.endswith('/v23.0/PN1/messages'))
        self.assertEqual(payload['template']['name'], 'content_published')
        self.assertEqual(payload['template']['components'][0]['parameters'][1]['text'], 'B C')


@override_settings(WHATSAPP_WEBHOOK_VERIFY_TOKEN='verify-me', WHATSAPP_APP_SECRET='shh')
class WhatsAppWebhookTests(PlatformFixturesMixin, APITestCase):
    def url(self):
        return reverse('whatsapp_global:webhook')

    def test_verification_handshake(self):
        ok = self.client.get(self.url(), {'hub.mode': 'subscribe', 'hub.verify_token': 'verify-me', 'hub.challenge': '42'})
        self.assertEqual(ok.status_code, 200)
        self.assertEqual(ok.content, b'42')
        bad = self.client.get(self.url(), {'hub.mode': 'subscribe', 'hub.verify_token': 'nope', 'hub.challenge': '42'})
        self.assertEqual(bad.status_code, 403)

    def _post(self, payload, secret='shh'):
        body = json.dumps(payload).encode()
        signature = 'sha256=' + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
        return self.client.generic('POST', self.url(), body, content_type='application/json', HTTP_X_HUB_SIGNATURE_256=signature)

    def test_status_updates_are_applied(self):
        message = WhatsAppMessage.objects.create(
            company=self.company, event='content_published', to_number='919876511111',
            status=WhatsAppMessage.Status.SENT, provider_message_id='wamid.9',
        )
        payload = {'entry': [{'changes': [{'value': {'statuses': [{'id': 'wamid.9', 'status': 'read', 'timestamp': '1790000000'}]}}]}]}
        response = self._post(payload)
        self.assertEqual(response.status_code, 200)
        message.refresh_from_db()
        self.assertEqual(message.status, WhatsAppMessage.Status.READ)
        self.assertIsNotNone(message.read_at)

    def test_bad_signature_is_rejected(self):
        response = self._post({'entry': []}, secret='wrong')
        self.assertEqual(response.status_code, 403)
