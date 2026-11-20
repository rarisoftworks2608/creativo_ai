import random

from django.test import SimpleTestCase
from PIL import Image

from apps.creative_generation.art_direction import (
    COMPOSITIONS, DEFAULT_POOL, FAMILIES, FRAMED_PRESETS, STYLE_POOLS, STYLE_PRESETS, UNFRAMED_TYPES, EnergyMap,
    choose_style, composition_for, logo_corners, plan_layout, seeded, style_pool,
)

ALL_CORNERS = ('top_right', 'top_left', 'bottom_right', 'bottom_left')

SIZE = (1024, 1280)
CREAM = (246, 238, 224)
LOGO = (327, 82)


def picture(*busy):
    """A calm cream picture with a patch of high-detail noise (a subject, flowers, lanterns) at each (x, y, w, h)."""
    image = Image.new('RGB', SIZE, CREAM)
    for x, y, w, h in busy:
        image.paste(Image.effect_noise((w, h), 70).convert('RGB'), (x, y))
    return image


def measure(family):
    """A text stack as wide as its family allows (at most 600 px) and 300 px tall."""
    return min(int(SIZE[0] * family.width), 600), 300


def overlaps(a, b):
    return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]


class EnergyMapTests(SimpleTestCase):
    def test_a_busy_patch_scores_far_higher_than_a_calm_one(self):
        energy = EnergyMap(picture((0, 800, 1024, 480)))
        self.assertLess(energy.mean((0, 100, 1024, 700)), 1)
        self.assertGreater(energy.mean((0, 850, 1024, 1250)), 20)

    def test_any_rectangle_even_a_degenerate_or_off_picture_one_has_a_score(self):
        energy = EnergyMap(picture())
        for rect in ((0, 0, 0, 0), (-50, -50, 10, 10), (1000, 1200, 2000, 2000), (5, 5, 6, 6)):
            self.assertGreaterEqual(energy.mean(rect), 0)


