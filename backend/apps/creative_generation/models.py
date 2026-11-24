from decimal import Decimal

from django.conf import settings
from django.db import models

from apps.companies.models import Company
from apps.content_calendar.models import ContentCalendarItem
from common.models import TimeStampedModel


def variation_image_upload_path(instance, filename):
    request = instance.generation_request
    return f'creative_generation/{request.company_id}/{request.id}/{filename}'


def request_asset_upload_path(instance, filename):
    return f'creative_generation/{instance.company_id}/inputs/{filename}'


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
    include_text_overlay = models.BooleanField(
        default=False,
        help_text='Composite an AI-written headline banner and CTA button onto the image itself. Off by '
                  'default - a plain clean photo is usually the better result; the headline/caption/CTA '
                  'copy is still generated and stored either way, just not baked into the image pixels '
                  'unless this is explicitly turned on.',
    )

    # What makes each creative type its own system (creative_types.py): the type's own inputs, the design style
    # and the size. Empty for requests made before they existed - those keep their old behaviour.
    brief_fields = models.JSONField(
        default=dict, blank=True,
        help_text='Type-specific inputs, e.g. a testimonial quote, an announcement title, a festival, a story objective.',
    )
    design_style = models.CharField(max_length=20, blank=True, help_text='Design style key (creative_types.DESIGN_STYLES).')
    aspect_ratio = models.CharField(max_length=8, blank=True, help_text="'1:1', '4:5', '1.91:1' or '9:16'; blank = the type's default.")
    slide_count = models.PositiveSmallIntegerField(default=0, help_text='Carousel only: how many slides (3-10).')
    customer_photo = models.ImageField(
        upload_to=request_asset_upload_path, blank=True, null=True,
        help_text='Testimonial only: an optional photo of the client, supplied by the person - never generated.',
    )
    generation_context = models.JSONField(
        default=dict, blank=True,
        help_text="Shared art direction kept for re-rendering, e.g. a carousel's series look and typography seed.",
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
    """One of up to 3 generated creative variations for a GenerationRequest (Epic 06: Variations) - or, for a
    carousel, one slide of it (publishing already posts every variation of a carousel as its slides)."""

    class Status(models.TextChoices):
        READY = 'ready', 'Ready'
        PROCESSING = 'processing', 'Processing'
        FAILED = 'failed', 'Failed'

    generation_request = models.ForeignKey(GenerationRequest, on_delete=models.CASCADE, related_name='variations')
    variation_number = models.PositiveSmallIntegerField()

    image = models.ImageField(upload_to=variation_image_upload_path)

    caption = models.TextField(blank=True)
    eyebrow = models.CharField(
        max_length=60, blank=True,
        help_text='Small kicker/label shown above the headline in the composited layout, e.g. "THE" or a category label.',
    )
    headline = models.CharField(max_length=255, blank=True)
    description = models.TextField(blank=True)
    cta = models.CharField(max_length=255, blank=True, verbose_name='CTA')
    hashtags = models.JSONField(default=list, blank=True)
    keywords = models.JSONField(default=list, blank=True)

    is_selected = models.BooleanField(default=False)

    slide_role = models.CharField(max_length=20, blank=True, help_text="Carousel only: 'cover', 'content' or 'cta'.")
    visual_scene = models.TextField(blank=True, help_text='The picture description this image was drawn from.')
    background = models.ImageField(
        upload_to=variation_image_upload_path, blank=True, null=True,
        help_text='The AI picture before text and logo were composited - kept so edited copy re-renders for free.',
    )
    render_params = models.JSONField(default=dict, blank=True, help_text='Layout inputs used to composite this image.')
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.READY)
    error_message = models.TextField(blank=True)

    class Meta:
        ordering = ['variation_number']
        unique_together = [['generation_request', 'variation_number']]

    def __str__(self):
        return f'Variation {self.variation_number} of request {self.generation_request_id}'
