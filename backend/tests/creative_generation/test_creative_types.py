"""The six creative types as six distinct systems: each type's own inputs, copy rules, picture direction, size,
typography and workflow (carousel slides, per-image regeneration, free text edits, download). All AI providers are
fakes - nothing here calls a real API."""

import io
import zipfile
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase
from django.urls import reverse
from PIL import Image, ImageStat
from rest_framework import status

from apps.creative_generation import creative_types
from apps.creative_generation.image_client import closest_ratio, GEMINI_RATIOS, openai_size
from apps.creative_generation.models import GenerationRequest, GenerationVariation
from apps.creative_generation.prompts import build_copy_prompt, build_image_prompt
from apps.creative_generation.tasks import carousel_slides
from apps.publishing.media import resolve_content

from .test_creative_generation import COPY_RESULT, BaseCreativeGenerationTestCase, FakeImageProvider, FakeTextProvider


def png_bytes(size=(120, 150), color='teal'):
    buffer = io.BytesIO()
    Image.new('RGB', size, color=color).save(buffer, format='PNG')
    return buffer.getvalue()


class RecordingImageProvider(FakeImageProvider):
    """Records each prompt and the shape asked for."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.calls = []

    def generate_image(self, *, prompt, reference_images=None, aspect=None):
        self.calls.append({'prompt': prompt, 'aspect': aspect})
        return png_bytes(), 'image/png'


class RecordingTextProvider(FakeTextProvider):
    def __init__(self, result=None):
        super().__init__(result)
        self.prompts = []

    def generate_json(self, *, system, prompt, json_schema):
        self.prompts.append(prompt)
        return super().generate_json(system=system, prompt=prompt, json_schema=json_schema)


CAROUSEL_RESULT = {
    'caption': 'Five signs it is time.', 'series_look': 'a sunlit modern studio in teal and amber',
    'hashtags': ['#web'], 'keywords': ['website'],
    'slides': [
        {'role': 'cover', 'headline': '5 Signs Your Website Needs an Upgrade', 'body': 'Swipe to check', 'cta': '', 'visual_scene': 'a laptop on an oak desk'},
        {'role': 'content', 'headline': 'It Looks Outdated', 'body': 'Design affects trust.', 'cta': '', 'visual_scene': 'an old monitor'},
        {'role': 'content', 'headline': 'It Is Slow', 'body': 'Speed is experience.', 'cta': '', 'visual_scene': 'a stopwatch'},
        {'role': 'content', 'headline': 'Not Mobile Friendly', 'body': 'Phones come first.', 'cta': '', 'visual_scene': 'a phone in hand'},
        {'role': 'cta', 'headline': "Let's Build Something Better", 'body': '', 'cta': 'Contact Us', 'visual_scene': 'a team at work'},
    ],
}


# --------------------------------------------------------------------------- pure rules


class LockedCopyTests(SimpleTestCase):
    def test_a_post_or_story_shows_the_typed_headline_text_and_cta_exactly(self):
        fields = {'headline': 'Your Website Is Your First Impression.', 'supporting_text': 'Stand out.', 'cta': "Let's Build Yours"}
        self.assertEqual(
            creative_types.locked_copy('post', fields),
            {'headline': 'Your Website Is Your First Impression.', 'description': 'Stand out.', 'cta': "Let's Build Yours"},
        )
        self.assertEqual(creative_types.locked_copy('story', {'headline': 'Ready?'}), {'headline': 'Ready?'})

    def test_a_festival_greets_by_the_occasion_and_has_no_sales_cta(self):
        locked = creative_types.locked_copy('festival_creative', {'festival': 'diwali', 'year': '2026'})
        self.assertEqual(locked['eyebrow'], 'Happy Diwali 2026')
        self.assertEqual(locked['cta'], '')
        custom = creative_types.locked_copy('festival_creative', {'festival': 'custom', 'festival_name': 'Founders Day'})
        self.assertEqual(custom['eyebrow'], 'Happy Founders Day')

    def test_an_announcement_label_carries_the_category_and_the_supplied_date(self):
        locked = creative_types.locked_copy(
            'announcement_creative', {'category': 'service_launch', 'title': 'Introducing Our AI Solutions', 'date': '12 Dec'},
        )
        self.assertEqual(locked['eyebrow'], 'NEW SERVICE / 12 Dec')
        self.assertEqual(locked['headline'], 'Introducing Our AI Solutions')
        own_label = creative_types.locked_copy('announcement_creative', {'category': 'custom', 'title': 'x', 'label': 'BIG NEWS'})
        self.assertEqual(own_label['eyebrow'], 'BIG NEWS')

    def test_a_testimonial_never_invents_a_name_a_company_or_a_rating(self):
        locked = creative_types.locked_copy('testimonial_creative', {'quote': 'Great work.'})
        self.assertEqual(locked['headline'], 'Great work.')
        self.assertEqual(locked['description'], '')  # no name supplied: none shown
        self.assertEqual(locked['cta'], '')
        self.assertIsNone(creative_types.rating_value({'quote': 'Great work.'}))
        full = creative_types.locked_copy('testimonial_creative', {
            'quote': 'Great work.', 'customer_name': 'Rahul Sharma', 'designation': 'Founder', 'company': 'ABC Enterprises',
        })
        self.assertEqual(full['description'], 'Rahul Sharma, Founder, ABC Enterprises')

    def test_a_testimonial_quote_is_only_handed_to_the_ai_when_shortening_was_allowed(self):
        locked = creative_types.locked_copy('testimonial_creative', {'quote': 'Long quote', 'allow_shorten': True})
        self.assertNotIn('headline', locked)

    def test_only_a_real_one_to_five_rating_draws_stars(self):
        self.assertEqual(creative_types.rating_value({'rating': 4}), 4)
        for value in (0, 6, 'five', None):
            self.assertIsNone(creative_types.rating_value({'rating': value}), value)

    def test_each_type_offers_its_own_sizes(self):
        self.assertEqual(creative_types.resolve_aspect_ratio('story', '4:5'), '9:16')
        self.assertEqual(creative_types.resolve_aspect_ratio('post', '1:1'), '1:1')
        self.assertEqual(creative_types.default_aspect_ratio('testimonial_creative'), '4:5')

    def test_a_design_style_chooses_the_typography_but_a_testimonial_keeps_its_quote_style(self):
        self.assertEqual(creative_types.presets_for('post', 'bold'), ('bold_sans', 'modern_caps'))
        self.assertEqual(creative_types.presets_for('testimonial_creative', 'bold'), ('testimonial_quote',))
        self.assertEqual(creative_types.picture_look('post', 'minimal'), 'light')
        self.assertEqual(creative_types.picture_look('testimonial_creative', 'cinematic'), 'light')


class CarouselSlidesTests(SimpleTestCase):
    def test_roles_run_cover_content_cta_and_the_typed_cta_wins(self):
        slides = carousel_slides(CAROUSEL_RESULT, {'cta': 'Book a call'}, 5)
        self.assertEqual([s['role'] for s in slides], ['cover', 'content', 'content', 'content', 'cta'])
        self.assertEqual(slides[-1]['cta'], 'Book a call')
        self.assertTrue(all(s['cta'] == '' for s in slides[:-1]))

    def test_an_outline_for_the_middle_slides_keeps_its_wording(self):
        outline = 'Looks outdated | Design affects trust\nSlow loading\nNot mobile friendly | Phones first'
        slides = carousel_slides(CAROUSEL_RESULT, {'outline': outline}, 5)
        self.assertEqual([s['headline'] for s in slides[1:4]], ['Looks outdated', 'Slow loading', 'Not mobile friendly'])
        self.assertEqual(slides[1]['body'], 'Design affects trust')
        self.assertEqual(slides[0]['headline'], '5 Signs Your Website Needs an Upgrade')  # the cover stays the AI's hook

    def test_a_response_without_slides_still_gives_a_cover(self):
        slides = carousel_slides(COPY_RESULT, {}, 5)
        self.assertEqual(len(slides), 1)
        self.assertEqual(slides[0]['headline'], COPY_RESULT['headline'])


class ImageSizeTests(SimpleTestCase):
    def test_openai_draws_the_nearest_of_its_three_sizes(self):
        self.assertEqual(openai_size(16 / 9), '1024x1536')
        self.assertEqual(openai_size(1.25), '1024x1536')
        self.assertEqual(openai_size(1.0), '1024x1024')
        self.assertEqual(openai_size(1 / 1.91), '1536x1024')
        self.assertIsNone(openai_size(None))

    def test_gemini_is_asked_for_the_nearest_ratio_it_supports(self):
        self.assertEqual(closest_ratio(16 / 9, GEMINI_RATIOS), '9:16')
        self.assertEqual(closest_ratio(1.25, GEMINI_RATIOS), '4:5')
        self.assertEqual(closest_ratio(1 / 1.91, GEMINI_RATIOS), '16:9')


# --------------------------------------------------------------------------- prompts


class TypePromptTests(BaseCreativeGenerationTestCase):
    def image_prompt(self, creative_type, **kwargs):
        return build_image_prompt(self.company, None, creative_type, 'instagram', 'A brief', '', 1, 1, **kwargs)

    def copy_prompt(self, creative_type, **kwargs):
        return build_copy_prompt(self.company, None, None, creative_type, 'instagram', 'A brief', '', **kwargs)

    def test_a_festival_picture_uses_that_occasions_own_imagery(self):
        diwali = self.image_prompt('festival_creative', brief_fields={'festival': 'diwali'})
        self.assertIn('diyas', diwali)
        holi = self.image_prompt('festival_creative', brief_fields={'festival': 'holi'})
        self.assertIn('colour powder', holi)
        self.assertNotIn('diyas', holi)
        custom = self.image_prompt('festival_creative', brief_fields={'festival': 'custom', 'festival_name': 'Baisakhi'})
        self.assertIn('Baisakhi', custom)
        self.assertIn('respectful', custom)

    def test_an_announcement_picture_follows_its_category(self):
        hiring = self.image_prompt('announcement_creative', brief_fields={'category': 'hiring', 'title': 'x'})
        opening = self.image_prompt('announcement_creative', brief_fields={'category': 'opening', 'title': 'x'})
        self.assertIn('workplace and the people', hiring)
        self.assertIn('storefront', opening)

    def test_a_story_is_framed_vertically_and_follows_its_objective(self):
        prompt = self.image_prompt('story', aspect_ratio='9:16', brief_fields={'objective': 'poll_question'})
        self.assertIn('tall vertical 9:16', prompt)
        self.assertIn('poll sticker', prompt)
        self.assertNotIn('portrait 4:5', prompt)

    def test_a_testimonial_background_is_quiet_and_has_no_people(self):
        prompt = self.image_prompt('testimonial_creative', brief_fields={'quote': 'x'})
        self.assertIn('no people', prompt)
        self.assertNotIn('smiling people', prompt)

    def test_a_design_style_shapes_the_picture(self):
        self.assertIn('cinematic art direction', self.image_prompt('post', design_style='cinematic'))
        self.assertNotIn('art direction:', self.image_prompt('post'))

    def test_the_copy_prompt_carries_the_type_rules_and_the_exact_text(self):
        prompt = self.copy_prompt('post', brief_fields={'headline': 'Your Website Is Your First Impression.'})
        self.assertIn('CREATIVE TYPE: Post', prompt)
        self.assertIn('Headline (use exactly as written): Your Website Is Your First Impression.', prompt)
        testimonial = self.copy_prompt('testimonial_creative', brief_fields={'quote': 'They were brilliant.'})
        self.assertIn('Client quote (verbatim): "They were brilliant."', testimonial)
        self.assertIn('never invent', testimonial)


# --------------------------------------------------------------------------- the API and the task


@patch('apps.creative_generation.tasks.get_text_provider')
@patch('apps.creative_generation.tasks.get_image_provider')
class CreativeTypeApiTests(BaseCreativeGenerationTestCase):
    def setUp(self):
        super().setUp()
        self.image = RecordingImageProvider()
        self.text = RecordingTextProvider()

    def wire(self, mock_get_image, mock_get_text, text_result=None):
        if text_result is not None:
            self.text = RecordingTextProvider(text_result)
        mock_get_image.return_value = self.image
        mock_get_text.return_value = self.text

    def url(self, name, **kwargs):
        return reverse(f'creative_generation:{name}', kwargs={'company_id': self.company.pk, **kwargs})

    def test_options_describe_every_type(self, mock_get_image, mock_get_text):
        self.authenticate_as('admin@example.com', 'StrongPass123!')
        data = self.client.get(self.url('options')).data
        self.assertEqual(
            [t['value'] for t in data['types']],
            ['post', 'carousel', 'story', 'festival_creative', 'announcement_creative', 'testimonial_creative'],
        )
        self.assertIn('diwali', [f['value'] for f in data['festivals']])

    def test_a_testimonial_without_a_quote_is_refused(self, mock_get_image, mock_get_text):
        self.wire(mock_get_image, mock_get_text)
        response = self.create_request(creative_type='testimonial_creative', brief_fields={'customer_name': 'Rahul'})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('quote', str(response.data))
        self.assertEqual(self.image.calls, [])

    def test_required_inputs_size_style_and_slide_count_are_validated(self, mock_get_image, mock_get_text):
        self.wire(mock_get_image, mock_get_text)
        for payload, field in (
            ({'creative_type': 'announcement_creative', 'brief_fields': {'category': 'milestone'}}, 'brief_fields'),
            ({'creative_type': 'story', 'aspect_ratio': '4:5'}, 'aspect_ratio'),
            ({'creative_type': 'post', 'design_style': 'grunge'}, 'design_style'),
            ({'creative_type': 'carousel', 'slide_count': 12, 'brief_fields': {'topic': 'x'}}, 'slide_count'),
            ({'creative_type': 'testimonial_creative', 'brief_fields': {'quote': 'x', 'rating': 9}}, 'brief_fields'),
        ):
            response = self.create_request(**payload)
            self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST, payload)
            self.assertIn(field, response.data, payload)

    def test_a_post_is_drawn_at_its_size_and_shows_the_typed_text_exactly(self, mock_get_image, mock_get_text):
        self.wire(mock_get_image, mock_get_text)
        with patch('apps.creative_generation.tasks.compose_creative', return_value=(png_bytes(), 'image/png')) as compose:
            response = self.create_request(
                creative_type='post', variation_count=1, include_text_overlay=True, aspect_ratio='1:1',
                design_style='bold', brief_fields={'headline': 'Your Website Is Your First Impression.', 'cta': "Let's Build Yours"},
            )
        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED, response.data)
        kwargs = compose.call_args.kwargs
        self.assertEqual(kwargs['headline'], 'Your Website Is Your First Impression.')
        self.assertEqual(kwargs['cta'], "Let's Build Yours")
        self.assertEqual(kwargs['description'], COPY_RESULT['description'])  # left blank: the AI writes it
        self.assertAlmostEqual(kwargs['aspect'], 1.0)
        self.assertTrue(kwargs['exact_aspect'])
        self.assertEqual(kwargs['style_presets'], ('bold_sans', 'modern_caps'))
        self.assertAlmostEqual(self.image.calls[0]['aspect'], 1.0)
        self.assertIn('square 1:1', self.image.calls[0]['prompt'])

    def test_a_story_keeps_out_of_the_app_bands(self, mock_get_image, mock_get_text):
        self.wire(mock_get_image, mock_get_text)
        with patch('apps.creative_generation.tasks.compose_creative', return_value=(png_bytes(), 'image/png')) as compose:
            self.create_request(creative_type='story', variation_count=1, brief_fields={'objective': 'offer'})
        kwargs = compose.call_args.kwargs
        self.assertAlmostEqual(kwargs['aspect'], 16 / 9)
        self.assertGreater(kwargs['safe_top'], 0)
        self.assertGreater(kwargs['safe_bottom'], 0)

    def test_a_testimonial_shows_the_real_quote_attribution_and_rating_only(self, mock_get_image, mock_get_text):
        # The AI tries to invent an attribution - it must not reach the creative.
        self.wire(mock_get_image, mock_get_text, {**COPY_RESULT, 'headline': 'Made-up praise', 'description': 'Jane Doe, CEO'})
        photo = SimpleUploadedFile('rahul.png', png_bytes((200, 200), 'orange'), content_type='image/png')
        self.authenticate_as('admin@example.com', 'StrongPass123!')
        with patch('apps.creative_generation.tasks.compose_creative', return_value=(png_bytes(), 'image/png')) as compose:
            response = self.client.post(
                self.url('request-list-create'),
                {
                    'creative_type': 'testimonial_creative', 'variation_count': 1,
                    'brief_fields': '{"quote": "The team understood our vision.", "customer_name": "Rahul Sharma", "rating": 5}',
                    'customer_photo': photo,
                },
                format='multipart',
            )
        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED, response.data)
        kwargs = compose.call_args.kwargs
        self.assertEqual(kwargs['headline'], 'The team understood our vision.')
        self.assertEqual(kwargs['description'], 'Rahul Sharma')
        self.assertEqual(kwargs['eyebrow'], 'What our clients say')
        self.assertEqual(kwargs['rating'], 5)
        self.assertIsNotNone(kwargs['portrait_bytes'])
        self.assertEqual(kwargs['highlights'], [])  # a testimonial is never dressed as a services poster
        request = GenerationRequest.objects.get(pk=response.data['id'])
        self.assertTrue(request.include_text_overlay)  # the quote IS the creative

    def test_a_carousel_is_planned_once_and_drawn_slide_by_slide(self, mock_get_image, mock_get_text):
        self.wire(mock_get_image, mock_get_text, CAROUSEL_RESULT)
        with patch('apps.creative_generation.tasks.compose_creative', return_value=(png_bytes(), 'image/png')) as compose:
            response = self.create_request(
                creative_type='carousel', slide_count=5, variation_count=3,
                brief_fields={'topic': '5 signs your website needs an upgrade', 'cta': 'Book a call'},
            )
        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED, response.data)
        request = GenerationRequest.objects.get(pk=response.data['id'])
        self.assertEqual(request.status, GenerationRequest.Status.SUCCEEDED)
        self.assertEqual(len(self.text.prompts), 1)  # one plan for the whole series
        self.assertIn('exactly 5 slides', self.text.prompts[0])
        slides = list(request.variations.order_by('variation_number'))
        self.assertEqual(len(slides), 5)  # five individual images, not one image of five panels
        self.assertEqual(len(self.image.calls), 5)
        self.assertEqual([s.slide_role for s in slides], ['cover', 'content', 'content', 'content', 'cta'])
        self.assertEqual([s.eyebrow for s in slides], ['', '02 / 05', '03 / 05', '04 / 05', '05 / 05'])
        self.assertEqual(slides[-1].cta, 'Book a call')
        calls = compose.call_args_list
        self.assertEqual(len({c.kwargs['style_seed'] for c in calls}), 1)       # one typography for the series
        self.assertEqual(len({c.kwargs['variation_seed'] for c in calls}), 5)   # each slide laid out for its picture
        self.assertGreater(len({c.kwargs['composition'] for c in calls}), 1)
        self.assertEqual(calls[0].kwargs['headline_scale'], 1.0)                 # the cover is the strongest slide
        self.assertLess(calls[1].kwargs['headline_scale'], 1.0)
        for call in self.image.calls:
            self.assertIn('sunlit modern studio', call['prompt'])                # the shared series look
        self.assertEqual(request.generation_context['series_look'], CAROUSEL_RESULT['series_look'])

        post_type, media, _caption = resolve_content(request.content_calendar_item)
        self.assertEqual(post_type, 'carousel')
        self.assertEqual(len(media), 5)

    def test_a_calendar_carousel_without_a_slide_count_gets_at_least_three_slides(self, mock_get_image, mock_get_text):
        self.wire(mock_get_image, mock_get_text, CAROUSEL_RESULT)
        request = GenerationRequest.objects.create(
            company=self.company, content_calendar_item=self.calendar_item, creative_type='carousel', variation_count=1,
            include_text_overlay=True,
        )
        from apps.creative_generation.tasks import generate_creative_variations

        generate_creative_variations.delay(request.id)
        self.assertEqual(request.variations.count(), 3)

    def test_editing_the_text_re_renders_the_kept_picture_without_an_ai_call(self, mock_get_image, mock_get_text):
        self.wire(mock_get_image, mock_get_text)
        response = self.create_request(creative_type='post', variation_count=1, include_text_overlay=True, brief_fields={'topic': 'x'})
        request = GenerationRequest.objects.get(pk=response.data['id'])
        variation = request.variations.get()
        self.assertTrue(variation.background)
        calls_before = len(self.image.calls)
        with patch('apps.creative_generation.tasks.compose_creative', return_value=(png_bytes(), 'image/png')) as compose:
            edited = self.client.patch(
                self.url('variation-edit', pk=request.pk, variation_id=variation.pk), {'headline': 'Fixed Spelling'}, format='json',
            )
        self.assertEqual(edited.status_code, status.HTTP_200_OK, edited.data)
        self.assertEqual(compose.call_args.kwargs['headline'], 'Fixed Spelling')
        self.assertEqual(len(self.image.calls), calls_before)  # no new picture, no credit used
        variation.refresh_from_db()
        self.assertEqual(variation.headline, 'Fixed Spelling')

    def test_an_old_creative_without_its_picture_can_only_have_its_caption_edited(self, mock_get_image, mock_get_text):
        self.wire(mock_get_image, mock_get_text)
        response = self.create_request(creative_type='post', variation_count=1)
        request = GenerationRequest.objects.get(pk=response.data['id'])
        variation = request.variations.get()
        variation.background = None
        variation.save(update_fields=['background'])
        url = self.url('variation-edit', pk=request.pk, variation_id=variation.pk)
        self.assertEqual(self.client.patch(url, {'headline': 'x'}, format='json').status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(self.client.patch(url, {'caption': 'New caption'}, format='json').status_code, status.HTTP_200_OK)

    def test_one_slide_can_be_regenerated_and_keeps_its_copy(self, mock_get_image, mock_get_text):
        self.wire(mock_get_image, mock_get_text, CAROUSEL_RESULT)
        response = self.create_request(creative_type='carousel', slide_count=5, brief_fields={'topic': 'x'})
        request = GenerationRequest.objects.get(pk=response.data['id'])
        slide = request.variations.get(variation_number=3)
        calls_before = len(self.image.calls)
        regenerated = self.client.post(self.url('variation-regenerate', pk=request.pk, variation_id=slide.pk))
        self.assertEqual(regenerated.status_code, status.HTTP_202_ACCEPTED, regenerated.data)
        self.assertEqual(len(self.image.calls), calls_before + 1)  # exactly one new picture
        self.assertIn('Slide 3 of 5', self.image.calls[-1]['prompt'])
        slide.refresh_from_db()
        self.assertEqual(slide.status, GenerationVariation.Status.READY)
        self.assertEqual(slide.headline, 'It Is Slow')
        self.assertEqual(slide.render_params['attempt'], 1)
        self.assertEqual(request.variations.count(), 5)

    def test_a_client_cannot_edit_or_regenerate(self, mock_get_image, mock_get_text):
        self.wire(mock_get_image, mock_get_text)
        response = self.create_request(creative_type='post', variation_count=1)
        request = GenerationRequest.objects.get(pk=response.data['id'])
        variation = request.variations.get()
        self.authenticate_as('acmeclient@example.com', 'StrongPass123!')
        edit = self.client.patch(self.url('variation-edit', pk=request.pk, variation_id=variation.pk), {'headline': 'x'}, format='json')
        regen = self.client.post(self.url('variation-regenerate', pk=request.pk, variation_id=variation.pk))
        self.assertEqual(edit.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(regen.status_code, status.HTTP_403_FORBIDDEN)

    def test_every_image_downloads_as_one_zip(self, mock_get_image, mock_get_text):
        self.wire(mock_get_image, mock_get_text, CAROUSEL_RESULT)
        response = self.create_request(creative_type='carousel', slide_count=5, brief_fields={'topic': 'x'})
        download = self.client.get(self.url('request-download', pk=response.data['id']))
        self.assertEqual(download.status_code, status.HTTP_200_OK)
        names = zipfile.ZipFile(io.BytesIO(download.content)).namelist()
        self.assertEqual(len(names), 5)
        self.assertTrue(names[0].startswith('slide_01'))

    def test_a_request_that_cannot_be_queued_leaves_nothing_behind(self, mock_get_image, mock_get_text):
        from apps.content_calendar.models import ContentCalendarItem

        self.wire(mock_get_image, mock_get_text)
        items_before = ContentCalendarItem.objects.count()
        with patch('apps.creative_generation.views.generate_creative_variations.delay', side_effect=ConnectionError('broker down')):
            response = self.create_request(creative_type='post', brief_fields={'topic': 'x'})
        self.assertEqual(response.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)
        self.assertIn('nothing was generated', response.data['detail'])
        self.assertEqual(GenerationRequest.objects.count(), 0)          # no request stuck at "pending"
        self.assertEqual(ContentCalendarItem.objects.count(), items_before)  # no orphan for the auto-generator
        self.assertEqual(self.image.calls, [])


# --------------------------------------------------------------------------- legibility of the text on the picture


class LegibilityTests(SimpleTestCase):
    """Text over a busy part of the picture gets a stronger backing, an edge scrim and a soft shadow; a calm part
    keeps the clean look."""

    def scene(self, busy_bottom):
        from PIL import ImageDraw

        image = Image.new('RGB', (1024, 1280), (40, 60, 90))
        if busy_bottom:
            draw = ImageDraw.Draw(image)
            for index in range(0, 1024, 24):  # bright, high-detail stripes everywhere: no calm place for the text
                draw.rectangle((index, 0, index + 10, 1280), fill=(235, 225, 200))
        buffer = io.BytesIO()
        image.save(buffer, format='PNG')
        return buffer.getvalue()

    def compose(self, busy_bottom):
        from apps.creative_generation.compositor import compose_creative

        data, _ = compose_creative(
            self.scene(busy_bottom), 'image/png', headline='Step One: Choose Sacred Locale',
            description='Select a venue that blends heritage with panoramic vistas.', placement='auto',
            composition='bottom', variation_seed=None,
        )
        return Image.open(io.BytesIO(data)).convert('L')

    def test_the_treatment_follows_how_busy_the_picture_is(self):
        from apps.creative_generation.compositor import BUSY, BUSY_MODERATE, BUSY_VERY, legibility_for

        self.assertEqual(legibility_for(BUSY_MODERATE - 1), (0.0, 4.5, False, False))   # calm: the clean look
        moderate = legibility_for(BUSY_MODERATE + 1)
        self.assertTrue(moderate[3] and not moderate[2])                                  # a shadow, no scrim
        busy, very = legibility_for(BUSY + 1), legibility_for(BUSY_VERY + 1)
        self.assertTrue(busy[2] and busy[3])                                              # scrim and shadow
        self.assertGreater(very[0], busy[0])                                              # a stronger backing
        self.assertGreater(busy[1], moderate[1])                                          # a higher contrast target

    def test_the_busiest_line_of_the_block_decides_not_the_average(self):
        from apps.creative_generation.compositor import _busyness

        image = Image.new('RGB', (1000, 1000), (30, 30, 30))
        from PIL import ImageDraw

        draw = ImageDraw.Draw(image)
        for x in range(0, 1000, 16):  # one busy stripe across the top of the block, the rest calm
            draw.rectangle((x, 100, x + 6, 160), fill=(240, 240, 240))
        self.assertGreater(_busyness(image, (0, 100, 1000, 700)), 2 * _busyness(image, (0, 300, 1000, 700)))

    def test_busy_detail_behind_the_text_is_darkened_but_a_calm_picture_is_left_alone(self):
        busy, calm = self.compose(True), self.compose(False)

        def bands(image, box_x):
            return [ImageStat.Stat(image.crop((box_x[0], y, box_x[1], y + 30))).mean[0] for y in range(0, 1250, 30)]

        # The bright stripe at the left edge (never under a letter) is much darker where the text sits.
        self.assertLess(min(bands(busy, (0, 10))), 150)  # about 225 in the picture
        self.assertGreater(max(bands(busy, (0, 10))), 200)  # and untouched away from the text
        # The calm picture keeps its own tone everywhere (no blanket darkening).
        for value in bands(calm, (0, 40)):
            self.assertAlmostEqual(value, 58, delta=12)


class OutlineInstructionTests(SimpleTestCase):
    def test_an_instruction_in_the_outline_is_never_put_on_a_slide(self):
        from apps.creative_generation.tasks import looks_like_instruction

        self.assertTrue(looks_like_instruction('Create a premium real estate Instagram carousel showcasing homes'))
        self.assertTrue(looks_like_instruction('Show 3 floor plans'))
        self.assertFalse(looks_like_instruction('Your website looks outdated | Design affects trust'))
        self.assertFalse(looks_like_instruction('It is possible to grow'))  # "possible" is not "post"

        outline = 'Create a premium real estate carousel showcasing homes\nSpacious floor plans\nLiving in light'
        slides = carousel_slides(CAROUSEL_RESULT, {'outline': outline}, 4)
        self.assertNotIn('Create a premium', ' '.join(s['headline'] for s in slides))
        self.assertEqual([s['headline'] for s in slides[1:3]], ['Spacious floor plans', 'Living in light'])
