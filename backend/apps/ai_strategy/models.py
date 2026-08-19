from django.conf import settings
from django.db import models

from apps.companies.models import Company
from common.models import TimeStampedModel


class BrandContext(TimeStampedModel):
    """AI's synthesized understanding of a company's brand (Epic 05: Brand Understanding).

    One holistic generation call analyzes the business, brand guidelines,
    products/services and audience, and produces a synthesized summary that
    downstream AI Planning / AI Strategy generations are grounded in - this
    is the "brand context" the rest of the epic depends on.
    """

    company = models.OneToOneField(Company, on_delete=models.CASCADE, related_name='brand_context')

    business_analysis = models.TextField(blank=True)
    brand_guidelines_analysis = models.TextField(blank=True)
    products_services_analysis = models.TextField(blank=True)
    audience_analysis = models.TextField(blank=True)
    summary = models.TextField(blank=True, help_text='Synthesized brand context used to ground later AI generations.')

    model_used = models.CharField(max_length=100, blank=True)
    generated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='+',
    )

    class Meta:
        verbose_name = 'Brand Context'
        verbose_name_plural = 'Brand Contexts'

    def __str__(self):
        return f'Brand context for {self.company.name}'


class StrategyOutput(TimeStampedModel):
    """A single AI Planning or AI Strategy generation result (Epic 05)."""

    class Kind(models.TextChoices):
        # AI Planning
        CONTENT_IDEAS = 'content_ideas', 'Content Ideas'
        TOPIC_SUGGESTIONS = 'topic_suggestions', 'Topic Suggestions'
        CONTENT_THEMES = 'content_themes', 'Content Themes'
        CAMPAIGN_SUGGESTIONS = 'campaign_suggestions', 'Campaign Suggestions'
        POSTING_SUGGESTIONS = 'posting_suggestions', 'Posting Suggestions'
        # AI Strategy
        CONTENT_STRATEGY = 'content_strategy', 'Content Strategy'
        PLATFORM_STRATEGY = 'platform_strategy', 'Platform Strategy'
        AUDIENCE_STRATEGY = 'audience_strategy', 'Audience Strategy'
        CAMPAIGN_STRATEGY = 'campaign_strategy', 'Campaign Strategy'

    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='strategy_outputs')
    kind = models.CharField(max_length=30, choices=Kind.choices)
    notes = models.TextField(blank=True, help_text='Optional extra guidance the admin supplied for this generation.')
    result = models.JSONField(default=dict, help_text='Structured output; shape depends on kind.')

    model_used = models.CharField(max_length=100, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='+',
    )

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.get_kind_display()} for {self.company.name} ({self.created_at:%Y-%m-%d})'
