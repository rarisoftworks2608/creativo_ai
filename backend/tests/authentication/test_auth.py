from django.contrib.auth.tokens import default_token_generator
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from rest_framework import status
from rest_framework.test import APITestCase

from apps.authentication.models import LoginHistory, User


class BaseAuthTestCase(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(email='admin@example.com', password='StrongPass123!')
        self.client_user = User.objects.create_user(
            email='client@example.com', password='StrongPass123!', role=User.Role.CLIENT,
        )

    def login(self, email, password):
        response = self.client.post(reverse('authentication:login'), {'email': email, 'password': password})
        return response

    def authenticate_as(self, email, password):
        response = self.login(email, password)
        access = response.data['access']
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {access}')
        return response


class LoginTests(BaseAuthTestCase):
    def test_login_success_returns_tokens_and_user(self):
        response = self.login('admin@example.com', 'StrongPass123!')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('access', response.data)
        self.assertIn('refresh', response.data)
        self.assertEqual(response.data['user']['email'], 'admin@example.com')
        self.assertEqual(response.data['user']['role'], 'admin')

    def test_login_records_success_history(self):
        self.login('admin@example.com', 'StrongPass123!')
        history = LoginHistory.objects.filter(email_attempted='admin@example.com').first()
        self.assertIsNotNone(history)
        self.assertTrue(history.was_successful)
        self.assertEqual(history.user, self.admin)

    def test_login_wrong_password_fails_and_is_logged(self):
        response = self.login('admin@example.com', 'WrongPassword!')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        history = LoginHistory.objects.filter(email_attempted='admin@example.com').first()
        self.assertIsNotNone(history)
        self.assertFalse(history.was_successful)

    def test_login_inactive_account_fails(self):
        self.client_user.is_active = False
        self.client_user.save(update_fields=['is_active'])
        response = self.login('client@example.com', 'StrongPass123!')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class LogoutAndRefreshTests(BaseAuthTestCase):
    def test_logout_blacklists_refresh_token(self):
        login_response = self.login('client@example.com', 'StrongPass123!')
        refresh = login_response.data['refresh']
        access = login_response.data['access']

        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {access}')
        logout_response = self.client.post(reverse('authentication:logout'), {'refresh': refresh})
        self.assertEqual(logout_response.status_code, status.HTTP_205_RESET_CONTENT)

        refresh_response = self.client.post(reverse('authentication:refresh'), {'refresh': refresh})
        self.assertEqual(refresh_response.status_code, status.HTTP_401_UNAUTHORIZED)


class ProfileTests(BaseAuthTestCase):
    def test_get_own_profile(self):
        self.authenticate_as('client@example.com', 'StrongPass123!')
        response = self.client.get(reverse('authentication:profile'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['email'], 'client@example.com')

    def test_update_own_profile(self):
        self.authenticate_as('client@example.com', 'StrongPass123!')
        response = self.client.patch(reverse('authentication:profile'), {'first_name': 'Test'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.client_user.refresh_from_db()
        self.assertEqual(self.client_user.first_name, 'Test')

    def test_profile_requires_authentication(self):
        response = self.client.get(reverse('authentication:profile'))
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class ChangePasswordTests(BaseAuthTestCase):
    def test_change_password_success(self):
        self.authenticate_as('client@example.com', 'StrongPass123!')
        response = self.client.post(reverse('authentication:change-password'), {
            'old_password': 'StrongPass123!',
            'new_password': 'NewStrongerPass456!',
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.client_user.refresh_from_db()
        self.assertTrue(self.client_user.check_password('NewStrongerPass456!'))

    def test_change_password_wrong_old_password(self):
        self.authenticate_as('client@example.com', 'StrongPass123!')
        response = self.client.post(reverse('authentication:change-password'), {
            'old_password': 'WrongOld!',
            'new_password': 'NewStrongerPass456!',
        })
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class ForgotResetPasswordTests(BaseAuthTestCase):
    def test_forgot_password_returns_generic_message_for_unknown_email(self):
        response = self.client.post(reverse('authentication:forgot-password'), {'email': 'nobody@example.com'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_reset_password_with_valid_token(self):
        uid = urlsafe_base64_encode(force_bytes(self.client_user.pk))
        token = default_token_generator.make_token(self.client_user)

        response = self.client.post(reverse('authentication:reset-password'), {
            'uid': uid,
            'token': token,
            'new_password': 'BrandNewPass789!',
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.client_user.refresh_from_db()
        self.assertTrue(self.client_user.check_password('BrandNewPass789!'))

    def test_reset_password_with_invalid_token_fails(self):
        uid = urlsafe_base64_encode(force_bytes(self.client_user.pk))
        response = self.client.post(reverse('authentication:reset-password'), {
            'uid': uid,
            'token': 'invalid-token',
            'new_password': 'BrandNewPass789!',
        })
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class UserManagementTests(BaseAuthTestCase):
    def test_admin_can_create_client_user(self):
        self.authenticate_as('admin@example.com', 'StrongPass123!')
        response = self.client.post(reverse('authentication:user-list-create'), {
            'email': 'newclient@example.com',
            'first_name': 'New',
            'last_name': 'Client',
        })
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        created = User.objects.get(email='newclient@example.com')
        self.assertEqual(created.role, User.Role.CLIENT)
        self.assertEqual(created.created_by, self.admin)
        self.assertTrue(response.data['generated_password'])

    def test_admin_can_create_another_admin(self):
        self.authenticate_as('admin@example.com', 'StrongPass123!')
        response = self.client.post(reverse('authentication:user-list-create'), {
            'email': 'newadmin@example.com', 'first_name': 'New', 'role': 'admin',
        })
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        created = User.objects.get(email='newadmin@example.com')
        self.assertEqual(created.role, User.Role.ADMIN)
        self.assertTrue(response.data['generated_password'])

    def test_client_cannot_create_users(self):
        self.authenticate_as('client@example.com', 'StrongPass123!')
        response = self.client.post(reverse('authentication:user-list-create'), {
            'email': 'newclient@example.com',
        })
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_client_cannot_list_users(self):
        self.authenticate_as('client@example.com', 'StrongPass123!')
        response = self.client.get(reverse('authentication:user-list-create'))
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_admin_can_deactivate_user(self):
        self.authenticate_as('admin@example.com', 'StrongPass123!')
        url = reverse('authentication:user-detail', kwargs={'pk': self.client_user.pk})
        response = self.client.patch(url, {'is_active': False})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.client_user.refresh_from_db()
        self.assertFalse(self.client_user.is_active)

    def test_admin_can_view_user_login_history(self):
        self.login('client@example.com', 'StrongPass123!')
        self.authenticate_as('admin@example.com', 'StrongPass123!')
        url = reverse('authentication:user-login-history', kwargs={'pk': self.client_user.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(response.data['results']), 1)