class PlanLayoutTests(SimpleTestCase):
    def plan(self, image, rng=None, logo=LOGO, text=True, **kwargs):
        return plan_layout(EnergyMap(image), SIZE, measure=measure if text else None, logo_size=logo, rng=rng, **kwargs)

    def test_a_calm_picture_gets_a_side_aligned_stack_low_down_not_the_centred_template(self):
        plan = self.plan(picture())
        self.assertIn(plan.family.align, ('left', 'right'))
        self.assertEqual(plan.logo_corner, 'top_right')
        self.assertGreater(plan.text_rect[1], SIZE[1] - 300 - 2 * int(SIZE[0] * 0.09))  # low down

    def test_a_centred_stack_is_only_chosen_when_it_is_clearly_the_best(self):
        # Busy on both sides, calm down the middle: only a centred stack fits.
        plan = self.plan(picture((0, 0, 150, 1280), (874, 0, 150, 1280)))
        self.assertEqual(plan.family.name, 'center')
        # On every calm picture, whatever the seed, centred never wins a near-tie.
        for seed in range(30):
            self.assertNotEqual(self.plan(picture(), rng=seeded(seed)).family.name, 'center', seed)

    def test_the_text_moves_off_a_busy_subject(self):
        busy = (0, 800, 1024, 480)  # the whole bottom is busy
        plan = self.plan(picture(busy))
        self.assertFalse(overlaps(plan.text_rect, (0, 830, 1024, 1280)))

    def test_the_logo_is_fixed_top_right_even_when_that_corner_is_busy(self):
        busy_corner = picture((600, 0, 424, 300))
        for seed in [None, *range(10)]:
            plan = self.plan(busy_corner, rng=seeded(seed))
            self.assertEqual(plan.logo_corner, 'top_right', seed)
            self.assertEqual(plan.logo_rect, logo_corners(SIZE, LOGO)['top_right'], seed)

    def test_other_corners_can_still_be_allowed_and_a_busy_one_then_sends_the_logo_to_a_calmer_one(self):
        plan = self.plan(picture((600, 0, 424, 300)), corners_allowed=ALL_CORNERS)
        self.assertEqual(plan.logo_corner, 'top_left')

    def test_a_busy_side_pushes_the_text_to_the_calm_side(self):
        plan = self.plan(picture((0, 0, 400, 1280)))  # a busy left edge, like a tall subject
        self.assertGreater(plan.text_rect[0], 380)

    def test_the_text_follows_the_composition_the_picture_was_asked_to_have(self):
        calm_left_busy_right = picture((560, 0, 464, 1280))
        calm_right_busy_left = picture((0, 0, 464, 1280))
        calm_top_busy_bottom = picture((0, 640, 1024, 640))
        calm_bottom_busy_top = picture((0, 0, 1024, 600))
        for image, composition, test in (
            (calm_left_busy_right, 'left', lambda r: r[2] < 560),
            (calm_right_busy_left, 'right', lambda r: r[0] > 464),
            (calm_top_busy_bottom, 'top', lambda r: r[3] < 640),
            (calm_bottom_busy_top, 'bottom', lambda r: r[1] > 600),
        ):
            for seed in [None, *range(8)]:
                plan = self.plan(image, rng=seeded(seed), prefer=composition)
                self.assertTrue(test(plan.text_rect), (composition, seed, plan.family.name, plan.text_rect))

    def test_a_picture_that_ignored_the_requested_composition_is_laid_out_by_what_it_looks_like(self):
        # Asked for calm space on the left, but the left is busy and the right is calm: the text goes right.
        plan = self.plan(picture((0, 0, 560, 1280)), prefer='left')
        self.assertGreater(plan.text_rect[0], 440)

    def test_the_composition_hint_alone_does_not_pull_the_text_onto_a_busy_area(self):
        for composition in COMPOSITIONS:
            plan = self.plan(picture((0, 800, 1024, 480)), prefer=composition)
            self.assertFalse(overlaps(plan.text_rect, (0, 830, 1024, 1280)), composition)

    def test_the_text_and_the_logo_never_overlap_and_stay_inside_the_picture(self):
        images = [picture(), picture((0, 800, 1024, 480)), picture((600, 0, 424, 300)), picture((0, 0, 400, 1280))]
        for image in images:
            for seed in [None, *range(12)]:
                plan = self.plan(image, rng=seeded(seed))
                x0, y0, x1, y1 = plan.text_rect
                self.assertGreaterEqual(x0, 0)
                self.assertGreaterEqual(y0, 0)
                self.assertLessEqual(x1, SIZE[0])
                self.assertLessEqual(y1, SIZE[1])
                self.assertFalse(overlaps(plan.text_rect, plan.logo_rect), (seed, plan.family.name, plan.logo_corner))

    def test_a_seed_varies_the_layout_between_near_equal_choices_and_is_repeatable(self):
        image = picture()
        plans = {seed: self.plan(image, rng=seeded(seed)) for seed in range(20)}
        layouts = {(plan.family.name, plan.logo_corner) for plan in plans.values()}
        self.assertGreaterEqual(len(layouts), 3)  # centred, left and right layouts all turn up
        self.assertEqual(self.plan(image, rng=seeded(7)), self.plan(image, rng=seeded(7)))

    def test_a_seeded_choice_is_never_a_poor_one(self):
        image = picture((0, 800, 1024, 480))
        for seed in range(20):
            self.assertFalse(overlaps(self.plan(image, rng=seeded(seed)).text_rect, (0, 830, 1024, 1280)), seed)

    def test_no_text_means_a_logo_only_plan_and_no_logo_means_a_text_only_plan(self):
        logo_only = self.plan(picture(), text=False)
        self.assertIsNone(logo_only.text_rect)
        self.assertEqual(logo_only.logo_corner, 'top_right')
        text_only = self.plan(picture(), logo=None)
        self.assertIsNone(text_only.logo_rect)
        self.assertIsNotNone(text_only.text_rect)

    def test_a_stack_too_tall_for_the_picture_still_gets_a_plan(self):
        plan = plan_layout(EnergyMap(picture()), SIZE, measure=lambda family: (600, 1500), logo_size=LOGO)
        self.assertIsNotNone(plan.text_rect)
        self.assertEqual(plan.logo_corner, 'top_right')

    def test_the_text_stays_clear_of_a_header_and_a_footer_it_is_told_about(self):
        for seed in (None, 1, 2, 3, 4, 5):
            plan = self.plan(picture(), rng=seeded(seed), margin_top=300, margin_bottom=500)
            self.assertGreaterEqual(plan.text_rect[1], 300, seed)
            self.assertLessEqual(plan.text_rect[3], SIZE[1] - 500, seed)

    def test_wide_flush_left_and_right_stacks_exist_for_a_two_line_headline(self):
        wide = {family.name: family for family in FAMILIES if family.width >= 0.7 and family.align != 'center'}
        self.assertEqual(set(wide), {'left_wide', 'right_wide'})
        self.assertEqual((wide['left_wide'].align, wide['right_wide'].align), ('left', 'right'))
        # Flush-left beats the centred stack for the same block when both are equally calm.
        plan = plan_layout(EnergyMap(picture()), SIZE, measure=lambda family: (int(SIZE[0] * family.width * 0.95), 300), logo_size=LOGO)
        self.assertNotEqual(plan.family.name, 'center')

    def test_the_logo_corners_are_at_the_standard_margin(self):
        corners = logo_corners(SIZE, LOGO)
        self.assertEqual(corners['top_right'], (1024 - 61 - 327, 61, 1024 - 61, 61 + 82))
        self.assertEqual(set(corners), {'top_right', 'top_left', 'bottom_right', 'bottom_left'})

    def test_every_family_is_available(self):
        self.assertEqual({family.align for family in FAMILIES}, {'center', 'left', 'right'})
        self.assertGreaterEqual(len(FAMILIES), 5)

    def test_the_variations_of_a_request_get_different_compositions_and_requests_start_on_different_ones(self):
        for request_id in range(12):
            self.assertEqual(len({composition_for(request_id, n) for n in (1, 2, 3)}), 3, request_id)
        self.assertEqual({composition_for(request_id, 1) for request_id in range(4)}, set(COMPOSITIONS))
        self.assertEqual(composition_for(5, 2), composition_for(5, 2))


