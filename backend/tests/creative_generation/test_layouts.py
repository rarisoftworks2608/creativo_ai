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

    def test_the_layout_only_describes_placement_and_size(self):
        self.assertEqual(set(layout_for('post')), {'placement', 'aspect'})
