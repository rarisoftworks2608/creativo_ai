from django.test import SimpleTestCase

from apps.creative_generation.festive import (
    apply_provided_wording, clean_scene_brief, describes_scene, element_for, is_festive_request, names_a_festival, parse_festive_details, props_for, split_greeting,
)

TEMPLATE = """Festival: Diwali
Main Greeting: Happy Diwali
Wish/Quote: May this Diwali bring light, joy and new beginnings.
Festive Element: Elegant golden diya
Brand Logo: [LOGO]"""


class ParseFestiveDetailsTests(SimpleTestCase):
    def test_reads_the_plan_template(self):
        self.assertEqual(parse_festive_details(TEMPLATE), {
            'festival': 'Diwali', 'greeting': 'Happy Diwali',
            'wish': 'May this Diwali bring light, joy and new beginnings.', 'element': 'Elegant golden diya',
        })

    def test_unfilled_placeholders_are_ignored(self):
        self.assertEqual(parse_festive_details('Main Greeting: [GREETING]\nWish/Quote: [WISH OR QUOTE]'), {})

    def test_fields_on_one_line_and_markdown_and_quotes(self):
        details = parse_festive_details('Diwali post **Main Greeting:** Happy Diwali **Wish / Quote:** "Light and joy."')
        self.assertEqual(details, {'greeting': 'Happy Diwali', 'wish': 'Light and joy.'})

    def test_a_free_text_brief_has_no_details(self):
        self.assertEqual(parse_festive_details('Create a Diwali post with a golden diya'), {})
        self.assertEqual(parse_festive_details(''), {})
        self.assertEqual(parse_festive_details(None), {})

    def test_labels_are_case_insensitive_and_do_not_match_inside_words(self):
        self.assertEqual(parse_festive_details('main greeting: Eid Mubarak'), {'greeting': 'Eid Mubarak'})
        self.assertEqual(parse_festive_details('Our wishlist: nothing'), {})


class SplitGreetingTests(SimpleTestCase):
    def test_splits_a_leading_greeting_word(self):
        self.assertEqual(split_greeting('Happy Diwali'), ('Happy', 'Diwali'))
        self.assertEqual(split_greeting('Merry Christmas'), ('Merry', 'Christmas'))
        self.assertEqual(split_greeting('Wishing you a Happy Holi'), ('Wishing you a', 'Happy Holi'))

    def test_a_single_phrase_stays_whole(self):
        self.assertEqual(split_greeting('Eid Mubarak'), ('', 'Eid Mubarak'))
        self.assertEqual(split_greeting('Happy'), ('', 'Happy'))


class ElementForTests(SimpleTestCase):
    def test_admins_element_wins(self):
        self.assertEqual(element_for({'element': 'a paper lantern', 'festival': 'Diwali'}), 'a paper lantern')

    def test_mapped_from_the_festival(self):
        self.assertIn('diya', element_for({'festival': 'Diwali'}))
        self.assertIn('crescent', element_for({}, 'Eid greetings for our customers'))
        self.assertIn('Ganesha', element_for({}, 'Ganesh Chaturthi wishes'))

    def test_no_false_match_inside_other_words(self):
        self.assertIn('iconic festive object suited to the occasion', element_for({}, 'Holistic wellness week'))


class ApplyProvidedWordingTests(SimpleTestCase):
    AI_COPY = {
        'caption': 'c', 'eyebrow': 'CELEBRATE', 'headline': 'Divine Design, Data-Driven Growth',
        'description': 'AI wrote this wish.', 'cta': 'Discover More', 'hashtags': [], 'keywords': [],
    }

    def test_admin_wording_replaces_the_ai_wording(self):
        result = apply_provided_wording(self.AI_COPY, parse_festive_details(TEMPLATE))
        self.assertEqual(result['eyebrow'], 'Happy')
        self.assertEqual(result['headline'], 'Diwali')
        self.assertEqual(result['description'], 'May this Diwali bring light, joy and new beginnings.')
        self.assertEqual(result['caption'], 'c')

    def test_only_what_was_provided_is_replaced(self):
        result = apply_provided_wording(self.AI_COPY, {'wish': 'Light and joy.'})
        self.assertEqual(result['description'], 'Light and joy.')
        self.assertEqual(result['headline'], 'Divine Design, Data-Driven Growth')

    def test_festive_creatives_never_carry_a_cta(self):
        self.assertEqual(apply_provided_wording(self.AI_COPY, {})['cta'], '')