class StyleTests(SimpleTestCase):
    def brand(self, **fields):
        return type('Brand', (), fields)()

    def test_every_preset_is_complete_and_uses_only_known_looks(self):
        for name, preset in STYLE_PRESETS.items():
            self.assertIn(preset['headline'], ('serif', 'brand'), name)
            self.assertIn(preset['weight'], ('regular', 'semibold', 'bold'), name)
            self.assertIn(preset['case'], ('title', 'upper'), name)
            self.assertIn(preset['headline_color'], ('ink', 'accent'), name)
            self.assertIn(preset['kicker'], ('tracked', 'rules', 'bar', 'plain'), name)
            self.assertIsInstance(preset['italic_tail'], bool, name)
            floor = 0.015 if preset.get('body') == 'caps' else 0.02  # a widely spaced sub-line is set smaller
            self.assertTrue(floor < preset['body_size'] < 0.035, name)
            self.assertIn(preset['divider'], ('diamond', 'line', 'dot', 'none'), name)
            self.assertIn(preset['cta'], ('pill', 'outline', 'square', 'underline'), name)
            self.assertTrue(0.045 < preset['size'] < 0.1, name)

    def test_the_presets_are_really_different_from_one_another(self):
        looks = {tuple(sorted(preset.items())) for preset in STYLE_PRESETS.values()}
        self.assertEqual(len(looks), len(STYLE_PRESETS))
        self.assertGreaterEqual(len({preset['cta'] for preset in STYLE_PRESETS.values()}), 4)

    def test_the_web_editorial_preset_is_the_premium_hero_look_a_light_serif_with_an_italic_tail_and_a_quiet_link(self):
        look = STYLE_PRESETS['web_editorial']
        self.assertEqual((look['headline'], look['weight'], look['case']), ('serif', 'regular', 'title'))
        self.assertTrue(look['italic_tail'])
        self.assertEqual((look['kicker'], look['cta'], look['divider']), ('tracked', 'underline', 'none'))

    def test_no_preset_but_the_promotional_one_sets_its_headline_in_bold(self):
        for name, preset in STYLE_PRESETS.items():
            if name != 'bold_sans':
                self.assertNotEqual(preset['weight'], 'bold', name)

    def test_every_pool_only_names_real_presets(self):
        for creative_type, pool in STYLE_POOLS.items():
            self.assertTrue(set(pool) <= set(STYLE_PRESETS), creative_type)

    def test_the_creative_type_sets_the_pool_and_an_unknown_one_gets_every_preset(self):
        self.assertEqual(style_pool('festival_creative', None), list(STYLE_POOLS['festival_creative']))
        self.assertEqual(style_pool('post', None), list(DEFAULT_POOL))
        self.assertEqual(style_pool('', None), list(DEFAULT_POOL))

    def test_the_heavy_preset_is_only_offered_for_promotions_so_everything_else_stays_luxurious(self):
        for creative_type in (*STYLE_POOLS, 'post', 'carousel', 'story'):
            if creative_type != 'promotional_creative':
                self.assertNotIn('bold_sans', style_pool(creative_type, None), creative_type)
        self.assertIn('bold_sans', style_pool('promotional_creative', None))
        # The refined light serif cut is available for the luxury-leaning types.
        self.assertIn('quiet_luxury', style_pool('festival_creative', None))
        self.assertIn('web_editorial', style_pool('post', None))  # the premium web-hero look is in every default pool
        self.assertEqual(STYLE_PRESETS['quiet_luxury']['weight'], 'regular')

    def test_a_luxurious_brand_leans_to_serif_and_a_bold_modern_one_to_sans(self):
        luxe = style_pool('post', self.brand(tone='Elegant, premium and timeless', visual_style='', brand_voice=''))
        self.assertTrue(luxe and all(STYLE_PRESETS[name]['headline'] == 'serif' for name in luxe))
        bold = style_pool('post', self.brand(tone='Bold and energetic', visual_style='modern', brand_voice=''))
        self.assertTrue(bold and all(STYLE_PRESETS[name]['headline'] == 'brand' for name in bold))
        # Both (or neither) kinds of word: no preference.
        mixed = style_pool('post', self.brand(tone='Premium yet bold', visual_style='', brand_voice=''))
        self.assertEqual(mixed, list(DEFAULT_POOL))

    def test_the_poster_presets_are_framed_light_headlines_with_a_sub_line_and_no_heavy_weight(self):
        self.assertEqual(set(FRAMED_PRESETS), {'tech_luxe', 'luxe_frame'})
        for name, preset in STYLE_PRESETS.items():
            self.assertEqual(bool(preset.get('frame')), name in FRAMED_PRESETS, name)
        for name in FRAMED_PRESETS:
            preset = STYLE_PRESETS[name]
            self.assertEqual((preset['weight'], preset['body'], preset['kicker']), ('regular', 'caps', 'tracked'), name)
        self.assertTrue(STYLE_PRESETS['tech_luxe']['accent_words'])      # the closing word of each sentence in the accent colour
        self.assertTrue(STYLE_PRESETS['luxe_frame']['italic_tail'])      # or in italic, in the serif

    def test_a_framed_creative_gets_a_poster_preset_that_suits_the_brand_and_a_greeting_never_does(self):
        tech = self.brand(tone='Warm, confident, innovative, data-focused', visual_style='', brand_voice='')
        self.assertEqual(style_pool('promotional_creative', tech, framed=True), ['tech_luxe'])
        luxe = self.brand(tone='Elegant, premium and timeless', visual_style='', brand_voice='')
        self.assertEqual(style_pool('event_creative', luxe, framed=True), ['luxe_frame'])
        self.assertEqual(set(style_pool('post', None, framed=True)), set(FRAMED_PRESETS))  # no preference: either
        self.assertEqual(choose_style(None, 'promotional_creative', tech, framed=True)[0], 'tech_luxe')
        self.assertEqual(set(UNFRAMED_TYPES), {'festival_creative', 'testimonial_creative'})
        for creative_type in UNFRAMED_TYPES:
            self.assertEqual(style_pool(creative_type, tech, framed=True), style_pool(creative_type, tech), creative_type)
            self.assertFalse(set(style_pool(creative_type, None, framed=True)) & set(FRAMED_PRESETS), creative_type)

    def test_the_poster_presets_are_never_offered_without_a_frame(self):
        for creative_type in (*STYLE_POOLS, 'post', ''):
            for brand in (None, self.brand(tone='innovative digital', visual_style='', brand_voice='')):
                self.assertFalse(set(style_pool(creative_type, brand)) & set(FRAMED_PRESETS), creative_type)

    def test_a_pool_is_never_empty_even_when_the_type_and_the_tone_disagree(self):
        # A festival creative for a bold-modern brand has no sans preset in its own pool: fall back to the sans ones.
        pool = style_pool('festival_creative', self.brand(tone='bold modern', visual_style='', brand_voice=''))
        self.assertTrue(pool)
        self.assertTrue(all(STYLE_PRESETS[name]['headline'] == 'brand' for name in pool))

    def test_the_style_is_seeded_and_without_a_seed_the_first_of_the_pool(self):
        name, _preset = choose_style(None, 'festival_creative', None)
        self.assertEqual(name, STYLE_POOLS['festival_creative'][0])
        self.assertEqual(choose_style(random.Random(4), 'post', None), choose_style(random.Random(4), 'post', None))
        names = {choose_style(random.Random(seed), 'post', None)[0] for seed in range(30)}
        self.assertGreaterEqual(len(names), 4)

    def test_seeded_gives_nothing_for_no_seed(self):
        self.assertIsNone(seeded(None))
        self.assertIsNotNone(seeded(0))  # a seed of zero is still a seed
