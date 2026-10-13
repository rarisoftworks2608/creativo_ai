from django.test import SimpleTestCase

from apps.creative_generation.layouts import PORTRAIT_4_5, STORY_9_16, layout_for


class LayoutForTests(SimpleTestCase):
    def test_festival_creatives_use_the_festive_style_below_the_subject(self):
        spec = layout_for('festival_creative', 'Diwali')
        self.assertEqual((spec['style'], spec['placement'], spec['aspect']), ('festive', 'below', PORTRAIT_4_5))

    def test_a_brief_with_the_festive_template_labels_is_festive_whatever_the_type(self):
        self.assertEqual(layout_for('post', 'Festival: Diwali')['style'], 'festive')

    def test_text_goes_below_for_most_types_and_at_the_top_for_the_ones_that_carry_more_copy(self):
        for creative_type in ('post', 'carousel', 'product_creative', 'story', 'instagram_post', 'unknown'):
            self.assertEqual(layout_for(creative_type)['placement'], 'below', creative_type)
        for creative_type in ('promotional_creative', 'event_creative', 'announcement_creative', 'educational_creative', 'testimonial_creative'):
            self.assertEqual(layout_for(creative_type)['placement'], 'top', creative_type)

    def test_only_stories_are_nine_by_sixteen(self):
        self.assertEqual(layout_for('story')['aspect'], STORY_9_16)
        self.assertEqual(layout_for('post')['aspect'], PORTRAIT_4_5)
        self.assertEqual(layout_for('promotional_creative')['style'], 'standard')

    def test_a_scene_brief_changes_the_background_but_never_the_text_or_logo_layout(self):
        scene = 'create realistic creative with lord ganesh murti visarjan in sea like lalbaugcha raja'
        for creative_type in ('festival_creative', 'post', 'event_creative', 'story'):
            plain, described = layout_for(creative_type, 'wishes'), layout_for(creative_type, scene)
            self.assertEqual(plain['background'], 'plain', creative_type)
            self.assertEqual(described['background'], 'scene', creative_type)
            for key in ('style', 'placement', 'aspect'):
                self.assertEqual(plain[key], described[key], (creative_type, key))
