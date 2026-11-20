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
        self.assertIn('natural deep focus', prompt)
        self.assertIn('nothing smeared into bokeh', prompt)  # a sharp, cinematic picture, not a blurred stock photo

    def test_the_scene_is_built_in_layers_never_one_object_on_an_empty_backdrop(self):
        prompt = self.prompt()
        for expected in ('never one object on an empty backdrop', 'foreground', 'middle ground', 'distant background', 'skyline'):
            self.assertIn(expected, prompt)

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

    def test_every_type_leaves_a_calm_lit_floor_for_the_text_to_sit_on(self):
        for creative_type in self.ALL_TYPES:
            prompt = self.prompt(creative_type)
            self.assertIn('upper 60% of the frame', prompt, creative_type)
            self.assertIn('lowest 40% shows only the smooth, softly lit floor', prompt, creative_type)  # a real surface, not an empty gradient
            self.assertIn('top-right corner stays calm', prompt, creative_type)
            self.assertIn('centre 8-92% of its height', prompt, creative_type)  # the portrait picture is centre-cropped to 4:5

    def test_each_composition_leaves_a_different_calm_area_and_the_logo_corner_is_always_calm(self):
        left = self.prompt(composition='left')
        self.assertIn('subject and all of its decor sit in the right 55%', left)
        self.assertIn('The left 45% of the frame is calm', left)
        right = self.prompt(composition='right')
        self.assertIn('subject and all of its decor sit in the left 55%', right)
        self.assertIn('The right 45% of the frame is calm', right)
        self.assertIn('top-right corner is part of this calm area', right)
        top = self.prompt(composition='top')
        self.assertIn('lower 60% of the frame', top)
        bottom = self.prompt(composition='bottom')
        self.assertEqual(bottom, self.prompt())  # bottom is the default
        for prompt in (left, right, top, bottom):
            self.assertIn('top-right corner', prompt)  # the logo sits there
            self.assertIn('centre 8-92% of its height', prompt)
        self.assertEqual(len({left, right, top, bottom}), 4)

    def test_the_prompt_asks_for_ultra_sharp_luxurious_detail(self):
        prompt = self.prompt()
        self.assertIn('ultra-high-resolution', prompt)
        self.assertIn('crisp fine detail', prompt)
        self.assertIn('luxurious finish', prompt)

    def test_business_creatives_get_the_dark_rich_luxury_look_and_greetings_and_testimonials_the_warm_bright_one(self):
        for creative_type in ('post', 'promotional_creative', 'product_creative', 'event_creative', 'announcement_creative'):
            prompt = self.prompt(creative_type)
            self.assertIn('dark, rich, low-key luxury grade', prompt, creative_type)
            self.assertIn('luminous accent light', prompt, creative_type)
            self.assertNotIn('never dark or moody', prompt, creative_type)
        for creative_type in ('festival_creative', 'testimonial_creative'):
            prompt = self.prompt(creative_type)
            self.assertIn('bright, airy and never dark or moody', prompt, creative_type)
            self.assertIn('warm golden light', prompt, creative_type)
            self.assertNotIn('low-key', prompt, creative_type)

    def test_a_brand_whose_own_style_is_light_filled_gets_the_light_look_but_a_bright_accent_colour_does_not_count(self):
        airy = self.profile(visual_style='Airy, pastel and light-filled interiors')
        self.assertIn('bright, airy and never dark or moody', self.prompt('promotional_creative', profile=airy))
        accent = BrandProfile.objects.create(
            company=Company.objects.create(name='Orange Co', created_by=self.company.created_by),
            visual_style='Modern, clean layout with warm earthy tones accented by bright orange',
        )
        self.assertIn('dark, rich, low-key luxury grade', self.prompt('promotional_creative', profile=accent))

    def test_the_brand_name_never_goes_into_the_picture_prompt_because_the_model_would_paint_it_on_an_object(self):
        prompt = self.prompt(scene_description='A laptop beside an Acme Retail branded notebook and an ACME RETAIL mug, skyline at dusk')
        self.assertNotIn('acme', prompt.lower())
        self.assertIn('A laptop beside an', prompt)
        self.assertIn('skyline at dusk', prompt)

    def test_every_composition_survives_a_provider_with_a_short_prompt_limit(self):
        profile = self.profile(
            brand_colors=[{'name': 'Primary', 'hex': '#83430B'}], visual_style='v' * 400, tone='t' * 300,
            dos=['d' * 200] * 6, donts=['n' * 200] * 6,
        )
        for composition, expected in (('bottom', 'lowest 40%'), ('top', 'top 40%'), ('left', 'left 45%'), ('right', 'right 45%')):
            cut = self.prompt('post', brief='b ' * 3000, profile=profile, scene_description='s ' * 1000, composition=composition)[:2048]
            self.assertIn(expected, cut, composition)
            self.assertIn('#83430B', cut, composition)

    def test_a_pinned_top_placement_asks_for_a_calm_wall_at_the_top_instead(self):
        from apps.creative_generation.prompts import _composition_sentence

        top = _composition_sentence('top')
        self.assertIn('lower 60% of the frame', top)
        self.assertIn('top 40% is only a calm, evenly lit wall', top)

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
        self.assertIn('lowest 40%', cut)
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
        self.assertIn('Never a lone object on an empty or gradient background', prompt)
        self.assertIn('built in layers', prompt)

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

    def test_the_copy_is_kept_short_and_an_occasion_gets_a_greeting_not_a_sales_pitch(self):
        prompt = self.copy_prompt()
        self.assertIn('at most 8 words', prompt)
        self.assertIn('ONE short sentence (at most 12 words)', prompt)
        self.assertIn('write a greeting, not a sales pitch', prompt)
        self.assertIn('cta an empty string', prompt)
        self.assertIn('never dark or moody', self.copy_prompt('festival_creative'))  # a greeting is warm and bright

    def test_the_scene_is_a_cinematic_location_never_a_tabletop_still_life_and_the_briefs_design_talk_is_ignored(self):
        prompt = self.copy_prompt()
        self.assertIn('cinematic, location-based', prompt)
        self.assertIn('never a tabletop still life of small objects', prompt)
        self.assertIn('a real venue such as a skyline terrace', prompt)  # for a corporate or events brand
        self.assertIn('ignore anything in the brief about layout, typography, text, logos, alignment or website design', prompt)

    def test_the_copy_is_written_for_the_type_hierarchy_a_kicker_of_keywords_and_a_headline_ending_on_the_key_word(self):
        prompt = self.copy_prompt()
        self.assertIn('"Strategy / Technology / Growth"', prompt)
        self.assertIn('two short parallel sentences ("Ideas Into Innovation. Technology Into Growth.")', prompt)
        self.assertIn('is set in emphasis, so end each on the word that carries the idea', prompt)

    def test_the_copy_asks_for_the_poster_fields_two_sentence_headline_a_sub_line_services_and_a_sign_off(self):
        prompt = self.copy_prompt('promotional_creative')
        for expected in (
            'two short parallel sentences', 'small widely spaced capitals like a sub-line', '- highlights:', '"ERP Solutions"',
            '- tagline:', '"Your Technology Partner"', 'an empty array for a greeting or a testimonial',
        ):
            self.assertIn(expected, prompt)

    def test_the_company_services_are_listed_so_the_highlights_come_from_them(self):
        self.assertNotIn('Company services:', self.copy_prompt())
        self.company.services = ['Custom Website Development with Modern CMS', 'Be-spoke ERP & CRM Development Solutions', '']
        prompt = self.copy_prompt()
        self.assertIn('Company services: Custom Website Development with Modern CMS; Be-spoke ERP & CRM Development Solutions', prompt)

    def test_the_scene_light_follows_the_look_and_a_tech_brand_gets_the_podium_and_glass_panels_scene(self):
        business = self.copy_prompt('promotional_creative')
        self.assertIn('low-key light - a deep, dark luxury grade', business)
        self.assertIn('for a software, digital or marketing brand, a dark polished stone podium', business)
        self.assertIn('translucent glass panels of abstract charts', business)
        self.assertIn('shows only abstract charts and shapes, never any writing, numbers or brand marks', business)
        greeting = self.copy_prompt('festival_creative')
        self.assertIn('warm, bright, airy light (never dark or moody)', greeting)

    def test_the_schema_requires_the_services_and_the_sign_off_too(self):
        for field in ('highlights', 'tagline'):
            self.assertIn(field, COPY_SCHEMA['required'])
            self.assertIn(field, COPY_SCHEMA['properties'])
        self.assertEqual(COPY_SCHEMA['properties']['highlights']['type'], 'array')

    def test_the_schema_requires_visual_scene(self):
        self.assertIn('visual_scene', COPY_SCHEMA['required'])
        self.assertIn('visual_scene', COPY_SCHEMA['properties'])
