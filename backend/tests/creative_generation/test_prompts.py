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


class FestivePromptTests(TestCase):
    def setUp(self):
        admin = User.objects.create_superuser(email='admin@example.com', password='StrongPass123!')
        self.company = Company.objects.create(name='Acme Retail', industry='Retail', created_by=admin)

    def image_prompt(self, brief='Diwali greeting', profile=None, **kwargs):
        return build_image_prompt(self.company, profile, 'festival_creative', 'instagram', brief, '', 1, 1, **kwargs)

    def test_festival_image_prompt_describes_the_flow_visually(self):
        prompt = self.image_prompt()
        self.assertIn('plain, light cream-ivory background', prompt)
        self.assertIn('One single subject', prompt)
        self.assertIn('golden brass diya', prompt)  # element chosen from the festival, Diwali
        self.assertIn('lowest 40% of the frame is a calm, empty', prompt)
        self.assertIn('top-right corner is empty', prompt)

    def test_festival_image_prompt_never_mentions_lettering_so_the_model_has_nothing_to_paint(self):
        prompt = self.image_prompt('Festival: Diwali\nMain Greeting: Happy Diwali\nWish/Quote: May this Diwali bring light.').lower()
        for word in ('text', 'letter', 'word', 'logo', 'caption', 'greeting', 'wish', 'headline', 'watermark', 'diwali', 'acme'):
            self.assertNotIn(word, prompt, word)

    def test_the_admins_own_festive_element_is_used(self):
        prompt = self.image_prompt('Festival: Diwali\nFestive Element: a hand-painted terracotta lamp')
        self.assertIn('a hand-painted terracotta lamp', prompt)
        self.assertNotIn('golden brass diya', prompt)

    def test_unknown_festival_still_gets_one_iconic_object(self):
        prompt = self.image_prompt('Festival: Hanukkah')
        self.assertIn('one single, beautifully crafted, iconic object that symbolises Hanukkah', prompt)

    def test_festival_image_prompt_fits_cloudflare_flux_and_ignores_the_everyday_brand_style(self):
        from apps.brand.models import BrandProfile
        from apps.creative_generation.image_client import CloudflareImageProvider

        profile = BrandProfile.objects.create(
            company=self.company,
            brand_colors=[{'name': 'Primary', 'hex': '#83430B'}, {'name': 'Secondary', 'hex': '#D97706'}],
            visual_style='professional photography of teams and projects, busy offices',
            tone='Warm and confident', dos=['Show people'] * 8, donts=['Avoid empty space'] * 8,
        )
        prompt = self.image_prompt(profile=profile)
        self.assertLessEqual(len(prompt), CloudflareImageProvider.MAX_PROMPT_CHARS)  # nothing gets truncated away
        self.assertIn('#83430B', prompt)
        self.assertNotIn('teams and projects', prompt)
        self.assertNotIn('Show people', prompt)

    def test_laxmi_prompt_adds_festival_props_around_the_admins_element_and_keeps_it_large(self):
        prompt = self.image_prompt('Festival: Laxmi Pujan\nFestive Element: Elegant golden diya on a subtle lotus')
        self.assertIn('Elegant golden diya on a subtle lotus, with a few gold coins and fresh pink lotus petals', prompt)
        self.assertIn('filling about half the width of the frame', prompt)

    def test_festival_image_prompt_has_no_line_art_ornaments_which_the_model_draws_as_random_squiggles(self):
        prompt = self.image_prompt().lower()
        self.assertNotIn('ornament', prompt)
        self.assertNotIn('line-art', prompt)

    def test_festival_image_prompt_still_appends_admin_guidance(self):
        self.assertIn('Prefer warm gold.', self.image_prompt(extra_guidance='Prefer warm gold.'))

    def test_other_creative_types_get_the_plain_design_not_the_festive_flow(self):
        prompt = build_image_prompt(self.company, None, 'post', 'instagram', 'A brief', '', 1, 1)
        self.assertIn('One single hero subject', prompt)
        self.assertIn('plain, light cream-ivory background', prompt)
        self.assertNotIn('golden brass diya', prompt)

    def test_festival_copy_prompt_asks_for_greeting_name_and_wish_with_no_cta(self):
        prompt = build_copy_prompt(self.company, None, None, 'festival_creative', 'instagram', 'Diwali', '')
        self.assertIn('festive greeting layout', prompt)
        self.assertIn('festival name', prompt)
        self.assertIn('cta: return an empty string', prompt)
        self.assertNotIn('already written', prompt)

    def test_festival_copy_prompt_tells_the_ai_which_wording_is_already_provided(self):
        prompt = build_copy_prompt(
            self.company, None, None, 'festival_creative', 'instagram',
            'Main Greeting: Happy Diwali\nWish/Quote: May this Diwali bring light.', '',
        )
        self.assertIn('already written', prompt)
        self.assertIn('greeting = "Happy Diwali"', prompt)
        self.assertIn('wish = "May this Diwali bring light."', prompt)

    def test_standard_copy_prompt_is_unchanged(self):
        prompt = build_copy_prompt(self.company, None, None, 'post', 'instagram', 'A brief', '')
        self.assertIn('cta: a short, understated call to action', prompt)
        self.assertNotIn('festive greeting layout', prompt)