class LakshmiPujanTests(SimpleTestCase):
    BRIEF = (
        'Festival: Laxmi Pujan\nMain Greeting: शुभ लक्ष्मी पूजन\n'
        'Wish/Quote: May Goddess Laxmi bless your home with prosperity.\n'
        'Festive Element: Elegant golden diya on a subtle lotus'
    )

    def test_a_hindi_greeting_is_read_and_kept_whole(self):
        details = parse_festive_details(self.BRIEF)
        self.assertEqual(details['greeting'], 'शुभ लक्ष्मी पूजन')
        self.assertEqual(split_greeting(details['greeting']), ('', 'शुभ लक्ष्मी पूजन'))
        copy = apply_provided_wording({'eyebrow': 'x', 'headline': 'y', 'description': 'z', 'cta': 'w'}, details)
        self.assertEqual(copy['headline'], 'शुभ लक्ष्मी पूजन')

    def test_festival_props_are_added_around_an_element_the_admin_named(self):
        props = props_for(parse_festive_details(self.BRIEF), self.BRIEF)
        self.assertIn('gold coins', props)
        self.assertIn('lotus petals', props)

    def test_no_props_when_there_is_no_admin_element_because_the_built_in_one_has_its_own(self):
        details = parse_festive_details('Festival: Laxmi Pujan')
        self.assertEqual(props_for(details, 'Festival: Laxmi Pujan'), '')
        self.assertIn('Goddess Lakshmi', element_for(details, 'Festival: Laxmi Pujan'))

    def test_diwali_gets_marigold_petals_and_unrelated_festivals_get_nothing(self):
        diwali = parse_festive_details('Festival: Diwali\nFestive Element: a brass lamp')
        self.assertIn('marigold', props_for(diwali))
        eid = parse_festive_details('Festival: Eid\nFestive Element: a lantern')
        self.assertEqual(props_for(eid), '')

    def test_lakshmi_is_matched_before_the_generic_diwali_element(self):
        self.assertIn('Goddess Lakshmi', element_for({}, 'Diwali Lakshmi Puja post'))
        self.assertIn('diya', element_for({}, 'Diwali post'))


class FestiveRecognitionTests(SimpleTestCase):
    def test_the_festival_type_is_always_festive(self):
        self.assertTrue(is_festive_request('festival_creative', 'anything at all'))

    def test_a_brief_written_with_the_template_labels_is_festive_even_on_a_post(self):
        for brief in (
            'Festive Element: a brass idol', 'Festival: Diwali', 'Main Greeting: Happy Diwali',
            'Wish/Quote: Light and joy.', 'Wish / Quote: Light and joy.',
        ):
            self.assertTrue(is_festive_request('post', brief), brief)

    def test_ordinary_briefs_and_bare_words_do_not_switch_the_layout(self):
        for brief in (
            'A product photo of our new sofa', 'Quote: our customers love it', 'Key element: the logo',
            'Our wishlist feature is live', '', None,
        ):
            self.assertFalse(is_festive_request('post', brief), brief)


class NothingIsInventedTests(SimpleTestCase):
    AI = {'caption': 'c', 'eyebrow': 'Warm wishes on', 'headline': 'Diwali', 'description': 'AI wish.', 'cta': 'Explore', 'hashtags': [], 'keywords': []}

    def test_a_brief_with_no_wording_and_no_festival_gets_no_words(self):
        brief = 'Festive Element: a polished brass lamp on a lotus'
        result = apply_provided_wording(self.AI, parse_festive_details(brief), brief)
        self.assertEqual((result['eyebrow'], result['headline'], result['description'], result['cta']), ('', '', '', ''))
        self.assertEqual(result['caption'], 'c')  # the post caption is separate and kept

    def test_naming_the_festival_lets_the_ai_fill_the_greeting_and_wish(self):
        result = apply_provided_wording(self.AI, parse_festive_details('Festival: Diwali'))
        self.assertEqual(result['headline'], 'Diwali')
        self.assertEqual(result['description'], 'AI wish.')

    def test_provided_wording_always_wins(self):
        details = parse_festive_details('Main Greeting: Happy Diwali\nWish/Quote: Light and joy.')
        result = apply_provided_wording(self.AI, details)
        self.assertEqual((result['eyebrow'], result['headline'], result['description']), ('Happy', 'Diwali', 'Light and joy.'))


