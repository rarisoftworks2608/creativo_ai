from decimal import Decimal

from django.conf import settings
from django.db import models

from apps.companies.models import Company
from apps.content_calendar.models import ContentCalendarItem
from common.models import TimeStampedModel


def variation_image_upload_path(instance, filename):
    request = instance.generation_request
    return f'creative_generation/{request.company_id}/{request.id}/{filename}'


class GenerationRequest(TimeStampedModel):
    """A single request to generate creative variations (Epic 06: Generation Management)."""

    class CreativeType(models.TextChoices):
        # Legacy: these three used to bundle a platform + generic "post" format
        # together. Kept only so existing rows still display/validate correctly -
        # new generations use POST + the separate `platform` field below instead.
        INSTAGRAM_POST = 'instagram_post', 'Instagram Post'
        FACEBOOK_POST = 'facebook_post', 'Facebook Post'
        LINKEDIN_POST = 'linkedin_post', 'LinkedIn Post'
        POST = 'post', 'Post'
        CAROUSEL = 'carousel', 'Carousel'
        STORY = 'story', 'Story'
        PROMOTIONAL_CREATIVE = 'promotional_creative', 'Promotional Creative'
        FESTIVAL_CREATIVE = 'festival_creative', 'Festival Creative'
        PRODUCT_CREATIVE = 'product_creative', 'Product Creative'
        EDUCATIONAL_CREATIVE = 'educational_creative', 'Educational Creative'
        EVENT_CREATIVE = 'event_creative', 'Event Creative'
        ANNOUNCEMENT_CREATIVE = 'announcement_creative', 'Announcement Creative'
        TESTIMONIAL_CREATIVE = 'testimonial_creative', 'Testimonial Creative'

    class Platform(models.TextChoices):
        INSTAGRAM = 'instagram', 'Instagram'
        FACEBOOK = 'facebook', 'Facebook'
        LINKEDIN = 'linkedin', 'LinkedIn'
        GENERAL = 'general', 'General / Multi-platform'

    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        QUEUED = 'queued', 'Queued'
        PROCESSING = 'processing', 'Processing'
        SUCCEEDED = 'succeeded', 'Succeeded'
        FAILED = 'failed', 'Failed'

    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='generation_requests')
    content_calendar_item = models.ForeignKey(
        ContentCalendarItem, null=True, blank=True, on_delete=models.SET_NULL, related_name='generation_requests',
    )

    creative_type = models.CharField(max_length=30, choices=CreativeType.choices)
    platform = models.CharField(
        max_length=15, choices=Platform.choices, default=Platform.GENERAL,
        help_text='Which platform this creative is being made for - independent of creative_type '
                  '(a Festival Creative can be for Instagram, Facebook, or LinkedIn).',
    )
    prompt_brief = models.TextField(blank=True, help_text='Visual brief / instructions for this generation.')
    product_info = models.TextField(blank=True, help_text='Product information to ground the generation.')
    variation_count = models.PositiveSmallIntegerField(
        default=3, help_text='How many variations to generate (1-3) - lower it while testing to save AI credits.',
    )

    status = models.CharField(max_length=15, choices=Status.choices, default=Status.PENDING)
    error_message = models.TextField(blank=True)
    retry_count = models.PositiveIntegerField(default=0)
    celery_task_id = models.CharField(max_length=255, blank=True)

    model_used = models.CharField(max_length=100, blank=True)
    usage = models.JSONField(default=dict, blank=True, help_text='Provider usage metadata (e.g. image/token counts).')
    cost_usd = models.DecimalField(max_digits=10, decimal_places=4, null=True, blank=True)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='+',
    )

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.get_creative_type_display()} for {self.company.name} ({self.status})'

    def add_cost(self, amount: Decimal):
        self.cost_usd = (self.cost_usd or Decimal('0')) + amount


class GenerationVariation(TimeStampedModel):
    """One of up to 3 generated creative variations for a GenerationRequest (Epic 06: Variations)."""

    generation_request = models.ForeignKey(GenerationRequest, on_delete=models.CASCADE, related_name='variations')
    variation_number = models.PositiveSmallIntegerField()

    image = models.ImageField(upload_to=variation_image_upload_path)

    caption = models.TextField(blank=True)
    headline = models.CharField(max_length=255, blank=True)
    description = models.TextField(blank=True)
    cta = models.CharField(max_length=255, blank=True, verbose_name='CTA')
    hashtags = models.JSONField(default=list, blank=True)
    keywords = models.JSONField(default=list, blank=True)

    is_selected = models.BooleanField(default=False)

    class Meta:
        ordering = ['variation_number']
        unique_together = [['generation_request', 'variation_number']]

    def __str__(self):
        return f'Variation {self.variation_number} of request {self.generation_request_id}'