class PlainPromptTests(TestCase):
    def setUp(self):
        admin = User.objects.create_superuser(email='admin@example.com', password='StrongPass123!')
        self.company = Company.objects.create(name='Acme Retail', products=['Oak sofa', 'Coffee table'], created_by=admin)

    def prompt(self, creative_type, brief='A cosy sofa', **kwargs):
        return build_image_prompt(self.company, None, creative_type, 'instagram', brief, '', 1, 1, **kwargs)

    def test_every_type_asks_for_a_plain_background_one_subject_and_an_empty_corner(self):
        for creative_type in ('post', 'promotional_creative', 'product_creative', 'event_creative', 'testimonial_creative', 'story'):
            prompt = self.prompt(creative_type)
            self.assertIn('plain, light cream-ivory background', prompt, creative_type)
            self.assertIn('One single hero subject', prompt, creative_type)
            self.assertIn('calm, empty, perfectly plain cream area', prompt, creative_type)

    def test_the_empty_area_follows_the_text_placement(self):
        self.assertIn('lowest 40%', self.prompt('post'))
        self.assertIn('top-right corner is empty', self.prompt('post'))
        self.assertIn('The top 40% of the frame', self.prompt('event_creative'))
        self.assertIn('lower-middle', self.prompt('event_creative'))
        self.assertIn('upper-middle', self.prompt('post'))

    def test_the_subject_comes_from_the_type_the_brief_and_the_products(self):
        prompt = self.prompt('product_creative', 'a walnut finish')
        self.assertIn('the product itself, shown whole', prompt)
        self.assertIn('a walnut finish', prompt)
        self.assertIn('Oak sofa, Coffee table', prompt)

    def test_the_company_name_and_layout_words_are_kept_out_of_the_prompt(self):
        prompt = self.prompt('post', brief='').lower()
        for word in ('acme', 'logo', 'headline', 'caption', 'watermark', 'footer'):
            self.assertNotIn(word, prompt, word)

    def test_a_long_brief_still_fits_cloudflare_flux(self):
        from apps.creative_generation.image_client import CloudflareImageProvider

        prompt = self.prompt('promotional_creative', brief='A very detailed description. ' * 80)
        self.assertLessEqual(len(prompt), CloudflareImageProvider.MAX_PROMPT_CHARS)

    def test_admin_guidance_is_still_appended(self):
        self.assertIn('Prefer warm gold.', self.prompt('post', extra_guidance='Prefer warm gold.'))


class ScenePromptTests(TestCase):
    VISARJAN = 'create realistic creative for anant chaturdashi with lord ganesh murti visarjan in sea like lalbaugcha raja'

    def setUp(self):
        admin = User.objects.create_superuser(email='admin@example.com', password='StrongPass123!')
        self.company = Company.objects.create(name='Acme Retail', created_by=admin)

    def prompt(self, creative_type='post', brief=None, **kwargs):
        return build_image_prompt(self.company, None, creative_type, 'instagram', brief or self.VISARJAN, '', 1, 1, **kwargs)

    def test_a_scene_brief_is_followed_not_reduced_to_one_subject_on_a_plain_background(self):
        for creative_type in ('post', 'event_creative', 'product_creative'):
            prompt = self.prompt(creative_type)
            self.assertIn('idol being immersed', prompt, creative_type)
            self.assertIn('open sea with waves', prompt, creative_type)
            self.assertIn('realistic, professionally photographed scene', prompt, creative_type)
            self.assertNotIn('plain, light cream-ivory background', prompt, creative_type)
            self.assertNotIn('simplify', prompt, creative_type)

    def test_a_festival_creative_with_a_scene_brief_makes_that_scene(self):
        prompt = self.prompt('festival_creative')
        self.assertIn('idol being immersed', prompt)
        self.assertIn('open sea with waves', prompt)
        self.assertIn('realistic, professionally photographed scene', prompt)
        self.assertNotIn('plain, light cream-ivory background', prompt)
        self.assertNotIn('One single subject', prompt)

    def test_a_festival_creative_without_a_brief_gets_the_festive_template(self):
        for brief in ('Anant Chaturdashi', 'Ganesh Chaturthi wishes', 'Diwali greeting for our followers'):
            prompt = self.prompt('festival_creative', brief)
            self.assertIn('plain, light cream-ivory background', prompt, brief)
            self.assertIn('One single subject', prompt, brief)
            self.assertNotIn('professionally photographed scene', prompt, brief)
        self.assertIn('handcrafted Lord Ganesha idol', self.prompt('festival_creative', 'Anant Chaturdashi wishes'))

    def test_the_templates_own_wording_is_not_mistaken_for_a_scene(self):
        brief = 'Festival: Diwali\nFestive Element: a hand-painted terracotta lamp with marigold petals and gold coins'
        prompt = self.prompt('festival_creative', brief)
        self.assertIn('One single subject', prompt)
        self.assertNotIn('professionally photographed scene', prompt)

    def test_a_scene_still_keeps_the_text_area_and_the_logo_corner_calm(self):
        below = self.prompt('post')
        self.assertIn('lowest 40% of the frame is calm, simple and uncluttered', below)
        self.assertIn('top-right corner is calm and uncluttered', below)
        self.assertIn('top 40% of the frame is calm, simple and uncluttered', self.prompt('event_creative'))

    def test_brand_colours_and_admin_guidance_are_added_to_a_scene(self):
        from apps.brand.models import BrandProfile

        profile = BrandProfile.objects.create(company=self.company, brand_colors=[{'name': 'Primary', 'hex': '#83430B'}])
        prompt = build_image_prompt(
            self.company, profile, 'post', 'instagram', self.VISARJAN, '', 1, 1, extra_guidance='Golden hour light.',
        )
        self.assertIn('#83430B', prompt)
        self.assertIn('Golden hour light.', prompt)

    def test_a_scene_prompt_fits_cloudflare_flux(self):
        from apps.creative_generation.image_client import CloudflareImageProvider

        self.assertLessEqual(len(self.prompt(brief='A very detailed scene description. ' * 60)), CloudflareImageProvider.MAX_PROMPT_CHARS)
        self.assertLessEqual(len(self.prompt('festival_creative', 'Diwali ' + 'a very detailed scene description. ' * 60)), CloudflareImageProvider.MAX_PROMPT_CHARS)

    def test_short_topics_and_template_briefs_still_get_the_plain_design(self):
        self.assertIn('plain, light cream-ivory background', self.prompt('festival_creative', 'Diwali greeting'))
        self.assertIn('One single subject', self.prompt('festival_creative', 'Festival: Diwali\nFestive Element: a brass lamp'))


