import io

from django.test import SimpleTestCase
from PIL import Image, ImageStat

from apps.creative_generation.compositor import _brand_colors, _brand_font, _sanitize_text, compose_creative


def fake_image_bytes(size=(600, 600), color='blue', fmt='JPEG'):
    buf = io.BytesIO()
    Image.new('RGB', size, color).save(buf, format=fmt)
    return buf.getvalue()


class FakeBrandProfile:
    def __init__(self, brand_colors=None, fonts=None):
        self.brand_colors = brand_colors or []
        self.fonts = fonts or []


class ComposeCreativeTests(SimpleTestCase):
    def test_returns_input_unchanged_when_nothing_to_overlay(self):
        original = fake_image_bytes()

        result_bytes, result_mime = compose_creative(original, 'image/jpeg')

        self.assertEqual(result_bytes, original)
        self.assertEqual(result_mime, 'image/jpeg')

    def test_headline_produces_a_different_valid_image(self):
        original = fake_image_bytes()

        result_bytes, result_mime = compose_creative(original, 'image/jpeg', headline='Elevate Your Everyday Living')

        self.assertEqual(result_mime, 'image/jpeg')
        self.assertNotEqual(result_bytes, original)
        composed = Image.open(io.BytesIO(result_bytes))
        composed.verify()

    def test_headline_and_cta_produces_a_valid_image(self):
        original = fake_image_bytes()

        result_bytes, result_mime = compose_creative(
            original, 'image/jpeg', headline='Elevate Your Everyday Living', cta='Book Your Site Visit Today',
        )

        composed = Image.open(io.BytesIO(result_bytes))
        composed.verify()
        self.assertEqual(composed.format, 'JPEG')

    def test_eyebrow_only_produces_a_valid_image(self):
        original = fake_image_bytes()

        result_bytes, _ = compose_creative(original, 'image/jpeg', eyebrow='THE')

        composed = Image.open(io.BytesIO(result_bytes))
        composed.verify()

    def test_description_only_produces_a_valid_image(self):
        original = fake_image_bytes()

        result_bytes, _ = compose_creative(
            original, 'image/jpeg', description='A premium home begins with decisions made long before the first brick.',
        )

        composed = Image.open(io.BytesIO(result_bytes))
        composed.verify()

    def test_full_layout_with_every_field_produces_a_valid_image(self):
        original = fake_image_bytes(size=(896, 1120))
        logo_bytes = fake_image_bytes(size=(200, 80), color='red', fmt='PNG')

        result_bytes, _ = compose_creative(
            original, 'image/jpeg',
            eyebrow='THE', headline='Majestique Standard',
            description='Luxury is not what you add. It is what you refuse to compromise.',
            cta='Live Majestique', logo_bytes=logo_bytes,
        )

        composed = Image.open(io.BytesIO(result_bytes))
        composed.verify()
        self.assertEqual(Image.open(io.BytesIO(result_bytes)).size, (896, 1120))

    def test_logo_only_produces_a_valid_image(self):
        original = fake_image_bytes()
        logo_bytes = fake_image_bytes(size=(200, 80), color='red', fmt='PNG')

        result_bytes, _ = compose_creative(original, 'image/jpeg', logo_bytes=logo_bytes)

        composed = Image.open(io.BytesIO(result_bytes))
        composed.verify()

    def test_smart_typography_in_headline_and_cta_does_not_raise(self):
        original = fake_image_bytes()

        result_bytes, _ = compose_creative(
            original, 'image/jpeg',
            headline='Human–Centric AI Solutions', cta='Book Now…',
        )

        composed = Image.open(io.BytesIO(result_bytes))
        composed.verify()

    def test_corrupt_logo_bytes_does_not_raise(self):
        original = fake_image_bytes()

        result_bytes, _ = compose_creative(original, 'image/jpeg', headline='Still Works', logo_bytes=b'not-an-image')

        composed = Image.open(io.BytesIO(result_bytes))
        composed.verify()

    def test_output_preserves_original_dimensions(self):
        original = fake_image_bytes(size=(800, 450))

        result_bytes, _ = compose_creative(
            original, 'image/jpeg', headline='Some Headline Text', cta='Learn More',
        )

        composed = Image.open(io.BytesIO(result_bytes))
        self.assertEqual(composed.size, (800, 450))

    def test_symbol_only_produces_a_valid_image(self):
        original = fake_image_bytes()
        symbol_bytes = fake_image_bytes(size=(120, 120), color='green', fmt='PNG')

        result_bytes, _ = compose_creative(original, 'image/jpeg', symbol_bytes=symbol_bytes)

        composed = Image.open(io.BytesIO(result_bytes))
        composed.verify()

    def test_corrupt_symbol_bytes_does_not_raise(self):
        original = fake_image_bytes()

        result_bytes, _ = compose_creative(original, 'image/jpeg', headline='Still Works', symbol_bytes=b'nope')

        composed = Image.open(io.BytesIO(result_bytes))
        composed.verify()

    def test_logo_and_symbol_together_produce_a_valid_image(self):
        original = fake_image_bytes()
        logo_bytes = fake_image_bytes(size=(200, 80), color='red', fmt='PNG')
        symbol_bytes = fake_image_bytes(size=(120, 120), color='green', fmt='PNG')

        result_bytes, _ = compose_creative(original, 'image/jpeg', logo_bytes=logo_bytes, symbol_bytes=symbol_bytes)

        composed = Image.open(io.BytesIO(result_bytes))
        composed.verify()

    def test_uses_brand_font_when_set(self):
        original = fake_image_bytes()
        profile = FakeBrandProfile(fonts=[{'name': 'Montserrat', 'usage': 'Headings'}])

        result_bytes, _ = compose_creative(
            original, 'image/jpeg', headline='Elevate Your Everyday Living', cta='Book now', brand_profile=profile,
        )

        composed = Image.open(io.BytesIO(result_bytes))
        composed.verify()


