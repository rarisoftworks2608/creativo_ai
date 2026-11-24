from django.test import SimpleTestCase

from apps.creative_generation.layouts import layout_for


class LayoutForTests(SimpleTestCase):
    def test_every_type_places_its_text_automatically_on_the_calmest_part_of_the_picture(self):
        for creative_type in (
            'post', 'carousel', 'story', 'product_creative', 'festival_creative', 'instagram_post',
            'promotional_creative', 'event_creative', 'announcement_creative', 'educational_creative',
            'testimonial_creative',
        ):
            self.assertEqual(layout_for(creative_type)['placement'], 'auto', creative_type)

    def test_a_festival_creative_has_no_layout_of_its_own(self):
        self.assertEqual(layout_for('festival_creative'), layout_for('post'))

    def test_only_stories_are_nine_by_sixteen(self):
        self.assertAlmostEqual(layout_for('story')['aspect'], 16 / 9)
        for creative_type in ('post', 'carousel', 'promotional_creative', 'festival_creative'):
            self.assertAlmostEqual(layout_for(creative_type)['aspect'], 1.25, msg=creative_type)

    def test_the_layout_only_describes_placement_size_and_safe_areas(self):
        self.assertEqual(set(layout_for('post')), {'placement', 'aspect', 'ratio', 'safe_top', 'safe_bottom'})

    def test_an_allowed_aspect_ratio_is_used_and_a_disallowed_one_falls_back_to_the_type_default(self):
        self.assertAlmostEqual(layout_for('post', '1:1')['aspect'], 1.0)
        self.assertAlmostEqual(layout_for('post', '1.91:1')['aspect'], 1 / 1.91)
        self.assertEqual(layout_for('story', '1:1')['ratio'], '9:16')  # a story is always vertical
        self.assertEqual(layout_for('carousel', '1.91:1')['ratio'], '4:5')

    def test_only_a_story_keeps_its_text_out_of_the_app_interface_bands(self):
        story = layout_for('story')
        self.assertGreater(story['safe_top'], 0.1)
        self.assertGreater(story['safe_bottom'], 0.15)
        self.assertEqual((layout_for('post')['safe_top'], layout_for('post')['safe_bottom']), (0.0, 0.0))
