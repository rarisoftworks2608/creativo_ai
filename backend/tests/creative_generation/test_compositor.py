import io

from django.test import SimpleTestCase
from PIL import Image, ImageDraw, ImageStat

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

    BROWN = (123, 90, 69)  # the test logo's own colour

    def brown(self, px):
        return all(abs(a - b) <= 14 for a, b in zip(px, self.BROWN))

    def noisy_side(self, side):
        """A calm cream picture whose left or right half-ish is busy with detail (a subject, flowers, drapes)."""
        photo = Image.new('RGB', (1024, 1280), self.LIGHT)
        box = (0, 0) if side == 'left' else (564, 0)
        photo.paste(Image.effect_noise((460, 1280), 70).convert('RGB'), box)
        buf = io.BytesIO()
        photo.save(buf, format='PNG')
        return buf.getvalue()

    def test_the_original_logo_keeps_its_own_colours_and_is_fixed_top_right_on_every_picture(self):
        # A calm picture: top-right.
        calm = self.compose(self.flat(self.LIGHT), logo_bytes=self.logo())
        self.assertGreater(self.count(calm, (512, 0, 1024, 300), self.brown), 15000)
        self.assertEqual(self.count(calm, (0, 0, 512, 300), self.brown), 0)
        # A busy top-right corner (flowers, lanterns): the logo does not move, same colours, same size.
        photo = Image.new('RGB', (1024, 1280), self.LIGHT)
        photo.paste(Image.effect_noise((424, 300), 70).convert('RGB'), (600, 0))
        buf = io.BytesIO()
        photo.save(buf, format='PNG')
        for seed in (None, 1, 2, 3):
            busy = self.compose(buf.getvalue(), logo_bytes=self.logo(), variation_seed=seed, headline='Diwali')
            self.assertGreater(self.count(busy, (512, 0, 1024, 300), self.brown), 15000, seed)
            self.assertEqual(self.count(busy, (0, 0, 512, 300), self.brown), 0, seed)

    def test_a_logo_that_would_vanish_into_the_picture_gets_a_plate_not_a_new_colour(self):
        # A brown logo on a dark brown picture: it is not recoloured, a light plate is put behind it instead.
        dark_brown = self.flat((70, 52, 40))
        lettered = Image.new('RGBA', (300, 100), (0, 0, 0, 0))  # letters with gaps between them, as real logos have
        for left in (30, 110, 190):
            lettered.paste(Image.new('RGBA', (60, 60), (*self.BROWN, 255)), (left, 20))
        buf = io.BytesIO()
        lettered.save(buf, format='PNG')
        image = self.compose(dark_brown, logo_bytes=buf.getvalue())
        self.assertGreater(self.count(image, (512, 0, 1024, 300), self.brown), 15000)  # the logo, as it is
        # The gap between the first two letters (about x 725-755) shows the plate directly behind the logo.
        gap = ImageStat.Stat(image.crop((730, 90, 750, 115)).convert('L')).mean[0]
        self.assertGreater(gap, 110)  # lighter than the picture around it (about 54)
        far = ImageStat.Stat(image.crop((100, 600, 300, 700)).convert('L')).mean[0]
        self.assertAlmostEqual(far, 54, delta=4)  # and the plate stays around the logo

    def test_the_plate_is_a_rounded_pill_with_a_clean_edge_not_a_box_or_a_smudge(self):
        dark_brown = self.flat((70, 52, 40))
        lettered = Image.new('RGBA', (300, 100), (0, 0, 0, 0))
        for left in (30, 110, 190):
            lettered.paste(Image.new('RGBA', (60, 60), (*self.BROWN, 255)), (left, 20))
        buf = io.BytesIO()
        lettered.save(buf, format='PNG')
        image = self.compose(dark_brown, logo_bytes=buf.getvalue())

        def luminance(point):
            r, g, b = image.getpixel(point)
            return r * 0.3 + g * 0.6 + b * 0.1

        # The logo sits at x 636-963, y 61-143; its plate reaches about 24 px further left and 14 px up and down.
        self.assertGreater(luminance((626, 102)), 200)   # inside the rounded end: a nearly white plate
        self.assertLess(luminance((604, 102)), 90)       # a clean edge: just outside it is the picture again
        self.assertLess(luminance((618, 52)), 90)        # the corner of the plate's box is rounded away, not filled in
        self.assertGreater(luminance((800, 50)), 200)    # while the top edge of the plate is solid

    def test_the_same_picture_gets_different_compositions_for_different_seeds_and_the_same_one_for_the_same_seed(self):
        photo = self.flat(self.LIGHT)
        copy = {'eyebrow': 'Happy', 'headline': 'Diwali', 'description': 'May this season bring light and joy.', 'cta': 'Visit us'}

        def render(seed):
            buf = io.BytesIO()
            self.compose(photo, logo_bytes=self.logo(), creative_type='festival_creative', variation_seed=seed, **copy).save(buf, format='PNG')
            return buf.getvalue()

        renders = {seed: render(seed) for seed in range(1, 9)}
        self.assertGreaterEqual(len(set(renders.values())), 4)  # clearly different layouts and typography
        self.assertEqual(render(3), renders[3])  # deterministic for a seed

    def test_the_default_placement_is_a_side_aligned_stack_in_the_open_part_not_a_centred_template(self):
        image = self.compose(
            self.flat(self.LIGHT), eyebrow='Happy', headline='Diwali', description='May this season bring light and joy.',
        )
        self.assertGreater(self.count(image, (0, 800, 1024, 1280), self.dark_ink), 600)
        self.assertEqual(self.count(image, (0, 0, 1024, 250), self.dark_ink), 0)  # nothing up in the logo's row
        columns = [x for x in range(0, 1024, 4) if self.count(image, (x, 800, x + 4, 1280), self.dark_ink)]
        self.assertGreater(abs((columns[0] + columns[-1]) / 2 - 512), 100)  # not centred: it hugs a side

    def test_the_text_goes_to_the_calm_side_the_picture_was_asked_to_leave(self):
        copy = {'eyebrow': 'Happy', 'headline': 'Diwali', 'description': 'May this season bring light and joy.'}
        # Calm on the right (busy left): the stack is on the right, for every seed.
        for seed in (None, 1, 2, 3, 4):
            image = self.compose(self.noisy_side('left'), composition='right', variation_seed=seed, **copy)
            self.assertGreater(self.count(image, (480, 250, 1024, 1280), self.dark_ink), 500, seed)
        # Calm on the left (busy right): the stack is on the left.
        for seed in (None, 1, 2, 3, 4):
            image = self.compose(self.noisy_side('right'), composition='left', variation_seed=seed, **copy)
            self.assertGreater(self.count(image, (0, 250, 560, 1280), self.dark_ink), 500, seed)

    def test_a_picture_that_ignored_the_composition_is_laid_out_by_what_it_really_looks_like(self):
        # Asked for calm space on the left, but the left is busy: the text goes to the calm right instead.
        image = self.compose(self.noisy_side('left'), composition='left', headline='Diwali', description='A warm wish.')
        self.assertGreater(self.count(image, (480, 250, 1024, 1280), self.dark_ink), 300)

    def test_hd_output_enlarges_the_picture_before_the_text_and_logo_are_drawn_and_never_reduces_it(self):
        copy = {'eyebrow': 'Happy', 'headline': 'Diwali', 'description': 'May this season bring light and joy.'}
        hd = self.compose(self.flat(self.LIGHT), logo_bytes=self.logo(), output_width=2048, **copy)
        self.assertEqual(hd.size, (2048, 2560))
        standard = self.compose(self.flat(self.LIGHT), logo_bytes=self.logo(), **copy)
        self.assertEqual(standard.size, (1024, 1280))
        # The text and the logo are set at the final size, not enlarged with the picture: about four times the pixels.
        self.assertGreater(self.count(hd, (0, 0, 2048, 2560), self.brown), 3.5 * self.count(standard, (0, 0, 1024, 1280), self.brown))
        self.assertGreater(self.count(hd, (0, 0, 2048, 2560), self.dark_ink), 3 * self.count(standard, (0, 0, 1024, 1280), self.dark_ink))
        # A picture already that wide, or wider, is kept as it is.
        self.assertEqual(self.compose(self.flat(self.LIGHT, size=(1024, 1280)), output_width=800, **copy).size, (1024, 1280))
        wide = self.compose(self.flat(self.LIGHT, size=(2400, 3000)), output_width=2048, **copy)
        self.assertEqual(wide.size, (2400, 3000))

    def test_the_hd_picture_is_cropped_to_the_ratio_first_and_keeps_its_ratio(self):
        tall = self.compose(self.flat(self.LIGHT, size=(1024, 1536)), output_width=2048, headline='Diwali')
        self.assertEqual(tall.size, (2048, 2560))  # 4:5, cropped before it was enlarged

    def test_the_jpeg_steps_its_quality_down_only_when_the_file_would_be_too_big_to_send(self):
        from unittest import mock

        from apps.creative_generation import compositor

        noisy = Image.effect_noise((800, 1000), 80).convert('RGB')
        full = compositor._encode_jpeg(noisy)
        with mock.patch.object(compositor, 'MAX_JPEG_BYTES', len(full) // 2):
            smaller = compositor._encode_jpeg(noisy)
        self.assertLess(len(smaller), len(full))
        self.assertTrue(full.startswith(b'\xff\xd8') and smaller.startswith(b'\xff\xd8'))
        photo = self.flat(self.LIGHT)
        self.assertLessEqual(len(compositor._encode_jpeg(Image.open(io.BytesIO(photo)).convert('RGB'))), compositor.MAX_JPEG_BYTES)

    def test_the_regular_weight_is_a_lighter_headline_than_the_bold_one(self):
        from apps.creative_generation.compositor import _headline_font

        def ink(weight):
            canvas = Image.new('L', (700, 200), 255)
            ImageDraw.Draw(canvas).text((10, 10), 'Diwali', font=_headline_font(weight, 120), fill=0)
            return sum(1 for px in canvas.getdata() if px < 128)

        self.assertLess(ink('regular'), ink('bold') * 0.85)

    def test_the_veil_behind_auto_text_has_no_hard_edge(self):
        image = self.compose(self.flat(self.DARK), headline='Big news', description='Read all about it.')
        column = [ImageStat.Stat(image.crop((8, y, 24, y + 1)).convert('L')).mean[0] for y in range(0, 1280, 8)]
        steps = [abs(b - a) for a, b in zip(column, column[1:])]
        self.assertLess(max(steps), 14)  # brightness changes gradually down the picture

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

    def test_the_text_stays_readable_over_the_brightest_spot_behind_it_not_just_the_average(self):
        from apps.creative_generation.compositor import _contrast_ratio, _luminance_extremes, _mix, _rgb, _text_style

        # A mostly dark picture with bright marigolds in it: the average alone would allow a faint veil.
        zone = Image.new('RGB', (200, 200), (40, 40, 60))
        zone.paste((255, 200, 40), (0, 0, 200, 60))
        bright, dark = _luminance_extremes(zone)
        self.assertEqual(bright, '#FFC828')
        self.assertEqual(dark, '#28283C')
        mean = '#%02X%02X%02X' % tuple(int(v) for v in ImageStat.Stat(zone).mean)
        veil, strength, ink, _accent = _text_style(mean, '#83430B', '#D97706', bright, dark)
        _gentle_veil, gentle_strength, _ink, _accent = _text_style(mean, '#83430B', '#D97706')
        self.assertGreater(strength, gentle_strength)
        self.assertGreaterEqual(_contrast_ratio(ink, _mix(bright, _rgb(veil), strength)), 4.5)

    def test_the_veil_holds_full_strength_from_where_the_text_starts(self):
        from apps.creative_generation.compositor import _vertical_gradient

        veil = _vertical_gradient((10, 100), '#000000', 200, ramp=0.2)
        alphas = [veil.getpixel((0, y))[3] for y in range(100)]
        self.assertEqual(alphas[0], 0)
        self.assertEqual(alphas[20], 200)
        self.assertEqual(alphas[99], 200)

    def test_light_pictures_get_dark_text_and_dark_pictures_white_text_without_a_heavy_veil(self):
        from apps.creative_generation.compositor import _text_style

        # Text that already reads on the picture gets no veil at all.
        _veil, strength, ink, _accent = _text_style('#F6EEE0', '#83430B', '#D97706')
        self.assertEqual(strength, 0.0)
        self.assertNotEqual(ink, '#FFFFFF')
        _veil, strength, ink, _accent = _text_style('#2A3A5C', '#83430B', '#D97706')
        self.assertEqual(strength, 0.0)
        self.assertEqual(ink, '#FFFFFF')
        # A mid-tone picture where neither reads on its own gets a veil, but not the heaviest.
        _veil, strength, _ink, _accent = _text_style('#9A9A9A', '#83430B', '#D97706')
        self.assertGreater(strength, 0.0)
        self.assertLess(strength, 0.8)


class TypographyTests(SimpleTestCase):
    """The premium editorial type hierarchy: light weights, an italic last word, soft body copy, a tracked kicker,
    a quiet CTA - and nothing cut short."""

    def draw(self):
        from PIL import ImageDraw

        return ImageDraw.Draw(Image.new('RGB', (1024, 1280), 'white'))

    def style(self, name='web_editorial'):
        from apps.creative_generation.art_direction import STYLE_PRESETS

        return STYLE_PRESETS[name]

    def parts(self, *, text_width=540, align='left', style=None, **copy):
        from apps.creative_generation.compositor import _build_text_parts

        fields = {'eyebrow': '', 'headline': '', 'description': '', 'cta': ''}
        fields.update(copy)
        return _build_text_parts(
            self.draw(), align=align, text_width=text_width, width=1024, brand_profile=None,
            style=style or self.style(), **fields,
        )

    def ink(self, font, text='Diwali happiness'):
        from PIL import ImageDraw

        canvas = Image.new('L', (900, 160), 255)
        ImageDraw.Draw(canvas).text((10, 10), text, font=font, fill=0)
        return sum(1 for px in canvas.getdata() if px < 128)

    def test_poppins_regular_is_registered_so_body_copy_is_really_regular_not_semibold(self):
        from apps.creative_generation.compositor import _brand_font

        self.assertTrue(str(_brand_font(None, 'regular', 60).path).endswith('Poppins-Regular.ttf'))
        self.assertTrue(str(_brand_font(None, 'semibold', 60).path).endswith('Poppins-SemiBold.ttf'))
        self.assertLess(self.ink(_brand_font(None, 'regular', 60)), self.ink(_brand_font(None, 'semibold', 60)) * 0.9)

    def test_the_last_word_of_the_headline_is_set_in_the_italic_cut(self):
        parts = self.parts(headline="Building Tomorrow's Businesses, Today")
        lines, font, _height, role, tail, emphasis = parts[0][1]
        self.assertEqual(role, 'headline')
        self.assertIsNone(emphasis)  # only the accent-word presets mark words
        word, italic = tail
        self.assertEqual(word, 'Today')
        self.assertTrue(str(italic.path).endswith('PlayfairDisplay-Italic-Variable.ttf'))
        self.assertEqual(italic.size, font.size)

    def test_there_is_no_italic_tail_for_one_word_caps_brand_font_devanagari_or_a_preset_without_it(self):
        def tail(style='web_editorial', **copy):
            return self.parts(style=self.style(style), **copy)[0][1][4]

        self.assertIsNone(tail(headline='Diwali'))
        self.assertIsNone(tail(headline='Elevate Every Moment', style='serif_caps'))  # caps
        self.assertIsNone(tail(headline='Elevate Every Moment', style='quiet_luxury'))  # not in this preset
        self.assertIsNone(tail(headline='Elevate Every Moment', style='modern_caps'))  # the brand's own font
        self.assertIsNone(tail(headline='\u0936\u0941\u092d \u0926\u0940\u092a\u093e\u0935\u0932\u0940'))
        self.assertIsNotNone(tail(headline='Elevate Every Moment'))

    def test_the_italic_word_is_drawn_in_italic_on_the_same_baseline_and_in_every_alignment(self):
        from PIL import ImageDraw

        from apps.creative_generation.compositor import _draw_line, _headline_font, _italic_headline_font

        font, italic = _headline_font('regular', 100), _italic_headline_font('regular', 100)

        def render(tail, align):
            canvas = Image.new('L', (1000, 220), 255)
            _draw_line(ImageDraw.Draw(canvas), {'left': 20, 'center': 500, 'right': 980}[align], 30, 'Businesses Today', font, 0, align, tail)
            return canvas

        for align in ('left', 'center', 'right'):
            plain, with_tail = render(None, align), render(('Today', italic), align)
            self.assertNotEqual(list(plain.getdata()), list(with_tail.getdata()), align)  # the last word differs
            for canvas in (plain, with_tail):
                xs = [x for x in range(1000) if any(canvas.getpixel((x, y)) < 128 for y in range(220))]
                self.assertLess(xs[-1], 1000, align)
                self.assertGreater(xs[0], 0, align)
        # The text before the italic word is exactly as it would be without one.
        left_plain, left_tail = render(None, 'left'), render(('Today', italic), 'left')
        self.assertEqual(list(left_plain.crop((0, 0, 380, 220)).getdata()), list(left_tail.crop((0, 0, 380, 220)).getdata()))

    def test_a_line_that_does_not_end_with_the_tail_word_is_left_alone(self):
        from PIL import ImageDraw

        from apps.creative_generation.compositor import _draw_line, _headline_font, _italic_headline_font

        font, italic = _headline_font('regular', 100), _italic_headline_font('regular', 100)
        one, two = Image.new('L', (900, 200), 255), Image.new('L', (900, 200), 255)
        _draw_line(ImageDraw.Draw(one), 10, 10, 'Building Tomorrow', font, 0, 'left', ('Today', italic))
        _draw_line(ImageDraw.Draw(two), 10, 10, 'Building Tomorrow', font, 0, 'left', None)
        self.assertEqual(list(one.getdata()), list(two.getdata()))

    def test_the_body_copy_shrinks_to_fit_a_narrow_column_and_is_never_cut_with_an_ellipsis(self):
        description = 'Tailored experiences that fuse technology, design, and impact for unforgettable corporate gatherings.'
        for text_width in (410, 360, 330):
            parts = self.parts(text_width=text_width, description=description)
            lines = parts[0][1][0]
            self.assertEqual(' '.join(lines), description, text_width)
            self.assertFalse(any('...' in line for line in lines), text_width)
            self.assertLessEqual(len(lines), 4, text_width)

    def test_a_truly_overlong_description_is_still_cut_cleanly_as_a_last_resort(self):
        parts = self.parts(text_width=330, description='word ' * 120)
        lines = parts[0][1][0]
        self.assertLessEqual(len(lines), 4)
        self.assertTrue(lines[-1].endswith('...'))

    def test_a_kicker_of_keywords_is_tracked_soft_and_shrinks_to_fit_the_column(self):
        from apps.creative_generation.compositor import _brand_font, _kicker_spacing, _spaced_width

        font = _brand_font(None, 'regular', 22)
        self.assertGreater(_kicker_spacing(font, 'tracked'), _kicker_spacing(font, 'plain'))
        self.assertEqual(_kicker_spacing(font, 'plain'), 3)
        for text_width in (540, 410, 360):  # 410 is the narrowest column any layout uses
            parts = self.parts(text_width=text_width, eyebrow='Strategy / Technology / Growth')
            text, kicker_font, kicker = parts[0][1]
            self.assertEqual(kicker, 'tracked')
            self.assertLessEqual(_spaced_width(self.draw(), text.upper(), kicker_font, _kicker_spacing(kicker_font, kicker)), text_width)

    def test_the_underlined_link_keeps_the_calls_sentence_case_the_others_are_capitals(self):
        quiet = self.parts(style=self.style('web_editorial'), cta='Explore Our Services')[0][1]
        self.assertEqual((quiet[0], quiet[4]), ('Explore Our Services', 'underline'))
        self.assertTrue(str(quiet[1].path).endswith('Poppins-Regular.ttf'))
        loud = self.parts(style=self.style('gold_serif'), cta='Explore Our Services')[0][1]
        self.assertEqual((loud[0], loud[4]), ('EXPLORE OUR SERVICES', 'outline'))

    def test_the_headline_ink_body_ink_and_kicker_ink_are_painted_in_their_own_tones(self):
        from apps.creative_generation.compositor import _paint_parts

        draw_target = Image.new('RGB', (1024, 1280), 'white')
        from PIL import ImageDraw

        parts = self.parts(eyebrow='Strategy', headline='Building Tomorrow Today', description='We help ambitious brands.')
        _paint_parts(
            ImageDraw.Draw(draw_target), parts, x=72, y=100, align='left', width=1024, ink='#000000',
            accent_color='#0000FF', headline_color='#FF0000', body_color='#00AA00', muted_color='#AA00AA',
        )
        colours = {px for px in draw_target.getdata()}

        def has(rgb, tolerance=60):
            return any(all(abs(a - b) <= tolerance for a, b in zip(px, rgb)) and px != (255, 255, 255) for px in colours)

        self.assertTrue(has((255, 0, 0)))    # the headline
        self.assertTrue(has((0, 170, 0)))    # the body copy
        self.assertTrue(has((170, 0, 170)))  # the tracked kicker

    def test_straight_quotes_become_curly_ones_at_draw_time_for_latin_text_only(self):
        from apps.creative_generation.compositor import _typographic

        self.assertEqual(_typographic("Building Tomorrow's Businesses, Today"), 'Building Tomorrow\u2019s Businesses, Today')
        self.assertEqual(_typographic("'Quoted' words"), '\u2018Quoted\u2019 words')
        self.assertEqual(_typographic('He said "hi" to "them"'), 'He said \u201chi\u201d to \u201cthem\u201d')
        self.assertEqual(_typographic('("Quoted")'), '(\u201cQuoted\u201d)')
        self.assertEqual(_typographic('No quotes here'), 'No quotes here')
        self.assertEqual(_typographic(''), '')
        hindi = "\u0936\u0941\u092d \u0926\u0940\u092a\u093e\u0935\u0932\u0940 's"
        self.assertEqual(_typographic(hindi), hindi)  # Devanagari text is left exactly as it is

    def test_the_headline_is_set_with_a_curly_apostrophe(self):
        parts = self.parts(headline="Building Tomorrow's Businesses, Today")
        self.assertIn('Tomorrow\u2019s', ' '.join(parts[0][1][0]))
        self.assertNotIn("'", ' '.join(parts[0][1][0]))

    def test_every_bundled_latin_font_has_the_curly_quote_glyphs_so_none_renders_as_a_missing_box(self):
        from apps.creative_generation.compositor import (
            BRAND_FONT_LIBRARY, _brand_font, _headline_font, _italic_headline_font,
        )

        fonts = [_headline_font('regular', 100), _headline_font('bold', 100), _italic_headline_font('regular', 100)]
        for family in BRAND_FONT_LIBRARY:
            profile = type('Brand', (), {'fonts': [{'name': family}]})()
            fonts += [_brand_font(profile, 'regular', 100), _brand_font(profile, 'semibold', 100), _brand_font(profile, 'bold', 100)]
        missing = fonts[0].getmask('\ue000')  # a private-use code point: what a font draws for a glyph it lacks
        for font in fonts:
            for char in '\u2019\u2018\u201c\u201d':
                glyph = font.getmask(char)
                self.assertGreater(sum(1 for px in glyph if px > 127), 0, (font.path, char))  # it draws something
                self.assertNotEqual(glyph.size, font.getmask('\ue000').size, (font.path, char))  # and it is not .notdef
            self.assertLess(font.getlength('\u2019'), 0.6 * font.size, font.path)  # a quote mark, not a wide box
        self.assertIsNotNone(missing)

    def test_the_whole_composition_with_the_premium_look_renders_the_italic_word_and_a_soft_body(self):
        from apps.creative_generation.compositor import compose_creative

        photo = io.BytesIO()
        Image.new('RGB', (1024, 1280), (232, 238, 244)).save(photo, format='PNG')
        brand = FakeBrandProfile(brand_colors=[{'name': 'Primary', 'hex': '#152F49'}, {'name': 'Secondary', 'hex': '#14A79C'}])
        data, _ = compose_creative(
            photo.getvalue(), 'image/png', eyebrow='Strategy / Technology / Growth', headline="Building Tomorrow's Businesses, Today",
            description='We help ambitious brands turn ideas into impact.', cta='Explore Our Services', brand_profile=brand,
            creative_type='event_creative', variation_seed=None, composition='left', output_width=1536,
        )
        image = Image.open(io.BytesIO(data)).convert('RGB')
        self.assertEqual(image.size, (1536, 1920))
        dark = sum(1 for px in image.getdata() if sum(px) < 240)
        self.assertGreater(dark, 3000)  # the headline's dark ink is there ...
        self.assertLess(dark, 0.08 * image.width * image.height)  # ... and it is a light, airy composition


class PosterFrameTests(SimpleTestCase):
    """A business creative is dressed as a designed poster: the kicker in a header row opposite the logo, a services
    strip and a footer along the bottom, the text stack in the space between. Greetings are never framed."""

    DARK = (24, 32, 64)
    COPY = {
        'eyebrow': 'Build / Automate / Transform', 'headline': 'Ideas Into Innovation. Technology Into Growth.',
        'description': 'Modern solutions for a smarter tomorrow.', 'cta': 'Explore more',
    }
    FRAME = {
        'highlights': ['Web Development', 'ERP Solutions', 'AI & Automation', 'Digital Transformation'],
        'tagline': 'Your Technology Partner', 'brand_name': 'Rari Softworks LLP', 'website': 'https://rarisoftworks.com/',
    }

    def photo(self, size=(1024, 1280)):
        buf = io.BytesIO()
        Image.new('RGB', size, self.DARK).save(buf, format='PNG')
        return buf.getvalue()

    def logo(self):
        image = Image.new('RGBA', (300, 100), (0, 0, 0, 0))
        image.paste(Image.new('RGBA', (240, 60), (123, 90, 69, 255)), (30, 20))
        buf = io.BytesIO()
        image.save(buf, format='PNG')
        return buf.getvalue()

    def render(self, *, frame=True, creative_type='promotional_creative', seed=3, **overrides):
        brand = FakeBrandProfile(brand_colors=[{'name': 'Primary', 'hex': '#83430B'}, {'name': 'Secondary', 'hex': '#D97706'}])
        fields = {**self.COPY, **(self.FRAME if frame else {}), **overrides}
        data, _ = compose_creative(
            self.photo(), 'image/png', brand_profile=brand, logo_bytes=self.logo(), creative_type=creative_type,
            variation_seed=seed, **fields,
        )
        return data

    def image(self, **kwargs):
        return Image.open(io.BytesIO(self.render(**kwargs))).convert('RGB')

    def light(self, image, box, floor=200):
        return sum(1 for px in image.crop(box).getdata() if min(px) > floor)

    @staticmethod
    def amber(px):
        return px[0] > 180 and 90 < px[1] < 170 and px[2] < 80

    def test_the_footer_has_the_company_name_and_sign_off_on_the_left_and_the_website_after_a_rule_on_the_right(self):
        image = self.image()
        self.assertGreater(self.light(image, (60, 1190, 420, 1232), 150), 100)   # "Rari Softworks LLP", "Your Technology Partner"
        self.assertGreater(self.light(image, (780, 1185, 960, 1222), 150), 60)   # "rarisoftworks.com" - no scheme, no www, no slash
        self.assertGreater(sum(1 for px in image.crop((640, 1190, 790, 1215)).getdata() if self.amber(px)), 20)  # the accent rule

    def test_the_services_strip_has_four_columns_with_hairline_dividers(self):
        image = self.image()
        for column in range(4):
            left = 72 + 220 * column + 10
            self.assertGreater(self.light(image, (left, 1070, left + 200, 1160), 150), 80, column)
        for index in (1, 2, 3):
            x = 72 + 220 * index
            lit = max(sum(image.getpixel((xx, 1110))) / 3 for xx in (x - 1, x, x + 1))
            self.assertGreater(lit, 70, index)  # a hairline in a tone between the ink and the picture (the picture is about 40)

    def test_the_kicker_is_a_header_row_opposite_the_logo_followed_by_a_short_accent_rule(self):
        image = self.image()
        self.assertGreater(self.light(image, (72, 85, 480, 120), 150), 50)
        self.assertGreater(sum(1 for px in image.crop((72, 90, 700, 115)).getdata() if self.amber(px)), 20)
        # The logo is still the original file, top-right, with a plate because brown would vanish on this picture.
        brown = lambda px: all(abs(a - b) <= 14 for a, b in zip(px, (123, 90, 69)))  # noqa: E731
        self.assertGreater(sum(1 for px in image.crop((512, 0, 1024, 300)).getdata() if brown(px)), 8000)

    def test_the_text_stack_keeps_clear_of_the_header_the_strip_and_the_footer(self):
        for seed in (None, 1, 2, 3, 4, 5, 6):
            image = self.image(seed=seed)
            self.assertEqual(self.light(image, (0, 162, 1024, 182)), 0, seed)     # between the header row and the stack
            self.assertEqual(self.light(image, (0, 1050, 1024, 1072)), 0, seed)   # between the stack and the strip

    def test_a_greeting_or_a_testimonial_is_never_framed_even_when_the_services_and_website_are_known(self):
        for creative_type in ('festival_creative', 'testimonial_creative'):
            image = self.image(creative_type=creative_type)
            self.assertEqual(self.light(image, (0, 1200, 1024, 1280), 150), 0, creative_type)

    def test_without_services_or_a_website_there_is_no_frame_and_the_kicker_stays_in_the_text_stack(self):
        bare = self.image(frame=False)
        self.assertEqual(self.light(bare, (0, 1200, 1024, 1280), 150), 0)
        self.assertNotEqual(self.render(frame=False), self.render(frame=True))

    def test_the_website_in_the_footer_is_the_call_to_action_so_the_button_is_dropped(self):
        self.assertEqual(self.render(cta='Explore more'), self.render(cta=''))
        # Without a website the call to action stays.
        no_site = {'website': ''}
        self.assertNotEqual(self.render(cta='Explore more', **no_site), self.render(cta='', **no_site))

    def test_one_service_is_not_a_strip_and_at_most_four_are_drawn(self):
        self.assertEqual(self.render(highlights=['Only one']), self.render(highlights=[]))
        self.assertEqual(
            self.render(highlights=['A one', 'B two', 'C three', 'D four']),
            self.render(highlights=['A one', 'B two', 'C three', 'D four', 'E five', 'F six']),
        )

    def test_the_same_seed_gives_the_same_poster_and_different_seeds_different_ones(self):
        self.assertEqual(self.render(seed=5), self.render(seed=5))
        self.assertGreaterEqual(len({self.render(seed=seed) for seed in range(1, 9)}), 3)

    def test_the_website_is_printed_without_the_scheme_www_or_path(self):
        from apps.creative_generation.compositor import _site_label

        self.assertEqual(_site_label('https://rarisoftworks.com/'), 'rarisoftworks.com')
        self.assertEqual(_site_label('http://www.Example.com/about?x=1'), 'example.com')
        self.assertEqual(_site_label('rarisoftworks.com'), 'rarisoftworks.com')
        self.assertEqual(_site_label(''), '')
        self.assertEqual(_site_label(None), '')

    def test_the_services_labels_are_sanitised_like_the_rest_of_the_copy(self):
        # Smart punctuation from the text AI must not render as a missing-glyph box.
        self.assertEqual(
            self.render(highlights=['AI – Automation', 'ERP “Solutions”']),
            self.render(highlights=['AI - Automation', 'ERP "Solutions"']),
        )


class AccentHeadlineTests(SimpleTestCase):
    """The poster headline: one sentence per line, the word that closes each sentence in the accent colour, over a
    small widely spaced sub-line with a short rule."""

    def parts(self, *, text_width=900, **copy):
        from apps.creative_generation.art_direction import STYLE_PRESETS
        from apps.creative_generation.compositor import _build_text_parts

        fields = {'eyebrow': '', 'headline': '', 'description': '', 'cta': ''}
        fields.update(copy)
        return _build_text_parts(
            ImageDraw.Draw(Image.new('RGB', (1024, 1280), 'white')), align='left', text_width=text_width, width=1024,
            brand_profile=None, style=STYLE_PRESETS['tech_luxe'], **fields,
        )

    def test_each_sentence_is_a_line_and_the_closing_word_of_each_is_marked(self):
        from apps.creative_generation.compositor import _emphasis_by_line

        parts = self.parts(headline='Ideas Into Innovation. Technology Into Growth.')
        lines, _font, _height, role, tail, emphasis = parts[0][1]
        self.assertEqual(role, 'headline')
        self.assertEqual(lines, ['Ideas Into Innovation.', 'Technology Into Growth.'])
        self.assertEqual(emphasis, [{2}, {2}])
        self.assertIsNone(tail)
        self.assertEqual(_emphasis_by_line(['Building Tomorrow’s', 'Businesses, Today']), [set(), {1}])  # the last word of the headline
        self.assertEqual(_emphasis_by_line(['Diwali']), [{0}])

    def test_a_long_sentence_wraps_inside_its_column_and_only_its_last_word_is_marked(self):
        parts = self.parts(text_width=420, headline='Ideas Into Innovation And Everything After.')
        lines, _font, _height, _role, _tail, emphasis = parts[0][1]
        self.assertGreater(len(lines), 1)
        self.assertEqual(sum(len(marked) for marked in emphasis), 1)
        self.assertEqual(emphasis[-1], {len(lines[-1].split()) - 1})

    def test_the_description_becomes_a_widely_spaced_caps_sub_line_with_a_rule_after_it(self):
        parts = self.parts(headline='Ideas Into Innovation.', description='Modern solutions for a smarter tomorrow.')
        self.assertEqual([part[0] for part in parts], ['lines', 'spaced', 'divider'])
        lines, font, spacing, role = parts[1][1]
        self.assertEqual(role, 'body')
        self.assertEqual(' '.join(lines), 'MODERN SOLUTIONS FOR A SMARTER TOMORROW.')
        self.assertGreater(spacing, font.size * 0.15)  # widely spaced
        self.assertLess(font.size, 30)                  # and small
        self.assertEqual(parts[2][1], 'line')

    def test_a_long_sub_line_wraps_to_at_most_three_lines_without_being_cut(self):
        text = 'We help ambitious brands turn bold ideas into measurable growth with strategy technology and care.'
        parts = self.parts(text_width=360, headline='Ideas', description=text)
        lines = parts[1][1][0]
        self.assertLessEqual(len(lines), 3)
        self.assertEqual(' '.join(lines), text.upper())
        self.assertNotIn('...', ' '.join(lines))

    def test_hindi_text_keeps_the_ordinary_stack_with_no_tracked_capitals_and_no_marked_words(self):
        parts = self.parts(headline='शुभ दीपावली', description='शुभ दिवाली')
        self.assertNotIn('spaced', [part[0] for part in parts])
        self.assertIsNone(parts[0][1][5])
