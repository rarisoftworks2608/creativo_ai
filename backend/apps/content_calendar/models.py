from django.conf import settings
from django.db import models

from apps.companies.models import Company
from common.models import TimeStampedModel


class ContentCalendarItem(TimeStampedModel):
    """A single planned piece of content on a company's content calendar (Epic 04).

    Category and Format are deliberately free text rather than a fixed enum:
    every client brings their own planning vocabulary (a real estate brand's
    "Leadership / Community / Gratitude & Service" weekly themes look nothing
    like a restaurant's "Promotional / Festival / Product" categories), so the
    suggestion list lives in the frontend, not as a DB constraint.
    """

    class Status(models.TextChoices):
        DRAFT = 'draft', 'Draft'
        SCHEDULED = 'scheduled', 'Scheduled'
        GENERATING = 'generating', 'Generating'
        GENERATED = 'generated', 'Generated'
        PENDING_APPROVAL = 'pending_approval', 'Pending Approval'
        APPROVED = 'approved', 'Approved'
        REJECTED = 'rejected', 'Rejected'
        PUBLISHED = 'published', 'Published'
        FAILED = 'failed', 'Failed'

    class Platform(models.TextChoices):
        INSTAGRAM = 'instagram', 'Instagram'
        FACEBOOK = 'facebook', 'Facebook'
        LINKEDIN = 'linkedin', 'LinkedIn'
        TWITTER = 'twitter', 'X (Twitter)'
        PINTEREST = 'pinterest', 'Pinterest'

    class Source(models.TextChoices):
        MANUAL = 'manual', 'Manual'
        EXCEL_IMPORT = 'excel_import', 'Excel Import'
        AD_HOC = 'ad_hoc', 'Ad Hoc Generation'

    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='content_calendar_items')

    topic = models.CharField(max_length=255, help_text='Topical / content idea, e.g. "National Doctor\'s Day".')
    category = models.CharField(max_length=100, blank=True, help_text='Coarse internal classification, optional.')
    weekly_theme = models.CharField(max_length=255, blank=True, help_text='e.g. "Leadership", "Community".')
    content_type = models.CharField(max_length=100, help_text='Format, e.g. "Static Post", "Reel", "Carousel".')
    platforms = models.JSONField(default=list, help_text='List of platform codes, e.g. ["instagram", "facebook"].')

    objective = models.CharField(max_length=255, blank=True)
    campaign = models.CharField(max_length=255, blank=True)

    scheduled_date = models.DateField()
    scheduled_time = models.TimeField(null=True, blank=True)

    caption_requirements = models.TextField(blank=True, help_text='Caption / content idea copy.')
    creative_requirements = models.TextField(blank=True, help_text='Visual brief.')
    cta = models.CharField(max_length=255, blank=True, verbose_name='CTA')
    hashtags = models.JSONField(default=list, blank=True)
    source_notes = models.CharField(max_length=500, blank=True, help_text='Reference / inspiration source, if any.')

    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    source = models.CharField(max_length=20, choices=Source.choices, default=Source.MANUAL)

    client_feedback = models.TextField(blank=True, help_text="Client's rejection feedback / change request.")
    regeneration_count = models.PositiveSmallIntegerField(
        default=0, help_text='How many times this item has been auto-regenerated after a rejection (max 1).',
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='content_calendar_items_created',
    )

    class Meta:
        ordering = ['scheduled_date', 'scheduled_time', '-created_at']

    def __str__(self):
        return f'{self.topic} ({self.company.name}, {self.scheduled_date})'
