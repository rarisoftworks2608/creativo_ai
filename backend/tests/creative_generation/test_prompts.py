from django.test import TestCase

from apps.authentication.models import User
from apps.companies.models import Company
from apps.creative_generation.prompts import build_copy_prompt, build_image_prompt


class ExtraGuidanceTests(TestCase):
    """Epic 21: admin-configured prompt guidance must be appended, not silently
    dropped, and must be a no-op when empty (the common case - most categories
    have no active template configured).
    """

    def setUp(self):
        admin = User.objects.create_superuser(email='admin@example.com', password='StrongPass123!')
        self.company = Company.objects.create(name='Acme Retail', created_by=admin)

    def test_image_prompt_appends_extra_guidance_when_given(self):
        prompt = build_image_prompt(
            self.company, None, 'post', 'instagram', 'A brief', '', 1, 1,
            extra_guidance='Always show marble textures.',
        )
        self.assertIn('ADDITIONAL GUIDANCE (admin-configured):', prompt)
        self.assertIn('Always show marble textures.', prompt)

    def test_image_prompt_omits_section_when_no_guidance(self):
        prompt = build_image_prompt(self.company, None, 'post', 'instagram', 'A brief', '', 1, 1)
        self.assertNotIn('ADDITIONAL GUIDANCE', prompt)

    def test_copy_prompt_appends_extra_guidance_when_given(self):
        prompt = build_copy_prompt(
            self.company, None, None, 'post', 'instagram', 'A brief', '',
            extra_guidance='Never use the word "cheap".',
        )
        self.assertIn('ADDITIONAL GUIDANCE (admin-configured):', prompt)
        self.assertIn('Never use the word "cheap".', prompt)

    def test_copy_prompt_omits_section_when_no_guidance(self):
        prompt = build_copy_prompt(self.company, None, None, 'post', 'instagram', 'A brief', '')
        self.assertNotIn('ADDITIONAL GUIDANCE', prompt)
