from django.test import SimpleTestCase

from apps.creative_generation.layouts import layout_for


class LayoutForTests(SimpleTestCase):
    def test_text_goes_below_for_most_types_and_at_the_top_for_the_ones_that_carry_more_copy(self):
        for creative_type in ('post', 'carousel', 'story', 'product_creative', 'festival_creative', 'instagram_post'):
            self.assertEqual(layout_for(creative_type)['placement'], 'below', creative_type)
        for creative_type in (
            'promotional_creative', 'event_creative', 'announcement_creative', 'educational_creative',
            'testimonial_creative',
        ):
            self.assertEqual(layout_for(creative_type)['placement'], 'top', creative_type)

    def test_a_festival_creative_has_no_layout_of_its_own(self):
        self.assertEqual(layout_for('festival_creative'), layout_for('post'))

    def test_only_stories_are_nine_by_sixteen(self):
        self.assertAlmostEqual(layout_for('story')['aspect'], 16 / 9)
        for creative_type in ('post', 'carousel', 'promotional_creative', 'festival_creative'):
            self.assertAlmostEqual(layout_for(creative_type)['aspect'], 1.25, msg=creative_type)

    def test_the_layout_only_describes_placement_and_size(self):
        self.assertEqual(set(layout_for('post')), {'placement', 'aspect'})
