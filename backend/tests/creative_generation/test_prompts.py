import datetime
import re

from django.test import TestCase

from apps.authentication.models import User
from apps.brand.models import BrandProfile
from apps.companies.models import Company
from apps.content_calendar.models import ContentCalendarItem
from apps.creative_generation.prompts import build_copy_prompt, build_image_prompt
from apps.creative_generation.schemas import COPY_SCHEMA


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


class ImagePromptTests(TestCase):
    ALL_TYPES = (
        'post', 'carousel', 'story', 'promotional_creative', 'festival_creative', 'product_creative',
        'educational_creative', 'event_creative', 'announcement_creative', 'testimonial_creative',
    )

    def setUp(self):
        admin = User.objects.create_superuser(email='admin@example.com', password='StrongPass123!')
        self.company = Company.objects.create(name='Acme Retail', products=['Oak sofa', 'Coffee table'], created_by=admin)

    def prompt(self, creative_type='post', brief='A cosy living room', profile=None, **kwargs):
        return build_image_prompt(self.company, profile, creative_type, 'instagram', brief, '', 1, 1, **kwargs)

    def profile(self, **fields):
        return BrandProfile.objects.create(company=self.company, **fields)

    def test_every_type_asks_for_a_full_detailed_scene_never_a_plain_backdrop(self):
        for creative_type in self.ALL_TYPES:
            prompt = self.prompt(creative_type)
            self.assertIn('richly detailed environment fills the whole frame edge to edge', prompt, creative_type)
            for banned in ('plain', 'cream', 'single subject', 'single hero', 'minimal'):
                self.assertNotIn(banned, prompt.lower(), f'{creative_type}: {banned}')

    def test_the_prompt_is_written_as_an_editorial_photograph_with_depth(self):
        prompt = self.prompt()
        self.assertIn('premium editorial advertising photograph', prompt)
        self.assertIn('50mm', prompt)
        self.assertIn('softly blurred', prompt)

    def test_the_scene_is_the_text_ais_description_else_the_cleaned_calendar_brief(self):
        written = self.prompt(brief='visrajan in sea lal baug', scene_description='A grand idol being lowered into the sea')
        self.assertIn('A grand idol being lowered into the sea', written)
        self.assertNotIn('visrajan', written)

        fallback = self.prompt(
            brief='Create a post for lakeside sunset yoga retreat. Include the CTA "Book now".', scene_description='  ',
        )
        self.assertIn('lakeside sunset yoga retreat', fallback)
        self.assertNotIn('Create a post', fallback)
        self.assertNotIn('Book now', fallback)  # a CTA is wording, not a picture

    def test_the_calm_areas_follow_the_text_placement(self):
        below = self.prompt('post')
        self.assertIn('upper-middle', below)
        self.assertIn('lowest 35%', below)
        self.assertIn('top-right corner is calm', below)
        top = self.prompt('event_creative')
        self.assertIn('lower-middle', top)
        self.assertIn('top 40%', top)

    def test_the_type_sets_the_mood_and_a_product_creative_falls_back_to_the_companys_products(self):
        self.assertIn('celebratory', self.prompt('festival_creative'))
        self.assertIn('shown whole', self.prompt('product_creative'))
        self.assertIn('Oak sofa, Coffee table', self.prompt('product_creative'))
        self.assertNotIn('Oak sofa', self.prompt('post'))
        self.assertIn('Also: a walnut finish', build_image_prompt(
            self.company, None, 'product_creative', 'instagram', 'A sofa', 'a walnut finish', 1, 1,
        ))

    def test_the_brand_guidelines_shape_the_scene(self):
        profile = self.profile(
            brand_colors=[{'name': 'Primary', 'hex': '#83430B'}, {'name': 'Secondary', 'hex': '#D97706'}],
            visual_style='Warm editorial photography', tone='Calm and confident',
            dos=['Use natural light', 'Show real materials'], donts=['No stock-photo smiles'],
        )
        prompt = self.prompt(profile=profile)
        for expected in (
            '#83430B', '#D97706', 'Warm editorial photography', 'Calm and confident',
            'Use natural light', 'Show real materials', 'No stock-photo smiles',
        ):
            self.assertIn(expected, prompt)

    def test_an_empty_brand_profile_adds_no_brand_lines(self):
        prompt = self.prompt(profile=self.profile())
        for absent in ('Brand palette', 'Brand visual style', 'Brand mood', "Brand do's", "Brand don'ts"):
            self.assertNotIn(absent, prompt)

    def test_the_words_models_paint_into_pictures_are_kept_out(self):
        prompt = self.prompt('post', brief='A cosy living room', profile=self.profile(visual_style='Warm photography')).lower()
        for word in ('text', 'logo', 'lettering', 'caption', 'headline', 'acme'):
            self.assertIsNone(re.search(rf'\b{word}\b', prompt), word)

    def test_the_scene_and_layout_survive_a_provider_with_a_short_prompt_limit(self):
        profile = self.profile(
            brand_colors=[{'name': 'Primary', 'hex': '#83430B'}], visual_style='v' * 400, tone='t' * 300,
            dos=['d' * 200] * 6, donts=['n' * 200] * 6,
        )
        prompt = self.prompt('post', brief='b ' * 3000, profile=profile, scene_description='s ' * 1000)
        cut = prompt[:2048]  # Cloudflare FLUX cuts everything after 2048 characters
        self.assertIn('richly detailed environment', cut)
        self.assertIn('lowest 35%', cut)
        self.assertIn('#83430B', cut)


