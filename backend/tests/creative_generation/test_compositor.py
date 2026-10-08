import io

from django.test import SimpleTestCase
from PIL import Image

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

    def test_no_white_plate_is_drawn_behind_the_logo(self):
        original = fake_image_bytes(size=(800, 800), color=(40, 90, 60))
        logo = self.flat_background_logo()

        result_bytes, _ = compose_creative(original, 'image/jpeg', logo_bytes=logo)

        composed = Image.open(io.BytesIO(result_bytes)).convert('RGB')
        # Top-right is where the old white logo plate used to go - it must be untouched photo now.
        for actual, expected in zip(composed.getpixel((780, 20)), (40, 90, 60)):  # JPEG rounding tolerance
            self.assertLessEqual(abs(actual - expected), 3)
        # The logo itself sits in the bottom strip, in white.
        bottom = composed.crop((0, 700, 400, 800))
        self.assertTrue(any(sum(px) > 700 for px in bottom.getdata()))

    def test_footer_uses_the_brand_color(self):
        original = fake_image_bytes(size=(800, 800), color=(255, 255, 255))
        brand = FakeBrandProfile(brand_colors=[{'name': 'Primary', 'hex': '#0000FF'}])

        result_bytes, _ = compose_creative(original, 'image/jpeg', headline='Hello', brand_profile=brand)

        composed = Image.open(io.BytesIO(result_bytes)).convert('RGB')
        r, g, b = composed.getpixel((790, 795))  # bottom-right corner: deepest part of the gradient, no text there
        self.assertGreater(b, r + 40)  # blue-tinted, not neutral grey

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
