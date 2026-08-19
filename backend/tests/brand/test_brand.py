import io

from django.urls import reverse
from PIL import Image
from rest_framework import status
from rest_framework.test import APITestCase

from apps.authentication.models import User
from apps.brand.models import BrandAsset, BrandProfile
from apps.companies.models import ClientProfile, Company


def make_image_file(name='logo.png'):
    buffer = io.BytesIO()
    Image.new('RGB', (10, 10), color='purple').save(buffer, format='PNG')
    buffer.seek(0)
    buffer.name = name
    return buffer


class BaseBrandTestCase(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(email='admin@example.com', password='StrongPass123!')
        self.company = Company.objects.create(name='Acme Retail', created_by=self.admin)
        self.company_user = User.objects.create_user(
            email='acmeclient@example.com', password='StrongPass123!', role=User.Role.CLIENT,
        )
        ClientProfile.objects.create(user=self.company_user, company=self.company, is_primary_contact=True)

        self.other_company = Company.objects.create(name='Other Co', created_by=self.admin)

    def authenticate_as(self, email, password):
        response = self.client.post(reverse('authentication:login'), {'email': email, 'password': password})
        access = response.data['access']
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {access}')
        return response


class BrandProfileTests(BaseBrandTestCase):
    def test_profile_is_created_on_first_access(self):
        self.authenticate_as('admin@example.com', 'StrongPass123!')
        self.assertFalse(BrandProfile.objects.filter(company=self.company).exists())

        url = reverse('brand:brand-profile', kwargs={'company_id': self.company.pk})
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(BrandProfile.objects.filter(company=self.company).exists())

    def test_admin_can_edit_brand_guidelines(self):
        self.authenticate_as('admin@example.com', 'StrongPass123!')
        url = reverse('brand:brand-profile', kwargs={'company_id': self.company.pk})
        response = self.client.patch(url, {
            'brand_voice': 'Confident and warm.',
            'tone': 'Friendly',
            'keywords': ['premium', 'trusted'],
            'restricted_words': ['cheap'],
            'brand_colors': [{'name': 'Primary', 'hex': '#AA3BFF'}],
            'fonts': [{'name': 'Poppins', 'usage': 'Headings'}],
            'customer_personas': [{'name': 'Busy Parent', 'summary': 'Time-poor, values convenience.'}],
            'offers': ['10% off first order'],
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['brand_voice'], 'Confident and warm.')
        self.assertEqual(response.data['keywords'], ['premium', 'trusted'])
        self.assertEqual(response.data['brand_colors'], [{'name': 'Primary', 'hex': '#AA3BFF'}])

    def test_rejects_invalid_hex_color(self):
        self.authenticate_as('admin@example.com', 'StrongPass123!')
        url = reverse('brand:brand-profile', kwargs={'company_id': self.company.pk})
        response = self.client.patch(url, {'brand_colors': [{'name': 'Primary', 'hex': 'not-a-color'}]}, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_client_can_view_own_brand_but_not_edit(self):
        self.authenticate_as('acmeclient@example.com', 'StrongPass123!')
        url = reverse('brand:brand-profile', kwargs={'company_id': self.company.pk})

        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        response = self.client.patch(url, {'brand_voice': 'Hacked'}, format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_client_cannot_view_other_companys_brand(self):
        self.authenticate_as('acmeclient@example.com', 'StrongPass123!')
        url = reverse('brand:brand-profile', kwargs={'company_id': self.other_company.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class BrandIdentityImageTests(BaseBrandTestCase):
    def test_admin_can_upload_and_remove_logo(self):
        self.authenticate_as('admin@example.com', 'StrongPass123!')
        upload_url = reverse('brand:brand-logo', kwargs={'company_id': self.company.pk})

        response = self.client.post(upload_url, {'file': make_image_file()}, format='multipart')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsNotNone(response.data['logo'])

        profile = BrandProfile.objects.get(company=self.company)
        self.assertTrue(bool(profile.logo))

        response = self.client.delete(upload_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        profile.refresh_from_db()
        self.assertFalse(bool(profile.logo))

    def test_client_cannot_upload_logo(self):
        self.authenticate_as('acmeclient@example.com', 'StrongPass123!')
        upload_url = reverse('brand:brand-logo', kwargs={'company_id': self.company.pk})
        response = self.client.post(upload_url, {'file': make_image_file()}, format='multipart')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_invalid_slot_404s(self):
        self.authenticate_as('admin@example.com', 'StrongPass123!')
        url = f"/api/v1/companies/{self.company.pk}/brand/not-a-slot/"
        response = self.client.post(url, {'file': make_image_file()}, format='multipart')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class BrandAssetTests(BaseBrandTestCase):
    def test_admin_can_upload_and_list_assets(self):
        self.authenticate_as('admin@example.com', 'StrongPass123!')
        url = reverse('brand:brand-asset-list-create', kwargs={'company_id': self.company.pk})

        response = self.client.post(url, {
            'category': BrandAsset.Category.PRODUCT_IMAGE,
            'file': make_image_file('product.png'),
        }, format='multipart')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['category'], 'product_image')
        self.assertEqual(response.data['name'], 'product.png')

        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 1)

    def test_category_filter(self):
        self.authenticate_as('admin@example.com', 'StrongPass123!')
        list_url = reverse('brand:brand-asset-list-create', kwargs={'company_id': self.company.pk})
        self.client.post(list_url, {
            'category': BrandAsset.Category.DOCUMENT, 'file': make_image_file('doc.png'),
        }, format='multipart')
        self.client.post(list_url, {
            'category': BrandAsset.Category.PRODUCT_IMAGE, 'file': make_image_file('prod.png'),
        }, format='multipart')

        response = self.client.get(list_url, {'category': 'document'})
        self.assertEqual(response.data['count'], 1)
        self.assertEqual(response.data['results'][0]['category'], 'document')

    def test_admin_can_delete_asset(self):
        self.authenticate_as('admin@example.com', 'StrongPass123!')
        list_url = reverse('brand:brand-asset-list-create', kwargs={'company_id': self.company.pk})
        created = self.client.post(list_url, {
            'category': BrandAsset.Category.DOCUMENT, 'file': make_image_file('doc.png'),
        }, format='multipart').data

        detail_url = reverse('brand:brand-asset-detail', kwargs={'company_id': self.company.pk, 'pk': created['id']})
        response = self.client.delete(detail_url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(BrandAsset.objects.filter(pk=created['id']).exists())

    def test_client_can_view_but_not_upload_assets(self):
        self.authenticate_as('admin@example.com', 'StrongPass123!')
        list_url = reverse('brand:brand-asset-list-create', kwargs={'company_id': self.company.pk})
        self.client.post(list_url, {
            'category': BrandAsset.Category.DOCUMENT, 'file': make_image_file('doc.png'),
        }, format='multipart')
        self.client.credentials()

        self.authenticate_as('acmeclient@example.com', 'StrongPass123!')
        response = self.client.get(list_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 1)

        response = self.client.post(list_url, {
            'category': BrandAsset.Category.DOCUMENT, 'file': make_image_file('doc2.png'),
        }, format='multipart')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
