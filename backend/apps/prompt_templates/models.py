from django.db import models

from common.models import TimeStampedModel


class PromptTemplate(TimeStampedModel):
    """Admin-editable extra guidance injected into AI prompts (Epic 21).

    Each row is one *version* of a template - versions sharing the same `slug`
    form that template's history. Only one version per slug should be active at
    a time (enforced in services.py, not here, so the intent stays explicit at
    the call site rather than hidden in a model save()).

    `platform`/`creative_type` are free-text, matching whatever
    GenerationRequest.Platform/CreativeType values are in use, rather than a
    hard FK - this module intentionally doesn't depend on creative_generation,
    only the other way around (see services.get_active_guidance, called from
    creative_generation/tasks.py).
    """

    class Category(models.TextChoices):
        IMAGE = 'image', 'Image Prompt'
        CAPTION = 'caption', 'Caption Prompt'
        VIDEO = 'video', 'Video Prompt'
        HASHTAG = 'hashtag', 'Hashtag Prompt'
        CAMPAIGN = 'campaign', 'Campaign Prompt'

    slug = models.SlugField(max_length=80, help_text='Groups versions of the same template together.')
    category = models.CharField(max_length=20, choices=Category.choices)
    platform = models.CharField(
        max_length=20, blank=True,
        help_text='Optional: instagram / facebook / linkedin / general. Blank = applies to every platform.',
    )
    creative_type = models.CharField(
        max_length=40, blank=True,
        help_text='Optional: e.g. festival_creative, product_creative. Blank = applies to every creative type.',
    )
    name = models.CharField(max_length=150)
    body = models.TextField(help_text='Extra guidance appended into the AI prompt for matching generations.')
    version = models.PositiveIntegerField(default=1)
    is_active = models.BooleanField(default=False)
    created_by = models.ForeignKey(
        'authentication.User', null=True, blank=True, on_delete=models.SET_NULL, related_name='+',
    )

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['slug', '-version']),
            models.Index(fields=['category', 'is_active']),
        ]

    def __str__(self):
        return f'{self.name} v{self.version}'