class SanitizeTextTests(SimpleTestCase):
    def test_replaces_en_and_em_dash(self):
        self.assertEqual(_sanitize_text('Human–Centric AI'), 'Human-Centric AI')
        self.assertEqual(_sanitize_text('Bold—Statement'), 'Bold-Statement')

    def test_replaces_curly_quotes(self):
        self.assertEqual(_sanitize_text('“Quoted”'), '"Quoted"')
        self.assertEqual(_sanitize_text("It’s here"), "It's here")

    def test_replaces_ellipsis_and_bullet(self):
        self.assertEqual(_sanitize_text('Loading…'), 'Loading...')
        self.assertEqual(_sanitize_text('• Point'), '- Point')

    def test_leaves_plain_ascii_untouched(self):
        self.assertEqual(_sanitize_text('Book Your Site Visit Today'), 'Book Your Site Visit Today')

    def test_strips_unanticipated_symbols_as_a_final_safety_net(self):
        # Not in the explicit replacement table - the NFKD+ascii-ignore fallback must
        # still produce plain ASCII rather than leaving something a font can't render.
        result = _sanitize_text('Special ⬜ offer ★ today')
        self.assertTrue(all(ord(c) < 128 for c in result))
        self.assertIn('Special', result)
        self.assertIn('offer', result)
        self.assertIn('today', result)

    def test_decomposes_accented_letters_to_ascii(self):
        self.assertEqual(_sanitize_text('Café'), 'Cafe')


class BrandFontTests(SimpleTestCase):
    def test_falls_back_to_poppins_when_no_brand_profile(self):
        font = _brand_font(None, 'bold', 40)
        self.assertIn('Poppins', font.path)

    def test_falls_back_to_poppins_for_unrecognized_font_name(self):
        profile = FakeBrandProfile(fonts=[{'name': 'Comic Sans MS', 'usage': 'Body'}])
        font = _brand_font(profile, 'bold', 40)
        self.assertIn('Poppins', font.path)

    def test_matches_static_family_by_name_case_insensitively(self):
        profile = FakeBrandProfile(fonts=[{'name': 'lato', 'usage': 'Headings'}])
        font = _brand_font(profile, 'semibold', 40)
        self.assertIn('Lato', font.path)

    def test_matches_variable_family_and_applies_bold_weight(self):
        profile = FakeBrandProfile(fonts=[{'name': 'Montserrat', 'usage': 'Headings'}])
        font = _brand_font(profile, 'bold', 40)
        self.assertIn('Montserrat', font.path)
        # A distinct bbox at 'bold' vs 'semibold' confirms the weight axis was actually set.
        semibold_font = _brand_font(profile, 'semibold', 40)
        self.assertNotEqual(font.getbbox('Test'), semibold_font.getbbox('Test'))


