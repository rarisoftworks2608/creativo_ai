import io

from django.test import SimpleTestCase
from PIL import Image

from apps.creative_generation.compositor import _brand_colors, compose_creative


def fake_image_bytes(size=(600, 600), color='blue', fmt='JPEG'):
    buf = io.BytesIO()
    Image.new('RGB', size, color).save(buf, format=fmt)
    return buf.getvalue()


class FakeBrandProfile:
    def __init__(self, brand_colors=None):
        self.brand_colors = brand_colors or []


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

    def test_logo_only_produces_a_valid_image(self):
        original = fake_image_bytes()
        logo_bytes = fake_image_bytes(size=(200, 80), color='red', fmt='PNG')

        result_bytes, _ = compose_creative(original, 'image/jpeg', logo_bytes=logo_bytes)

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