class DescribesSceneTests(SimpleTestCase):
    VISARJAN = 'create realistic creative for anant chaturdashi with lord ganesh murti visarjan in sea like lalbaugcha raja'

    def test_a_description_of_the_picture_is_a_scene(self):
        self.assertTrue(describes_scene(self.VISARJAN))
        self.assertTrue(describes_scene('create realistic creative for anant chaturth darshi with lord ganesh murti visrajan in sea like lal baug cha raja'))
        self.assertTrue(describes_scene('a family lighting diyas on a balcony at dusk with fairy lights'))
        self.assertTrue(describes_scene('Diwali post with a golden diya, rangoli and string lights around it'))

    def test_a_topic_or_a_festival_name_alone_is_not(self):
        for brief in (
            'Diwali greeting for our followers', 'Anant Chaturdashi', 'Ganesh Chaturthi wishes', 'create a Diwali post',
            'Eid wishes', 'New sofa launch', 'Diwali post with a golden diya', '', None, '   ',
        ):
            self.assertFalse(describes_scene(brief), brief)

    def test_filler_and_the_festival_name_do_not_count_towards_a_description(self):
        self.assertFalse(describes_scene('please create a beautiful realistic premium creative post for ganesh chaturthi wishes'))

    def test_template_briefs_keep_the_plain_design_even_though_they_are_long(self):
        template = (
            'Create a premium, minimal festive social media creative for Laxmi Pujan in Instagram portrait size. '
            'Use a plain, soft light-coloured background such as warm ivory, cream or off-white with a luxurious feel.\n'
            'Festival: Laxmi Pujan\nMain Greeting: Happy Diwali\nWish/Quote: Light and joy.'
        )
        self.assertFalse(describes_scene(template))
        self.assertFalse(describes_scene('Festive Element: a handcrafted brass idol of Goddess Lakshmi seated on a lotus'))

    def test_ganesha_with_an_a_is_recognised_as_the_festival(self):
        self.assertIn('Ganesha idol', element_for({}, 'Lord Ganesha wishes'))
        self.assertTrue(names_a_festival('lord ganesha murti'))


class NothingIsInventedTests(SimpleTestCase):
    AI = {'caption': 'c', 'eyebrow': 'Warm wishes on', 'headline': 'Diwali', 'description': 'AI wish.', 'cta': 'Explore', 'hashtags': [], 'keywords': []}

    def test_a_brief_with_no_wording_and_no_festival_gets_no_words(self):
        brief = 'Festive Element: a polished brass lamp on a lotus'
        result = apply_provided_wording(self.AI, parse_festive_details(brief), brief)
        self.assertEqual((result['eyebrow'], result['headline'], result['description'], result['cta']), ('', '', '', ''))
        self.assertEqual(result['caption'], 'c')  # the post caption is separate and kept

    def test_naming_the_festival_lets_the_ai_fill_the_greeting_and_wish(self):
        result = apply_provided_wording(self.AI, parse_festive_details('Festival: Diwali'))
        self.assertEqual(result['headline'], 'Diwali')
        self.assertEqual(result['description'], 'AI wish.')

    def test_provided_wording_always_wins(self):
        details = parse_festive_details('Main Greeting: Happy Diwali\nWish/Quote: Light and joy.')
        result = apply_provided_wording(self.AI, details)
        self.assertEqual((result['eyebrow'], result['headline'], result['description']), ('Happy', 'Diwali', 'Light and joy.'))


