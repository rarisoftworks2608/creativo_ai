"""Shared fixtures for the publishing / WhatsApp / analytics / reports / subscription tests."""

import datetime
import io
import shutil
import tempfile

from django.core.files.base import ContentFile
from django.test import override_settings
from django.urls import reverse
from PIL import Image

from apps.authentication.models import User
from apps.companies.models import ClientProfile, Company
from apps.content_calendar.models import ContentCalendarItem
from apps.creative_generation.models import GenerationRequest, GenerationVariation
from apps.social_accounts.models import SocialAccount
from common.crypto import encrypt_secret
from config.celery import app as celery_app

PASSWORD = 'StrongPass123!'


def png_bytes(color='purple', size=(16, 20)):
    buffer = io.BytesIO()
    Image.new('RGB', size, color=color).save(buffer, format='PNG')
    return buffer.getvalue()


class TempMediaMixin:
    """Writes every uploaded/generated file of the test class into a throwaway folder."""

    @classmethod
    def setUpClass(cls):
        cls._media_root = tempfile.mkdtemp(prefix='test_media_')
        cls._media_override = override_settings(MEDIA_ROOT=cls._media_root)
        cls._media_override.enable()
        super().setUpClass()

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        cls._media_override.disable()
        shutil.rmtree(cls._media_root, ignore_errors=True)


class EagerCeleryMixin:
    """Runs .delay() synchronously (see test_creative_generation for why app.conf is mutated)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._original_eager = celery_app.conf.task_always_eager
        cls._original_propagates = celery_app.conf.task_eager_propagates
        celery_app.conf.task_always_eager = True
        celery_app.conf.task_eager_propagates = True

    @classmethod
    def tearDownClass(cls):
        celery_app.conf.task_always_eager = cls._original_eager
        celery_app.conf.task_eager_propagates = cls._original_propagates
        super().tearDownClass()


class PlatformFixturesMixin:
    """Admin, two companies, a client at the first, and helpers to build approved content."""

    def setUp(self):
        super().setUp()
        self.admin = User.objects.create_superuser(email='admin@example.com', password=PASSWORD)
        self.company = Company.objects.create(name='Acme Retail', created_by=self.admin, website='https://acme.example')
        self.other_company = Company.objects.create(name='Other Co', created_by=self.admin)
        self.client_user = User.objects.create_user(
            email='client@example.com', password=PASSWORD, role=User.Role.CLIENT, phone_number='+91 98765 43210',
        )
        self.client_profile = ClientProfile.objects.create(user=self.client_user, company=self.company)

    def login(self, user):
        response = self.client.post(reverse('authentication:login'), {'email': user.email, 'password': PASSWORD})
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {response.data["access"]}')
        return response

    def make_item(self, *, company=None, status=ContentCalendarItem.Status.APPROVED, platforms=None, **extra):
        return ContentCalendarItem.objects.create(
            company=company or self.company, topic=extra.pop('topic', 'Festive offer'),
            content_type=extra.pop('content_type', 'Static Post'), platforms=platforms or ['instagram', 'facebook'],
            scheduled_date=extra.pop('scheduled_date', datetime.date.today() + datetime.timedelta(days=3)),
            status=status, created_by=self.admin, **extra,
        )

    def add_creative(self, item, *, variations=1, creative_type=GenerationRequest.CreativeType.POST):
        request = GenerationRequest.objects.create(
            company=item.company, content_calendar_item=item, creative_type=creative_type,
            prompt_brief=item.topic, status=GenerationRequest.Status.SUCCEEDED, variation_count=variations,
        )
        created = []
        for number in range(1, variations + 1):
            variation = GenerationVariation(
                generation_request=request, variation_number=number, caption=f'Caption {number}',
                headline=f'Headline {number}', cta='Shop now', hashtags=['#Diwali', 'Offer'],
            )
            variation.image.save(f'variation_{number}.png', ContentFile(png_bytes()), save=False)
            variation.save()
            created.append(variation)
        return request, created

    def make_account(self, platform='facebook', *, company=None, account_id='12345', **extra):
        return SocialAccount.objects.create(
            company=company or self.company, platform=platform, account_name=f'Acme {platform}',
            account_id=account_id, access_token=encrypt_secret('token-123'),
            status=extra.pop('status', SocialAccount.Status.CONNECTED), **extra,
        )
