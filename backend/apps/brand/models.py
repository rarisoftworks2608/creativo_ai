from django.conf import settings
from django.db import models

from apps.companies.models import Company
from common.models import TimeStampedModel


def brand_identity_upload_path(instance, filename):
    return f'brand/{instance.company_id}/identity/{filename}'


def brand_asset_upload_path(instance, filename):
    return f'brand/{instance.company_id}/assets/{instance.category}/{filename}'


class BrandProfile(TimeStampedModel):
    """A company's brand profile (Epic 03): identity, guidelines and marketing information.

    Target audience / products / services / USP / competitors are already
    captured on Company (Epic 02) as the single source of truth for that
    business data; this model only adds the fields that are specific to the
    brand context and not already tracked there.
    """

    company = models.OneToOneField(Company, on_delete=models.CASCADE, related_name='brand_profile')

    # Brand Identity
    logo = models.ImageField(upload_to=brand_identity_upload_path, blank=True, null=True)
    secondary_logo = models.ImageField(upload_to=brand_identity_upload_path, blank=True, null=True)
    favicon = models.ImageField(upload_to=brand_identity_upload_path, blank=True, null=True)
    brand_colors = models.JSONField(
        default=list, blank=True,
        help_text='List of {"name": "Primary", "hex": "#AA3BFF"} objects.',
    )
    fonts = models.JSONField(
        default=list, blank=True,
        help_text='List of {"name": "Poppins", "usage": "Headings"} objects.',
    )
    typography_notes = models.TextField(blank=True, help_text='General typography guidance.')

    # Brand Guidelines
    brand_voice = models.TextField(blank=True)
    tone = models.TextField(blank=True)
    writing_style = models.TextField(blank=True)
    visual_style = models.TextField(blank=True)
    dos = models.JSONField(default=list, blank=True, help_text='List of things to do.')
    donts = models.JSONField(default=list, blank=True, help_text="List of things to avoid.")
    keywords = models.JSONField(default=list, blank=True, help_text='Preferred keywords/phrases.')
    restricted_words = models.JSONField(default=list, blank=True, help_text='Words/phrases to avoid.')

    # Marketing Information (brand-specific additions beyond Company's business info)
    customer_personas = models.JSONField(
        default=list, blank=True,
        help_text='List of {"name": ..., "summary": ...} persona objects.',
    )
    offers = models.JSONField(default=list, blank=True, help_text='List of current offers/promotions.')
    campaign_information = models.TextField(blank=True)

    class Meta:
        verbose_name = 'Brand Profile'

    def __str__(self):
        return f'Brand profile for {self.company.name}'


class BrandAsset(TimeStampedModel):
    """A single uploaded file in a company's brand asset library (Epic 03: Brand Assets)."""

    class Category(models.TextChoices):
        LOGO_UPLOAD = 'logo_upload', 'Logo Upload'
        REFERENCE_IMAGE = 'reference_image', 'Reference Image'
        PRODUCT_IMAGE = 'product_image', 'Product Image'
        DOCUMENT = 'document', 'Document'
        MARKETING_MATERIAL = 'marketing_material', 'Marketing Material'

    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='brand_assets')
    category = models.CharField(max_length=20, choices=Category.choices)
    file = models.FileField(upload_to=brand_asset_upload_path)
    name = models.CharField(max_length=255, blank=True)

    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='brand_assets_uploaded',
    )

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.name or self.file.name

    def save(self, *args, **kwargs):
        if not self.name and self.file:
            self.name = self.file.name.rsplit('/', 1)[-1]
        super().save(*args, **kwargs)