class BrandColorsTests(SimpleTestCase):
    def test_uses_primary_and_first_other_color_when_present(self):
        profile = FakeBrandProfile(brand_colors=[
            {'name': 'Primary', 'hex': '#7D5F45'},
            {'name': 'Secondary', 'hex': '#83430B'},
        ])

        banner_color, accent_color = _brand_colors(profile)

        self.assertEqual(banner_color, '#7D5F45')
        self.assertEqual(accent_color, '#83430B')

    def test_falls_back_to_defaults_when_no_brand_profile(self):
        banner_color, accent_color = _brand_colors(None)

        self.assertTrue(banner_color.startswith('#'))
        self.assertTrue(accent_color.startswith('#'))

    def test_ignores_malformed_hex_values(self):
        profile = FakeBrandProfile(brand_colors=[{'name': 'Primary', 'hex': 'not-a-hex-color'}])

        banner_color, _ = _brand_colors(profile)

        self.assertTrue(banner_color.startswith('#'))
        self.assertNotEqual(banner_color, 'not-a-hex-color')


class BrandLayerTests(SimpleTestCase):
    def flat_background_logo(self):
        """A dark-brown mark on a flat off-white background with lots of empty margin, like a JPEG logo upload."""
        image = Image.new('RGB', (400, 200), (247, 247, 247))
        image.paste(Image.new('RGB', (120, 60), (123, 90, 69)), (140, 70))
        buf = io.BytesIO()
        image.save(buf, format='JPEG', quality=95)
        return buf.getvalue()

    def test_logo_background_is_removed_and_the_margin_trimmed(self):
        from apps.creative_generation.compositor import _prepare_mark

        mark = _prepare_mark(self.flat_background_logo())

        self.assertEqual(mark.mode, 'RGBA')
        self.assertLessEqual(abs(mark.width - 120), 4)  # trimmed to the artwork, not the 400px canvas
        self.assertLessEqual(abs(mark.height - 60), 4)
        self.assertEqual(mark.getpixel((mark.width // 2, mark.height // 2))[3], 255)  # artwork stays solid

    def test_logo_with_real_transparency_is_kept_as_is(self):
        from apps.creative_generation.compositor import _prepare_mark

        image = Image.new('RGBA', (100, 40), (0, 0, 0, 0))
        image.paste(Image.new('RGBA', (60, 20), (255, 255, 255, 255)), (20, 10))
        buf = io.BytesIO()
        image.save(buf, format='PNG')

        mark = _prepare_mark(buf.getvalue())

        self.assertEqual((mark.width, mark.height), (60, 20))

    def test_unreadable_logo_gives_none(self):
        from apps.creative_generation.compositor import _prepare_mark

        self.assertIsNone(_prepare_mark(b'not-an-image'))

    def test_long_text_ends_with_an_ellipsis_instead_of_being_cut_mid_sentence(self):
        from PIL import ImageDraw, ImageFont

        from apps.creative_generation.compositor import _wrapped_lines

        draw = ImageDraw.Draw(Image.new('RGB', (10, 10)))
        font = ImageFont.load_default()
        lines = _wrapped_lines(draw, 'one two three four five six seven eight nine ten ' * 4, font, 120, max_lines=2)

        self.assertEqual(len(lines), 2)
        self.assertTrue(lines[-1].endswith('...'))

    def test_non_breaking_hyphen_survives(self):
        self.assertEqual(_sanitize_text('Data‑Driven'), 'Data-Driven')


class FestiveLayoutTests(SimpleTestCase):
    CREAM = (250, 244, 232)

    def festive(self, *, size=(1024, 1536), logo=None, **copy):
        original = fake_image_bytes(size=size, color=self.CREAM, fmt='PNG')
        brand = FakeBrandProfile(brand_colors=[{'name': 'Primary', 'hex': '#83430B'}, {'name': 'Secondary', 'hex': '#D97706'}])
        result_bytes, mime = compose_creative(original, 'image/png', logo_bytes=logo, brand_profile=brand, layout='festive', **copy)
        return Image.open(io.BytesIO(result_bytes)).convert('RGB'), mime

    def dark_pixels(self, image, box):
        return sum(1 for px in image.crop(box).getdata() if sum(px) < 450)

    def transparent_logo(self):
        image = Image.new('RGBA', (300, 100), (0, 0, 0, 0))
        image.paste(Image.new('RGBA', (240, 60), (123, 90, 69, 255)), (30, 20))
        buf = io.BytesIO()
        image.save(buf, format='PNG')
        return buf.getvalue()

    def test_output_is_cropped_to_instagram_portrait_4_by_5(self):
        image, mime = self.festive(eyebrow='Happy', headline='Diwali', description='May this Diwali bring light.')
        self.assertEqual(image.size, (1024, 1280))
        self.assertEqual(mime, 'image/jpeg')

    def test_a_square_image_is_extended_down_to_4_by_5_with_a_seamless_background(self):
        image, _ = self.festive(size=(1000, 1000), eyebrow='Happy', headline='Diwali', description='May this Diwali bring light.')
        self.assertEqual(image.size, (1000, 1250))
        # The added area continues the plain cream background - no visible seam at the join row.
        above, below = image.getpixel((20, 995)), image.getpixel((20, 1005))
        self.assertLessEqual(max(abs(a - b) for a, b in zip(above, below)), 6)

    def photo_with(self, size=(1024, 1280), subject=None, stray=None):
        from PIL import ImageDraw, ImageFont

        photo = Image.new('RGB', size, self.CREAM)
        draw = ImageDraw.Draw(photo)
        if subject:
            draw.ellipse(subject, fill=(205, 150, 55))
        if stray:
            font = ImageFont.truetype('apps/creative_generation/fonts/Roboto-Variable.ttf', 40)
            draw.text(stray, 'HAPPY DIWALI rarisoftworks', font=font, fill=(60, 30, 10))
        buf = io.BytesIO()
        photo.save(buf, format='PNG')
        return buf.getvalue()

    def compose(self, photo, **copy):
        brand = FakeBrandProfile(brand_colors=[{'name': 'Primary', 'hex': '#83430B'}, {'name': 'Secondary', 'hex': '#D97706'}])
        result_bytes, _ = compose_creative(photo, 'image/png', brand_profile=brand, layout='festive', **copy)
        return Image.open(io.BytesIO(result_bytes)).convert('RGB')

    def test_lettering_the_image_model_painted_where_the_greeting_goes_is_erased(self):
        # A line of stray words sits just below where the one-line wish will be drawn.
        image = self.compose(self.photo_with(stray=(150, 1195)), description='A short wish.')
        self.assertEqual(self.dark_pixels(image, (0, 1192, image.width, 1250)), 0)

    def test_a_subject_that_ends_above_the_text_is_untouched(self):
        image = self.compose(self.photo_with(subject=(300, 300, 724, 700)), headline='Diwali', description='May this bring light.')
        self.assertEqual(image.size, (1024, 1280))  # nothing needed extending
        r, g, b = image.getpixel((512, 692))        # the subject's lowest rows are still there
        self.assertTrue(r > 180 and g > 120 and b < 110, (r, g, b))

    def test_a_low_subject_is_never_cut_the_canvas_grows_and_the_text_goes_below_it(self):
        image = self.compose(
            self.photo_with(subject=(250, 560, 774, 940)),
            eyebrow='Happy', headline='Diwali', description='May this Diwali bring light, joy and new beginnings.',
        )
        self.assertGreater(image.height, 1280)
        self.assertLessEqual(image.height, int(1024 * 1.45))
        r, g, b = image.getpixel((512, 930))  # the subject's bottom is intact, not covered or faded out
        self.assertTrue(r > 180 and g > 120 and b < 110, (r, g, b))
        self.assertGreater(self.dark_pixels(image, (0, 1000, image.width, image.height)), 500)  # text sits beneath it
        self.assertEqual(self.dark_pixels(image, (0, 0, image.width, 540)), 0)

    def test_a_subject_touching_the_bottom_edge_does_not_smear_into_the_extension(self):
        from PIL import ImageDraw

        from apps.creative_generation.compositor import _extend_down

        photo = Image.new('RGB', (1000, 1000), self.CREAM)
        ImageDraw.Draw(photo).rectangle([300, 800, 700, 999], fill=(200, 20, 60))  # runs off the bottom edge

        extended = _extend_down(photo.convert('RGBA'), 250).convert('RGB')

        self.assertEqual(extended.size, (1000, 1250))
        for actual, expected in zip(extended.getpixel((500, 1245)), self.CREAM):  # right under the subject
            self.assertLessEqual(abs(actual - expected), 4)
        midway = extended.getpixel((500, 1075))[1]  # halfway down the extension: partly faded, neither the subject nor plain cream
        self.assertTrue(60 < midway < 220, midway)

    def test_a_plain_bottom_edge_is_continued_exactly(self):
        from apps.creative_generation.compositor import _extend_down

        extended = _extend_down(Image.new('RGBA', (800, 800), (*self.CREAM, 255)), 200).convert('RGB')
        for actual, expected in zip(extended.getpixel((400, 990)), self.CREAM):
            self.assertLessEqual(abs(actual - expected), 2)

    def test_content_bottom_finds_the_subject_and_ignores_thin_marks(self):
        from apps.creative_generation.compositor import _content_bottom

        subject = Image.open(io.BytesIO(self.photo_with(subject=(300, 300, 724, 700))))
        self.assertLessEqual(abs(_content_bottom(subject, 90) - 700), 12)
        marks = Image.open(io.BytesIO(self.photo_with(stray=(150, 1195))))
        self.assertEqual(_content_bottom(marks, 90), 0)

    def test_a_clean_plain_background_is_left_visually_unchanged_by_the_cleaning(self):
        image, _ = self.festive(logo=self.transparent_logo())
        for point in ((50, 800), (500, 1000), (900, 1200)):
            for actual, expected in zip(image.getpixel(point), self.CREAM):
                self.assertLessEqual(abs(actual - expected), 3)

    def test_a_landscape_image_is_left_alone(self):
        image, _ = self.festive(size=(1500, 1000), headline='Diwali')
        self.assertEqual(image.size, (1500, 1000))

    def test_greeting_and_wish_are_drawn_in_the_lower_part_only(self):
        image, _ = self.festive(eyebrow='Happy', headline='Diwali', description='May this Diwali bring light, joy and new beginnings.')
        width, height = image.size
        self.assertGreater(self.dark_pixels(image, (0, int(height * 0.65), width, height)), 500)
        self.assertEqual(self.dark_pixels(image, (0, int(height * 0.15), width, int(height * 0.6))), 0)  # the element's space stays empty

    def test_background_stays_light_no_dark_footer_scrim(self):
        image, _ = self.festive(headline='Diwali', description='A wish.')
        r, g, b = image.getpixel((5, image.height - 5))
        self.assertGreater(r + g + b, 700)

    def test_logo_sits_in_the_top_right_corner_and_nowhere_else_at_the_top(self):
        image, _ = self.festive(logo=self.transparent_logo(), headline='Diwali')
        width, height = image.size
        self.assertGreater(self.dark_pixels(image, (int(width * 0.7), 0, width, int(height * 0.12))), 300)
        self.assertEqual(self.dark_pixels(image, (0, 0, int(width * 0.5), int(height * 0.12))), 0)

    def test_logo_only_still_places_the_logo(self):
        image, _ = self.festive(logo=self.transparent_logo())
        self.assertGreater(self.dark_pixels(image, (int(image.width * 0.7), 0, image.width, int(image.height * 0.12))), 300)

    def test_text_stays_legible_if_the_background_turns_out_dark(self):
        original = fake_image_bytes(size=(1024, 1536), color=(20, 20, 30), fmt='PNG')
        result_bytes, _ = compose_creative(original, 'image/png', headline='Diwali', description='A wish.', layout='festive')
        image = Image.open(io.BytesIO(result_bytes)).convert('RGB')
        bright = sum(1 for px in image.crop((0, 900, 1024, 1280)).getdata() if sum(px) > 450)
        self.assertGreater(bright, 500)

    def test_a_long_festival_name_shrinks_to_fit_instead_of_overflowing(self):
        image, _ = self.festive(headline='Makar Sankranti Pongal', description='Warm wishes.')
        left_edge = (0, 900, 15, 1280)
        right_edge = (image.width - 15, 900, image.width, 1280)
        self.assertEqual(self.dark_pixels(image, left_edge), 0)
        self.assertEqual(self.dark_pixels(image, right_edge), 0)


class HindiTextTests(SimpleTestCase):
    HINDI = 'शुभ लक्ष्मी पूजन'

    def test_devanagari_survives_sanitising_and_is_not_stripped_to_nothing(self):
        self.assertEqual(_sanitize_text(self.HINDI), self.HINDI)
        self.assertEqual(_sanitize_text('शुभ — Laxmi “Pujan”'), 'शुभ - Laxmi "Pujan"')

    def test_conjunct_joiners_are_kept_but_other_symbols_are_still_stripped(self):
        self.assertEqual(_sanitize_text('क\u200dष'), 'क\u200dष')
        self.assertEqual(_sanitize_text('Hello ✨ Diwali'), 'Hello  Diwali')

    def test_hindi_text_gets_a_devanagari_font_and_latin_text_keeps_its_own(self):
        from apps.creative_generation.compositor import _headline_font

        self.assertIn('Devanagari', _headline_font('bold', 40, self.HINDI).path)
        self.assertIn('Devanagari', _brand_font(None, 'regular', 30, self.HINDI).path)
        self.assertIn('PlayfairDisplay', _headline_font('bold', 40, 'Diwali').path)
        self.assertIn('Poppins', _brand_font(None, 'regular', 30, 'May this Diwali bring light').path)

    def test_a_hindi_festive_greeting_is_actually_drawn(self):
        original = fake_image_bytes(size=(1024, 1536), color=(250, 244, 232), fmt='PNG')
        brand = FakeBrandProfile(brand_colors=[{'name': 'Primary', 'hex': '#83430B'}, {'name': 'Secondary', 'hex': '#D97706'}])

        result_bytes, _ = compose_creative(
            original, 'image/png', brand_profile=brand, layout='festive',
            headline=self.HINDI, description='May Goddess Laxmi bless your home with prosperity.',
        )

        image = Image.open(io.BytesIO(result_bytes)).convert('RGB')
        headline_band = image.crop((0, 880, 1024, 1010))  # where the festival name is set
        self.assertGreater(sum(1 for px in headline_band.getdata() if sum(px) < 600), 800)

    def test_a_hindi_wish_is_drawn_whole_not_letter_by_letter(self):
        from PIL import ImageDraw

        from apps.creative_generation.compositor import _brand_font, _draw_spaced

        canvas = Image.new('RGB', (900, 120), 'white')
        font = _brand_font(None, 'regular', 40, self.HINDI)
        _draw_spaced(ImageDraw.Draw(canvas), 450, 20, self.HINDI, font, (0, 0, 0), spacing=12)
        dark = [x for x in range(900) if any(sum(canvas.getpixel((x, y))) < 300 for y in range(120))]
        # Spacing is not applied to Devanagari: the text stays one tight, centred run.
        self.assertLess(max(dark) - min(dark), 12 + font.getlength(self.HINDI) + 40)


class PlainDesignSystemTests(SimpleTestCase):
    """Every creative type: plain background, logo top-right, only the text placement differs."""

    CREAM = (250, 244, 232)
    SUBJECT = (40, 120, 200)  # blue: distinct from the cream background, the dark text and the orange accent

    def photo(self, size=(1024, 1280), subject=None):
        from PIL import ImageDraw

        image = Image.new('RGB', size, self.CREAM)
        if subject:
            ImageDraw.Draw(image).ellipse(subject, fill=self.SUBJECT)
        buf = io.BytesIO()
        image.save(buf, format='PNG')
        return buf.getvalue()

    def logo(self):
        image = Image.new('RGBA', (300, 100), (0, 0, 0, 0))
        image.paste(Image.new('RGBA', (240, 60), (123, 90, 69, 255)), (30, 20))
        buf = io.BytesIO()
        image.save(buf, format='PNG')
        return buf.getvalue()

    def compose(self, photo, **kwargs):
        brand = FakeBrandProfile(brand_colors=[{'name': 'Primary', 'hex': '#83430B'}, {'name': 'Secondary', 'hex': '#D97706'}])
        result_bytes, _ = compose_creative(photo, 'image/png', brand_profile=brand, **kwargs)
        return Image.open(io.BytesIO(result_bytes)).convert('RGB')

    def count(self, image, box, predicate):
        return sum(1 for px in image.crop(box).getdata() if predicate(px))

    def dark(self, px):
        return sum(px) < 450

    def subject_pixel(self, px):
        return px[0] < 90 and 90 < px[1] < 160 and px[2] > 160

    def test_the_logo_is_large_and_in_the_top_right_corner_for_every_type(self):
        for kwargs in ({'layout': 'standard', 'placement': 'below'}, {'layout': 'standard', 'placement': 'top'}, {'layout': 'festive'}):
            image = self.compose(self.photo(), logo_bytes=self.logo(), **kwargs)
            width = image.width
            box = (width - int(width * 0.06) - int(width * 0.32), int(width * 0.06), width - int(width * 0.06), int(width * 0.06) + 82)
            self.assertGreater(self.count(image, box, self.dark), 12000, kwargs)  # a big logo (about 327 x 82 px of artwork)
            self.assertEqual(self.count(image, (0, 0, width // 2, 200), self.dark), 0, kwargs)

    def test_there_is_no_plate_behind_the_logo(self):
        image = self.compose(self.photo(), logo_bytes=self.logo(), layout='standard')
        for point in ((image.width - 400, 10), (image.width - 5, 5), (image.width - 25, 140)):
            for actual, expected in zip(image.getpixel(point), self.CREAM):
                self.assertLessEqual(abs(actual - expected), 4, point)

    def test_below_placement_centres_the_text_under_the_subject(self):
        image = self.compose(
            self.photo(subject=(300, 250, 724, 620)), layout='standard', placement='below',
            eyebrow='New', headline='Meet the new collection', description='Made to last.', cta='Shop now',
        )
        width, height = image.size
        self.assertGreater(self.count(image, (0, int(height * 0.65), width, height), self.dark), 800)
        self.assertEqual(self.count(image, (0, 0, width, int(height * 0.18)), self.dark), 0)

    def test_top_placement_puts_the_text_top_left_and_keeps_the_lower_area_for_the_subject(self):
        image = self.compose(
            self.photo(subject=(300, 700, 724, 1100)), layout='standard', placement='top',
            eyebrow='Event', headline='Annual summit 2026', description='Join us in Pune.', cta='Register',
        )
        width, height = image.size
        self.assertGreater(self.count(image, (0, 0, int(width * 0.58), int(height * 0.3)), self.dark), 800)
        self.assertEqual(self.count(image, (int(width * 0.64), 0, width, int(height * 0.3)), self.dark), 0)  # right side is the logo's
        self.assertEqual(self.count(image, (0, int(height * 0.62), 250, height), self.dark), 0)  # nothing below the text, beside the subject

    def test_the_cta_is_a_pill_in_the_brand_accent_colour(self):
        image = self.compose(self.photo(), layout='standard', placement='below', headline='Big news', cta='Learn more')
        accent_pixels = self.count(image, (0, 0, image.width, image.height), lambda px: px[0] > 150 and 60 < px[1] < 150 and px[2] < 60)
        self.assertGreater(accent_pixels, 1500)

    def test_stories_are_nine_by_sixteen(self):
        image = self.compose(self.photo(size=(1024, 1024)), layout='standard', headline='Story', aspect=16 / 9)
        self.assertEqual(image.size, (1024, 1820))

    def test_top_placement_extends_a_square_image_upwards_not_downwards(self):
        image = self.compose(self.photo(size=(1000, 1000), subject=(300, 500, 700, 950)), layout='standard', placement='top', headline='Hello')
        self.assertEqual(image.size, (1000, 1250))
        self.assertTrue(self.subject_pixel(image.getpixel((500, 1000))))  # the subject moved down by the 250px added on top

    def test_a_subject_is_never_covered_or_cut_whichever_way_the_text_goes(self):
        for placement, subject in (('below', (250, 560, 774, 940)), ('top', (250, 330, 774, 700))):
            photo = self.photo(subject=subject)
            before = self.count(Image.open(io.BytesIO(photo)).convert('RGB'), (0, 0, 1024, 1280), self.subject_pixel)
            image = self.compose(
                photo, layout='standard', placement=placement,
                eyebrow='Kicker', headline='A fairly long headline for the creative', description='Body copy goes here.', cta='Go',
            )
            after = self.count(image, (0, 0, image.width, image.height), self.subject_pixel)
            self.assertGreater(after, before * 0.97, placement)  # nothing of the subject was painted over
            self.assertLess(after, before * 1.03, placement)


class SceneModeTests(SimpleTestCase):
    """A described scene: a full photograph shown whole, with the same text and logo layout on top."""

    def scene(self, size=(1024, 1280)):
        # A sea-and-sky style picture: bright sky over mid-blue water, with some texture so it is not "plain".
        import random

        random.seed(7)
        image = Image.new('RGB', size, (150, 190, 225))
        pixels = image.load()
        horizon = int(size[1] * 0.45)
        for y in range(size[1]):
            for x in range(size[0]):
                if y < horizon:
                    pixels[x, y] = (170 - y // 12, 205 - y // 14, 240 - y // 20)
                else:
                    wave = random.randint(-14, 14)
                    pixels[x, y] = (120 + wave, 175 + wave, 215 + wave)
        buf = io.BytesIO()
        image.save(buf, format='PNG')
        return buf.getvalue()

    def logo(self):
        image = Image.new('RGBA', (300, 100), (0, 0, 0, 0))
        image.paste(Image.new('RGBA', (240, 60), (123, 90, 69, 255)), (30, 20))
        buf = io.BytesIO()
        image.save(buf, format='PNG')
        return buf.getvalue()

    def compose(self, photo, **kwargs):
        brand = FakeBrandProfile(brand_colors=[{'name': 'Primary', 'hex': '#83430B'}, {'name': 'Secondary', 'hex': '#D97706'}])
        result_bytes, _ = compose_creative(photo, 'image/png', brand_profile=brand, background='scene', **kwargs)
        return Image.open(io.BytesIO(result_bytes)).convert('RGB')

    def white_pixels(self, image, box):
        return sum(1 for px in image.crop(box).getdata() if min(px) > 235)

    def test_the_scene_is_shown_whole_never_extended_or_smoothed(self):
        photo = self.scene()
        original = Image.open(io.BytesIO(photo)).convert('RGB')
        image = self.compose(photo, layout='festive', placement='below', eyebrow='Happy', headline='Anant Chaturdashi', description='May Ganpati bless you.')
        self.assertEqual(image.size, original.size)
        # Away from the text and the logo the photograph is untouched (allowing for JPEG rounding).
        for point in ((60, 400), (500, 300), (900, 500), (200, 600)):
            for actual, expected in zip(image.getpixel(point), original.getpixel(point)):
                self.assertLessEqual(abs(actual - expected), 10, point)

    def test_text_sits_below_on_a_gradient_for_the_below_placement(self):
        photo = self.scene()
        original = Image.open(io.BytesIO(photo)).convert('RGB')
        image = self.compose(photo, layout='standard', placement='below', headline='Big news', description='Read all about it.', cta='Learn more')
        low = (0, 1000, 1024, 1280)
        self.assertLess(ImageStat.Stat(image.crop(low)).mean[2], ImageStat.Stat(original.crop(low)).mean[2] - 40)  # darkened by the gradient
        self.assertGreater(self.white_pixels(image, low), 400)  # white text
        self.assertEqual(self.white_pixels(image, (0, 0, 600, 200)), 0)

    def test_text_sits_at_the_top_left_on_a_gradient_for_the_top_placement(self):
        photo = self.scene()
        original = Image.open(io.BytesIO(photo)).convert('RGB')
        image = self.compose(photo, layout='standard', placement='top', eyebrow='Event', headline='Annual summit', description='Join us in Pune.')
        self.assertLess(ImageStat.Stat(image.crop((0, 0, 1024, 260))).mean[2], ImageStat.Stat(original.crop((0, 0, 1024, 260))).mean[2] - 40)
        self.assertGreater(self.white_pixels(image, (0, 0, 620, 330)), 400)
        self.assertEqual(self.white_pixels(image, (0, 1000, 1024, 1280)), 0)

    def test_the_logo_is_large_and_in_the_top_right_corner_over_the_scene(self):
        photo = self.scene()
        original = Image.open(io.BytesIO(photo)).convert('RGB')
        image = self.compose(photo, layout='festive', placement='below', logo_bytes=self.logo())
        width = image.width
        corner = (width - int(width * 0.06) - int(width * 0.32), int(width * 0.06), width - int(width * 0.06), int(width * 0.06) + 82)

        def changed(box):
            return sum(
                1 for a, b in zip(image.crop(box).getdata(), original.crop(box).getdata())
                if sum(abs(p - q) for p, q in zip(a, b)) > 120
            )

        self.assertGreater(changed(corner), 8000)  # a big mark (about 327 x 82 px of artwork) that stands out from the sky
        self.assertLess(changed((0, 0, width // 2, 200)), 50)  # and nothing at the top-left

    def test_a_taller_picture_is_cropped_to_the_ratio_and_a_shorter_one_is_kept(self):
        tall = self.compose(self.scene(size=(1000, 1500)), layout='standard', headline='Hello')
        self.assertEqual(tall.size, (1000, 1250))
        square = self.compose(self.scene(size=(1000, 1000)), layout='standard', headline='Hello')
        self.assertEqual(square.size, (1000, 1000))  # not invented, not stretched

    def test_a_hindi_greeting_is_drawn_over_a_scene(self):
        image = self.compose(self.scene(), layout='festive', placement='below', headline='\u0936\u0941\u092d \u0932\u0915\u094d\u0937\u094d\u092e\u0940 \u092a\u0942\u091c\u0928')
        self.assertGreater(self.white_pixels(image, (0, 1000, 1024, 1280)) + sum(
            1 for px in image.crop((0, 1000, 1024, 1280)).getdata() if px[0] > 170 and px[2] < 120), 300)

    def test_logo_only_over_a_scene_adds_no_gradient(self):
        photo = self.scene()
        original = Image.open(io.BytesIO(photo)).convert('RGB')
        image = self.compose(photo, layout='standard', logo_bytes=self.logo())
        for actual, expected in zip(image.getpixel((500, 1200)), original.getpixel((500, 1200))):
            self.assertLessEqual(abs(actual - expected), 8)
