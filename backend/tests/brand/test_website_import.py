import io
from unittest import mock

from django.urls import reverse
from PIL import Image
from rest_framework import status

from apps.brand import website_import
from apps.brand.models import BrandAsset, BrandProfile
from common.ai_errors import AIProviderNotConfigured

from .test_brand import BaseBrandTestCase

PAGE_HTML = """
<html><head>
<title>Acme Retail - Furniture for modern homes</title>
<meta name="description" content="Modern furniture, delivered free.">
<meta name="theme-color" content="#AA3BFF">
<link rel="stylesheet" href="/site.css">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Poppins:wght@400;700&family=Inter">
<link rel="icon" href="/fav.png" sizes="32x32">
<script type="application/ld+json">
{"@context": "https://schema.org", "@type": "Organization", "name": "Acme Retail",
 "logo": "https://acme.example/brand/logo-full.png", "telephone": "+91 98765 43210",
 "address": {"@type": "PostalAddress", "streetAddress": "12 MG Road", "addressLocality": "Pune", "addressCountry": "IN"}}
</script>
<style>.btn { background: #FF6A00; color: #fff } .btn:hover { background: #ff6a00 }</style>
</head><body>
<header><a href="/"><img class="site-logo" src="/logo-icon.png" alt="Acme"></a></header>
<img src="/photos/living-room.jpg" alt="Living room"><img src="/photos/tiny.jpg" alt="x"><img src="/img/arrow-icon.png">
<h1>Furniture made for modern homes</h1>
<p>Acme Retail sells sofas, tables and storage with free delivery across the country. We keep our words simple and warm.</p>
<a href="mailto:hello@acme.example?subject=Hi">Email</a><a href="/about">About us</a><a href="/products">Our products</a><a href="/careers">Careers</a>
<footer><img class="invert brightness-0" src="/logo-white.png" alt="Acme"></footer>
</body></html>
"""

DRAFT = {
    'brand_voice': 'Warm and plain-spoken.', 'tone': 'Friendly, practical', 'writing_style': 'Short sentences.',
    'visual_style': 'Bright, airy interiors.', 'typography_notes': '', 'dos': ['Mention free delivery', 'mention free delivery'],
    'donts': ['Avoid jargon'], 'keywords': ['modern', 'free delivery'], 'restricted_words': [],
    'customer_personas': [{'name': 'First-time buyer', 'summary': 'Furnishing a first flat.'}],
    'offers': [], 'campaign_information': '', 'industry': 'Retail - Furniture',
    'description': 'Sells modern furniture.', 'target_audience': 'Young homeowners', 'target_market': 'Pune, India',
    'products': ['Sofas', 'Tables'], 'services': ['Free delivery'], 'usp': 'Free delivery on every order', 'competitors': [],
}


def png_bytes():
    buffer = io.BytesIO()
    Image.new('RGB', (20, 20), color='purple').save(buffer, format='PNG')
    return buffer.getvalue()


def jpeg_bytes(size):
    buffer = io.BytesIO()
    Image.new('RGB', size, color='teal').save(buffer, format='JPEG')
    return buffer.getvalue()


def fake_fetch(url, max_bytes):
    if url.endswith('tiny.jpg'):
        return url, 'image/jpeg', jpeg_bytes((50, 40))
    if url.endswith('.jpg'):
        return url, 'image/jpeg', jpeg_bytes((600, 400))
    if url.endswith('.png'):
        return url, 'image/png', png_bytes()
    if url.endswith('/site.css'):
        return url, 'text/css', b'a { color: #AA3BFF } body { font-family: "Poppins", Arial, sans-serif }'
    return url, 'text/html; charset=utf-8', PAGE_HTML.encode()


class ScrapeTests(BaseBrandTestCase):
    def test_extracts_colors_fonts_logo_and_favicon(self):
        with mock.patch.object(website_import, '_fetch', side_effect=fake_fetch):
            site = website_import.scrape_website('acme.example')

        self.assertEqual(site['url'], 'https://acme.example')
        hexes = [c['hex'] for c in site['colors']]
        self.assertEqual(hexes[0], '#AA3BFF')
        self.assertIn('#FF6A00', hexes)
        self.assertEqual(site['colors'][0]['name'], 'Primary')
        self.assertNotIn('#FFFFFF', hexes)
        self.assertEqual([f['name'] for f in site['fonts']][:2], ['Poppins', 'Inter'])
        # The site's declared (JSON-LD) logo is the primary logo, not the small header icon;
        # the header icon becomes the secondary logo and the white footer variant is ignored.
        self.assertEqual(site['logo_url'], 'https://acme.example/brand/logo-full.png')
        self.assertEqual(site['secondary_logo_url'], 'https://acme.example/logo-icon.png')
        self.assertEqual(site['favicon_url'], 'https://acme.example/fav.png')
        self.assertEqual(site['contact'], {
            'email': 'hello@acme.example', 'phone': '+91 98765 43210', 'address': '12 MG Road, Pune, IN',
        })
        photo_urls = [url for url, _alt in site['images']]
        self.assertIn('https://acme.example/photos/living-room.jpg', photo_urls)
        self.assertFalse([u for u in photo_urls if 'logo' in u or 'icon' in u])
        self.assertIn('Furniture made for modern homes', site['text'])

    def test_follows_about_and_products_pages_but_not_others(self):
        fetched = []

        def tracking_fetch(url, max_bytes):
            fetched.append(url)
            return fake_fetch(url, max_bytes)

        with mock.patch.object(website_import, '_fetch', side_effect=tracking_fetch):
            website_import.scrape_website('https://acme.example')

        self.assertIn('https://acme.example/about', fetched)
        self.assertIn('https://acme.example/products', fetched)
        self.assertNotIn('https://acme.example/careers', fetched)

    def test_header_logo_is_used_when_the_site_declares_none(self):
        html = PAGE_HTML.replace('"logo": "https://acme.example/brand/logo-full.png",', '')
        with mock.patch.object(website_import, '_fetch', side_effect=lambda u, m: (u, 'text/html', html.encode())):
            site = website_import.scrape_website('https://acme.example')
        self.assertEqual(site['logo_url'], 'https://acme.example/logo-icon.png')
        self.assertIsNone(site['secondary_logo_url'])

    def test_og_image_is_not_mistaken_for_a_logo(self):
        html = '<html><head><meta property="og:image" content="/hero-banner.jpg"></head><body>hi</body></html>'
        parser = website_import._parse(html)
        self.assertEqual(website_import.pick_logos(parser, {}, 'https://acme.example'), (None, None))

    def test_rejects_private_addresses(self):
        for url in ('http://127.0.0.1', 'http://localhost', 'http://169.254.169.254/latest/meta-data', 'ftp://example.com'):
            with self.assertRaises(website_import.WebsiteImportError, msg=url):
                website_import._assert_public_url(url)

    def test_blank_url_is_rejected(self):
        with self.assertRaises(website_import.WebsiteImportError):
            website_import.normalize_url('   ')


