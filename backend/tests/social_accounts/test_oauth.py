from unittest.mock import Mock, patch
from urllib.parse import parse_qs, urlparse

from django.test import override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.social_accounts import oauth
from apps.social_accounts.models import SocialAccount, SocialOAuthSession
from common.crypto import decrypt_secret
from tests.helpers import PlatformFixturesMixin

META = {'META_APP_ID': 'app-1', 'META_APP_SECRET': 'secret-1', 'META_LOGIN_CONFIG_ID': '',
        'SOCIAL_OAUTH_REDIRECT_BASE': 'https://app.example.com'}
LINKEDIN = {'LINKEDIN_CLIENT_ID': 'li-1', 'LINKEDIN_CLIENT_SECRET': 'li-secret',
            'SOCIAL_OAUTH_REDIRECT_BASE': 'https://app.example.com'}


def response(payload, status_code=200):
    mock = Mock(status_code=status_code)
    mock.json.return_value = payload
    mock.text = str(payload)
    return mock


class OAuthTests(PlatformFixturesMixin, APITestCase):
    def url(self, name, **kwargs):
        return reverse(f'social_accounts:{name}', kwargs={'company_id': self.company.pk, **kwargs})

    @override_settings(META_APP_ID='', META_APP_SECRET='')
    def test_start_explains_missing_app_credentials(self):
        self.login(self.admin)
        response_ = self.client.get(self.url('oauth-start', provider='meta'))
        self.assertEqual(response_.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('META_APP_ID', response_.data['detail'])

    @override_settings(**META)
    def test_start_returns_authorization_url_with_signed_state(self):
        self.login(self.admin)
        data = self.client.get(self.url('oauth-start', provider='meta')).data
        query = parse_qs(urlparse(data['authorization_url']).query)
        self.assertEqual(query['client_id'], ['app-1'])
        self.assertEqual(query['redirect_uri'], ['https://app.example.com/oauth/callback/meta'])
        self.assertIn('pages_manage_posts', query['scope'][0])
        state = oauth.parse_state(query['state'][0], provider='meta', company_id=self.company.id, user_id=self.admin.id)
        self.assertEqual(state['c'], self.company.id)

    @override_settings(**META)
    def test_state_for_another_company_is_rejected(self):
        state = oauth.build_state(company_id=self.other_company.id, user_id=self.admin.id, provider='meta')
        self.login(self.admin)
        response_ = self.client.post(self.url('oauth-complete', provider='meta'), {'code': 'c', 'state': state})
        self.assertEqual(response_.status_code, status.HTTP_400_BAD_REQUEST)

    @override_settings(**META)
    def test_meta_complete_then_connect_page_and_instagram(self):
        state = oauth.build_state(company_id=self.company.id, user_id=self.admin.id, provider='meta')

        def fake_get(url, params=None, timeout=None):
            if url.endswith('/oauth/access_token') and 'code' in params:
                return response({'access_token': 'short'})
            if url.endswith('/oauth/access_token'):
                return response({'access_token': 'long', 'expires_in': 5184000})
            if url.endswith('/me/accounts'):
                return response({'data': [{
                    'id': 'PAGE1', 'name': 'Acme Page', 'access_token': 'page-token', 'followers_count': 900,
                    'instagram_business_account': {'id': 'IG1', 'username': 'acme', 'followers_count': 1500},
                }]})
            if url.endswith('/me/permissions'):
                return response({'data': [{'permission': p, 'status': 'granted'}
                                          for p in ('pages_manage_posts', 'instagram_content_publish')]})
            raise AssertionError(f'unexpected url {url}')

        self.login(self.admin)
        with patch('apps.social_accounts.oauth.httpx.get', side_effect=fake_get):
            completed = self.client.post(self.url('oauth-complete', provider='meta'), {'code': 'abc', 'state': state})
        self.assertEqual(completed.status_code, status.HTTP_200_OK, completed.data)
        keys = {c['key'] for c in completed.data['candidates']}
        self.assertEqual(keys, {'facebook:PAGE1', 'instagram:IG1'})
        self.assertNotIn('token', completed.data['candidates'][0])

        connect = self.client.post(
            self.url('oauth-connect', session_id=completed.data['session_id']), {'keys': ['instagram:IG1']}, format='json',
        )
        self.assertEqual(connect.status_code, status.HTTP_201_CREATED, connect.data)
        account = SocialAccount.objects.get(platform='instagram', account_id='IG1')
        self.assertEqual(decrypt_secret(account.access_token), 'page-token')
        self.assertEqual(account.metadata['page_id'], 'PAGE1')
        self.assertEqual(account.connection_method, SocialAccount.ConnectionMethod.OAUTH)
        self.assertIn('instagram_content_publish', account.scopes)

        again = self.client.post(
            self.url('oauth-connect', session_id=completed.data['session_id']), {'keys': ['facebook:PAGE1']}, format='json',
        )
        self.assertEqual(again.status_code, status.HTTP_400_BAD_REQUEST)  # single-use session
        self.assertEqual(SocialOAuthSession.objects.get().payload, '')

    @override_settings(**LINKEDIN)
    def test_linkedin_complete_lists_member_and_organizations(self):
        state = oauth.build_state(company_id=self.company.id, user_id=self.admin.id, provider='linkedin')

        def fake_get(url, params=None, headers=None, timeout=None):
            if url.endswith('/v2/userinfo'):
                return response({'sub': 'MEMBER1', 'name': 'Sam Admin'})
            if url.endswith('/rest/organizationAcls'):
                return response({'elements': [{'organization': 'urn:li:organization:42'}]})
            if url.endswith('/rest/organizations/42'):
                return response({'localizedName': 'Acme Ltd', 'vanityName': 'acme'})
            raise AssertionError(url)

        token_response = response({'access_token': 'li-token', 'expires_in': 5184000, 'refresh_token': 'r1',
                                   'refresh_token_expires_in': 31536000, 'scope': 'w_organization_social,openid'})
        self.login(self.admin)
        with patch('apps.social_accounts.oauth.httpx.post', return_value=token_response), \
                patch('apps.social_accounts.oauth.httpx.get', side_effect=fake_get):
            completed = self.client.post(self.url('oauth-complete', provider='linkedin'), {'code': 'x', 'state': state})
        self.assertEqual(completed.status_code, status.HTTP_200_OK, completed.data)
        self.assertEqual({c['key'] for c in completed.data['candidates']},
                         {'linkedin:person:MEMBER1', 'linkedin:organization:42'})

        self.client.post(self.url('oauth-connect', session_id=completed.data['session_id']),
                         {'keys': ['linkedin:organization:42']}, format='json')
        account = SocialAccount.objects.get(platform='linkedin')
        self.assertEqual(account.linkedin_urn, 'urn:li:organization:42')
        self.assertEqual(decrypt_secret(account.refresh_token), 'r1')
        self.assertIsNotNone(account.token_expires_at)

    def test_oauth_status_lists_redirect_uris(self):
        self.login(self.admin)
        data = self.client.get(self.url('oauth-status')).data
        self.assertTrue(data['meta']['redirect_uri'].endswith('/oauth/callback/meta'))
        self.assertTrue(data['linkedin']['redirect_uri'].endswith('/oauth/callback/linkedin'))
