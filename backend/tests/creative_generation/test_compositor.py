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

    def test_a_hindi_wish_is_drawn_whole_not_letter_by_letter(self):
        from PIL import ImageDraw

        from apps.creative_generation.compositor import _brand_font, _draw_spaced

        canvas = Image.new('RGB', (900, 120), 'white')
        font = _brand_font(None, 'regular', 40, self.HINDI)
        _draw_spaced(ImageDraw.Draw(canvas), 450, 20, self.HINDI, font, (0, 0, 0), spacing=12)
        dark = [x for x in range(900) if any(sum(canvas.getpixel((x, y))) < 300 for y in range(120))]
        # Spacing is not applied to Devanagari: the text stays one tight, centred run.
        self.assertLess(max(dark) - min(dark), 12 + font.getlength(self.HINDI) + 40)


class SceneLayoutTests(SimpleTestCase):
    """The full scene is shown whole, with the same logo and text template on top for every type."""

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
        result_bytes, _ = compose_creative(photo, 'image/png', brand_profile=brand, **kwargs)
        return Image.open(io.BytesIO(result_bytes)).convert('RGB')

    def white_pixels(self, image, box):
        return sum(1 for px in image.crop(box).getdata() if min(px) > 235)

    def test_the_scene_is_shown_whole_never_extended_or_smoothed(self):
        photo = self.scene()
        original = Image.open(io.BytesIO(photo)).convert('RGB')
        image = self.compose(photo, placement='below', eyebrow='Happy', headline='Anant Chaturdashi', description='May Ganpati bless you.')
        self.assertEqual(image.size, original.size)
        # Away from the text and the logo the photograph is untouched (allowing for JPEG rounding).
        for point in ((60, 400), (500, 300), (900, 500), (200, 600)):
            for actual, expected in zip(image.getpixel(point), original.getpixel(point)):
                self.assertLessEqual(abs(actual - expected), 10, point)

    def flat(self, color, size=(1024, 1280)):
        buf = io.BytesIO()
        Image.new('RGB', size, color).save(buf, format='PNG')
        return buf.getvalue()

    def count(self, image, box, predicate):
        return sum(1 for px in image.crop(box).getdata() if predicate(px))

    def dark_ink(self, px):
        return sum(px) < 330  # the brand's darkened primary (#83430B)

    LIGHT = (246, 238, 224)  # a sunlit cream wall
    DARK = (24, 32, 64)      # a night sky

    def test_a_light_picture_gets_dark_brand_coloured_text_straight_onto_it(self):
        image = self.compose(
            self.flat(self.LIGHT), placement='below', eyebrow='Happy', headline='Diwali', description='May this season bring light and joy.',
        )
        low = (0, 900, 1024, 1280)
        self.assertGreater(self.count(image, low, self.dark_ink), 600)  # dark text ...
        self.assertGreater(ImageStat.Stat(image.crop(low).convert('L')).mean[0], 200)  # ... on a picture that stays light, not a dark panel

    def test_a_dark_picture_gets_white_text(self):
        image = self.compose(self.flat(self.DARK), placement='below', headline='Big news', description='Read all about it.', cta='Learn more')
        self.assertGreater(self.white_pixels(image, (0, 1000, 1024, 1280)), 400)
        self.assertEqual(self.white_pixels(image, (0, 0, 600, 200)), 0)

    def test_text_sits_at_the_top_left_for_the_top_placement_in_both_styles(self):
        for color, is_text in ((self.LIGHT, self.dark_ink), (self.DARK, lambda px: min(px) > 235)):
            image = self.compose(self.flat(color), placement='top', eyebrow='Event', headline='Annual summit', description='Join us in Pune.')
            self.assertGreater(self.count(image, (0, 0, 620, 330), is_text), 400, color)
            self.assertEqual(self.count(image, (0, 1000, 1024, 1280), is_text), 0, color)

    def test_a_centred_kicker_gets_thin_rules_either_side(self):
        from PIL import ImageDraw

        from apps.creative_generation.compositor import _spaced_width

        brand = FakeBrandProfile()
        font = _brand_font(brand, 'semibold', max(14, int(1024 * 0.026)), 'HAPPY')
        text_width = _spaced_width(ImageDraw.Draw(Image.new('RGB', (10, 10))), 'HAPPY', font, 3)
        image = self.compose(self.flat(self.LIGHT), placement='below', eyebrow='Happy')
        band_height = int(font.size * 1.7)
        band = (0, 1280 - int(1024 * 0.09) - band_height, 1024, 1280 - int(1024 * 0.09))
        xs = [x for x in range(1024) if self.count(image, (x, band[1], x + 1, band[3]), lambda px: sum(px) < 600)]
        self.assertGreater(max(xs) - min(xs), text_width + 2 * 1024 * 0.1)  # the rules extend well past the text

    def test_a_centred_stack_has_a_divider_between_headline_and_body_and_a_left_aligned_one_does_not(self):
        from PIL import ImageDraw

        from apps.creative_generation.compositor import _build_text_parts

        draw = ImageDraw.Draw(Image.new('RGB', (1024, 1280)))

        def kinds(centered, **copy):
            parts = _build_text_parts(draw, centered=centered, text_width=900, width=1024, cta='', brand_profile=None, **copy)
            return [part[0] for part in parts]

        copy = {'eyebrow': 'Happy', 'headline': 'Diwali', 'description': 'A wish.'}
        self.assertEqual(kinds(True, **copy), ['eyebrow', 'lines', 'divider', 'lines'])
        self.assertEqual(kinds(False, **copy), ['eyebrow', 'lines', 'lines'])
        self.assertEqual(kinds(True, eyebrow='', headline='', description='Only a body'), ['lines'])

    def test_the_logo_is_large_and_in_the_same_top_right_corner_whichever_way_the_text_goes(self):
        photo = self.scene()
        original = Image.open(io.BytesIO(photo)).convert('RGB')

        for placement in ('below', 'top'):
            image = self.compose(photo, placement=placement, logo_bytes=self.logo())
            width = image.width
            corner = (width - int(width * 0.06) - int(width * 0.32), int(width * 0.06), width - int(width * 0.06), int(width * 0.06) + 82)

            def changed(box):
                return sum(
                    1 for a, b in zip(image.crop(box).getdata(), original.crop(box).getdata())
                    if sum(abs(p - q) for p, q in zip(a, b)) > 120
                )

            self.assertGreater(changed(corner), 8000, placement)  # a big mark (about 327 x 82 px of artwork) that stands out from the sky
            self.assertLess(changed((0, 0, width // 2, 200)), 50, placement)  # and nothing at the top-left

    def test_a_logo_that_keeps_its_own_background_is_not_turned_into_a_solid_block(self):
        # A shaded (non-flat) background cannot be keyed out, so the logo stays an opaque rectangle.
        from PIL import ImageDraw

        artwork = Image.new('RGB', (300, 100))
        for x in range(300):
            ImageDraw.Draw(artwork).line([(x, 0), (x, 99)], fill=(255 - x // 5, 255 - x // 5, 255 - x // 5))
        ImageDraw.Draw(artwork).rectangle((60, 30, 240, 70), fill=(123, 20, 20))
        buf = io.BytesIO()
        artwork.save(buf, format='PNG')

        image = self.compose(self.flat(self.LIGHT), logo_bytes=buf.getvalue())
        width = image.width
        box = (width - int(width * 0.06) - int(width * 0.32), int(width * 0.06), width - int(width * 0.06), int(width * 0.06) + 100)
        light = self.count(image, box, lambda px: min(px) > 180)
        dark = self.count(image, box, lambda px: sum(px) < 330)
        total = (box[2] - box[0]) * (box[3] - box[1])
        self.assertGreater(light, total * 0.3)  # its background is still there
        self.assertGreater(dark, total * 0.1)   # and so is its artwork

    def test_a_taller_picture_is_cropped_to_the_ratio_and_a_shorter_one_is_kept(self):
        tall = self.compose(self.scene(size=(1000, 1500)), headline='Hello')
        self.assertEqual(tall.size, (1000, 1250))
        square = self.compose(self.scene(size=(1000, 1000)), headline='Hello')
        self.assertEqual(square.size, (1000, 1000))  # not invented, not stretched

    def test_a_hindi_greeting_is_drawn_over_a_scene(self):
        image = self.compose(self.flat(self.DARK), placement='below', headline='\u0936\u0941\u092d \u0932\u0915\u094d\u0937\u094d\u092e\u0940 \u092a\u0942\u091c\u0928')
        self.assertGreater(self.white_pixels(image, (0, 1000, 1024, 1280)), 300)

    def test_logo_only_over_a_scene_adds_no_gradient(self):
        photo = self.scene()
        original = Image.open(io.BytesIO(photo)).convert('RGB')
        image = self.compose(photo, logo_bytes=self.logo())
        for actual, expected in zip(image.getpixel((500, 1200)), original.getpixel((500, 1200))):
            self.assertLessEqual(abs(actual - expected), 8)


class TextStyleTests(SimpleTestCase):
    def test_the_text_is_readable_on_any_picture_with_the_gentlest_veil_that_works(self):
        from apps.creative_generation.compositor import VEIL_STRENGTHS, _contrast_ratio, _mix, _rgb, _text_style

        for backdrop in ('#FFFFFF', '#F6EEE0', '#D8C7A0', '#9A9A9A', '#6B7F99', '#C46A1B', '#2A3A5C', '#000000'):
            veil, strength, ink, accent = _text_style(backdrop, '#83430B', '#D97706')
            shown = _mix(backdrop, _rgb(veil), strength)
            self.assertGreaterEqual(_contrast_ratio(ink, shown), 4.5, backdrop)
            self.assertGreaterEqual(_contrast_ratio(accent, shown), 3.0, backdrop)
            self.assertIn(strength, VEIL_STRENGTHS)

    def test_light_pictures_get_dark_text_and_dark_pictures_white_text_without_a_heavy_veil(self):
        from apps.creative_generation.compositor import _text_style

        _veil, strength, ink, _accent = _text_style('#F6EEE0', '#83430B', '#D97706')
        self.assertEqual(strength, 0.35)
        self.assertNotEqual(ink, '#FFFFFF')
        _veil, strength, ink, _accent = _text_style('#2A3A5C', '#83430B', '#D97706')
        self.assertEqual(strength, 0.35)
        self.assertEqual(ink, '#FFFFFF')
