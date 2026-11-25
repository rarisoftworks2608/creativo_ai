from django.test import TestCase

from apps.authentication.models import User


class AdminThemeTests(TestCase):
    """The Django admin uses the Studio theme (templates/admin/base_site.html) on every page."""

    def test_login_page_is_branded(self):
        response = self.client.get('/admin/login/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'class="cr-brand"')
        self.assertContains(response, 'Creativo AI')
        self.assertContains(response, '--accent: #ff6b3d')
        self.assertNotContains(response, 'Django administration')

    def test_index_and_change_list_use_the_theme(self):
        admin = User.objects.create_superuser(email='admin@example.com', password='StrongPass123!')
        self.client.force_login(admin)
        for url in ('/admin/', '/admin/activity_log/activitylog/'):
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200, url)
            self.assertContains(response, 'class="cr-brand"')
            self.assertContains(response, '--header-bg: #0c0c0e')
        self.assertContains(self.client.get('/admin/'), 'Data administration')