class ImportEndpointTests(BaseBrandTestCase):
    def url(self, company=None):
        return reverse('brand:brand-import-from-website', kwargs={'company_id': (company or self.company).pk})

    def run_import(self, payload=None, draft=None):
        provider = mock.Mock()
        provider.generate_json.return_value = draft or DRAFT
        with mock.patch.object(website_import, '_fetch', side_effect=fake_fetch), \
                mock.patch.object(website_import, 'get_provider', return_value=provider):
            return self.client.post(self.url(), payload or {'url': 'acme.example'}, format='json')

    def test_fills_brand_and_company_fields(self):
        self.authenticate_as('admin@example.com', 'StrongPass123!')
        response = self.run_import()

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('Brand voice', response.data['filled'])
        self.assertIn('Primary logo', response.data['filled'])
        profile = BrandProfile.objects.get(company=self.company)
        self.assertEqual(profile.brand_voice, 'Warm and plain-spoken.')
        self.assertEqual(profile.dos, ['Mention free delivery'])  # de-duplicated
        self.assertEqual(profile.brand_colors[0]['hex'], '#AA3BFF')
        self.assertEqual(profile.fonts[0]['name'], 'Poppins')
        self.assertIn('logo-from-website', profile.logo.name)
        self.assertIn('secondary_logo-from-website', profile.secondary_logo.name)
        self.assertTrue(profile.favicon)
        self.assertIn('Secondary logo', response.data['filled'])
        assets = BrandAsset.objects.filter(company=self.company, category='reference_image')
        self.assertEqual([a.name for a in assets], ['living-room.jpg'])  # the 50x40 photo is too small
        self.assertEqual(assets[0].uploaded_by, self.admin)
        self.company.refresh_from_db()
        self.assertEqual(self.company.industry, 'Retail - Furniture')
        self.assertEqual(self.company.products, ['Sofas', 'Tables'])
        self.assertEqual(self.company.website, 'https://acme.example')
        self.assertEqual(self.company.contact_email, 'hello@acme.example')
        self.assertEqual(self.company.contact_phone, '+91 98765 43210')
        self.assertEqual(self.company.address, '12 MG Road, Pune, IN')

    def test_keeps_existing_values_unless_overwrite(self):
        self.authenticate_as('admin@example.com', 'StrongPass123!')
        BrandProfile.objects.create(company=self.company, brand_voice='Hand written voice')
        self.company.usp = 'Hand written USP'
        self.company.save()

        self.run_import()
        profile = BrandProfile.objects.get(company=self.company)
        self.assertEqual(profile.brand_voice, 'Hand written voice')
        self.assertEqual(profile.tone, 'Friendly, practical')  # empty field still filled
        self.company.refresh_from_db()
        self.assertEqual(self.company.usp, 'Hand written USP')

        self.run_import({'url': 'acme.example', 'overwrite': True})
        profile.refresh_from_db()
        self.company.refresh_from_db()
        self.assertEqual(profile.brand_voice, 'Warm and plain-spoken.')
        self.assertEqual(self.company.usp, 'Free delivery on every order')

    def test_client_cannot_import(self):
        self.authenticate_as('acmeclient@example.com', 'StrongPass123!')
        response = self.client.post(self.url(), {'url': 'acme.example'}, format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_unreachable_site_is_a_400_not_a_crash(self):
        self.authenticate_as('admin@example.com', 'StrongPass123!')
        with mock.patch.object(
            website_import, '_fetch', side_effect=website_import.WebsiteImportError('The website took too long to respond.'),
        ):
            response = self.client.post(self.url(), {'url': 'slow.example'}, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('too long', response.data['detail'])

    def test_missing_ai_key_is_a_503(self):
        self.authenticate_as('admin@example.com', 'StrongPass123!')
        provider = mock.Mock()
        provider.generate_json.side_effect = AIProviderNotConfigured('Groq API key is missing or invalid.')
        with mock.patch.object(website_import, '_fetch', side_effect=fake_fetch), \
                mock.patch.object(website_import, 'get_provider', return_value=provider):
            response = self.client.post(self.url(), {'url': 'acme.example'}, format='json')
        self.assertEqual(response.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)

    def test_url_is_required(self):
        self.authenticate_as('admin@example.com', 'StrongPass123!')
        response = self.client.post(self.url(), {}, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