class VisualSceneTests(TestCase):
    BRIEF = 'create realistic creative for anant chaturth darshi with lord ganesh murti visrajan in sea like lal baug cha raja'
    AI_SCENE = 'A very large decorated Ganesha idol being immersed into the open sea, waves rising around it, golden evening light'

    def setUp(self):
        admin = User.objects.create_superuser(email='admin@example.com', password='StrongPass123!')
        self.company = Company.objects.create(name='Acme Retail', created_by=admin)

    def image_prompt(self, creative_type='festival_creative', **kwargs):
        return build_image_prompt(self.company, None, creative_type, 'instagram', self.BRIEF, '', 1, 1, **kwargs)

    def test_the_text_ai_s_description_is_what_the_image_model_gets(self):
        prompt = self.image_prompt(scene_description=self.AI_SCENE)
        self.assertIn(self.AI_SCENE, prompt)
        for raw in ('create realistic creative', 'visrajan', 'lal baug cha raja', 'chaturth'):
            self.assertNotIn(raw, prompt, raw)

    def test_without_it_the_cleaned_brief_is_used_so_idol_and_sea_still_reach_the_model(self):
        prompt = self.image_prompt()
        self.assertIn('idol being immersed', prompt)
        self.assertIn('open sea with waves', prompt)
        self.assertNotIn('visrajan', prompt)

    def test_a_blank_description_falls_back_to_the_cleaned_brief(self):
        self.assertIn('open sea with waves', self.image_prompt(scene_description='   '))

    def test_the_description_is_ignored_when_the_brief_is_not_a_scene(self):
        prompt = build_image_prompt(self.company, None, 'festival_creative', 'instagram', 'Diwali', '', 1, 1, scene_description=self.AI_SCENE)
        self.assertNotIn(self.AI_SCENE, prompt)
        self.assertIn('One single subject', prompt)

    def test_the_copy_prompt_asks_for_a_visual_scene_only_for_a_scene_brief(self):
        scene = build_copy_prompt(self.company, None, None, 'festival_creative', 'instagram', self.BRIEF, '')
        self.assertIn('visual_scene: rewrite the creative brief', scene)
        self.assertIn('being immersed into the open sea', scene)  # the worked example for the AI
        for creative_type, brief in (('festival_creative', 'Diwali wishes'), ('post', 'New sofa launch')):
            plain = build_copy_prompt(self.company, None, None, creative_type, 'instagram', brief, '')
            self.assertIn('visual_scene: return an empty string', plain)
            self.assertNotIn('rewrite the creative brief', plain)

    def test_the_schema_requires_visual_scene(self):
        from apps.creative_generation.schemas import COPY_SCHEMA

        self.assertIn('visual_scene', COPY_SCHEMA['properties'])
        self.assertIn('visual_scene', COPY_SCHEMA['required'])