class DescribesSceneTests(SimpleTestCase):
    VISARJAN = 'create realistic creative for anant chaturdashi with lord ganesh murti visarjan in sea like lalbaugcha raja'

    def test_a_free_text_description_is_a_scene(self):
        self.assertTrue(describes_scene(self.VISARJAN))
        self.assertTrue(describes_scene('a family lighting diyas on a balcony at dusk with fairy lights'))

    def test_short_topics_keep_the_plain_design(self):
        for brief in ('Diwali greeting for our followers', 'Eid wishes', 'New sofa launch', '', None, '   '):
            self.assertFalse(describes_scene(brief), brief)

    def test_template_briefs_keep_the_plain_design_even_though_they_are_long(self):
        template = (
            'Create a premium, minimal festive social media creative for Laxmi Pujan in Instagram portrait size. '
            'Use a plain, soft light-coloured background such as warm ivory, cream or off-white with a luxurious feel.\n'
            'Festival: Laxmi Pujan\nMain Greeting: Happy Diwali\nWish/Quote: Light and joy.'
        )
        self.assertFalse(describes_scene(template))
        self.assertFalse(describes_scene('Festive Element: a handcrafted brass idol of Goddess Lakshmi seated on a lotus'))

    def test_a_festival_named_in_free_text_lets_the_ai_write_the_greeting_and_wish(self):
        brief = 'create realistic creative for anant chaturdashi with lord ganesh murti visarjan in sea'
        result = apply_provided_wording(NothingIsInventedTests.AI, parse_festive_details(brief), brief)
        self.assertEqual((result['eyebrow'], result['headline'], result['description']), ('Warm wishes on', 'Diwali', 'AI wish.'))

    def test_a_festival_named_only_by_its_element_is_also_recognised(self):
        brief = 'Festive Element: a handcrafted brass idol of Goddess Lakshmi'
        self.assertEqual(apply_provided_wording(NothingIsInventedTests.AI, parse_festive_details(brief), brief)['description'], 'AI wish.')


class NamesAFestivalTests(SimpleTestCase):
    def test_recognises_festival_names_in_free_text(self):
        for text in ('anant chaturdashi darshi with ganesh murti', 'Ganesh Chaturthi wishes', 'Diwali greetings', 'eid mubarak post', 'Merry Christmas', 'laxmi pujan'):
            self.assertTrue(names_a_festival(text), text)

    def test_ordinary_text_and_look_alike_words_are_not_festivals(self):
        for text in ('a new sofa for your living room', 'Video guide', 'holistic wellness', '', None):
            self.assertFalse(names_a_festival(text), text)


class CleanSceneBriefTests(SimpleTestCase):
    def test_the_visarjan_brief_becomes_idol_and_sea(self):
        cleaned = clean_scene_brief(
            'create realistic creative for anant chaturth darshi with lord ganesh murti visrajan in sea like lal baug cha raja'
        )
        self.assertIn('idol being immersed', cleaned)
        self.assertIn('open sea with waves', cleaned)
        self.assertIn('Lalbaugcha Raja', cleaned)
        self.assertNotIn('create', cleaned)
        self.assertNotIn('murti', cleaned)
        self.assertNotIn('visrajan', cleaned)
        self.assertNotIn('chaturth', cleaned)  # festival names are not drawn

    def test_correct_spellings_give_the_same_result(self):
        self.assertEqual(
            clean_scene_brief('create realistic creative for anant chaturdashi with lord ganesh murti visarjan in sea like lalbaugcha raja'),
            clean_scene_brief('create realistic creative for anant chaturth darshi with lord ganesh murti visrajan in sea like lal baug cha raja'),
        )

    def test_a_brief_that_is_already_a_description_is_left_alone(self):
        text = 'a family lighting diyas on a balcony at dusk with fairy lights'
        self.assertEqual(clean_scene_brief(text), text)

    def test_only_the_leading_instruction_is_removed(self):
        self.assertEqual(clean_scene_brief('Make a premium post for Diwali with rangoli and lamps at home'), 'Diwali with rangoli and lamps at home')
        self.assertEqual(clean_scene_brief(''), '')
        self.assertEqual(clean_scene_brief(None), '')