class CopyPromptTests(TestCase):
    def setUp(self):
        admin = User.objects.create_superuser(email='admin@example.com', password='StrongPass123!')
        self.company = Company.objects.create(name='Acme Retail', created_by=admin)

    def copy_prompt(self, creative_type='post', brief='A brief', calendar_item=None):
        return build_copy_prompt(
            self.company, None, None, creative_type, 'instagram', brief, '', calendar_item=calendar_item,
        )

    def item(self, **fields):
        return ContentCalendarItem.objects.create(
            company=self.company, topic='Summer Launch', content_type='Static Post', platforms=['instagram'],
            scheduled_date=datetime.date(2026, 6, 1), **fields,
        )

    def test_every_type_gets_the_same_copy_roles_and_always_a_visual_scene(self):
        for creative_type in ('post', 'festival_creative', 'event_creative'):
            prompt = self.copy_prompt(creative_type)
            self.assertIn('cta: a short, understated call to action', prompt, creative_type)
            self.assertIn('visual_scene: ONE clear, concrete English description', prompt, creative_type)
            self.assertIn('richly detailed scene', prompt, creative_type)
            self.assertNotIn('festive greeting layout', prompt, creative_type)

    def test_the_scene_is_set_in_the_companys_world(self):
        self.company.industry = 'Real Estate'
        prompt = self.copy_prompt()
        self.assertIn('(industry: Real Estate)', prompt)
        self.assertIn('Set it in a world that suits the business and its audience', prompt)

    def test_the_calendar_entrys_planning_details_are_part_of_the_instruction(self):
        prompt = self.copy_prompt(calendar_item=self.item(
            category='Seasonal', weekly_theme='Community', objective='Brand awareness', campaign='Summer 2026',
        ))
        self.assertIn('Content calendar entry (follow it closely):', prompt)
        for expected in (
            '- Category: Seasonal', '- Weekly theme: Community', '- Objective: Brand awareness',
            '- Campaign: Summer 2026', '- Scheduled for: 01 June 2026',
        ):
            self.assertIn(expected, prompt)

    def test_an_ad_hoc_generation_or_no_calendar_item_adds_no_calendar_lines(self):
        self.assertNotIn('Content calendar entry', self.copy_prompt())
        ad_hoc = self.item(source=ContentCalendarItem.Source.AD_HOC)
        self.assertNotIn('Content calendar entry', self.copy_prompt(calendar_item=ad_hoc))

    def test_the_schema_requires_visual_scene(self):
        self.assertIn('visual_scene', COPY_SCHEMA['required'])
        self.assertIn('visual_scene', COPY_SCHEMA['properties'])
