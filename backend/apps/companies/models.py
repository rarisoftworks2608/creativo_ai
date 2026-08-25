from django.conf import settings
from django.db import models

from common.models import TimeStampedModel

# Business fields that must be filled in for a company's onboarding
# checklist to be considered complete (Epic 02: Onboarding).
ONBOARDING_REQUIRED_FIELDS = [
    'name', 'industry', 'description', 'contact_email', 'contact_phone',
    'address', 'target_market', 'target_audience', 'usp',
]


class Company(TimeStampedModel):
    """A tenant business account. Every company's data must stay isolated (Epic 25)."""

    class Status(models.TextChoices):
        ACTIVE = 'active', 'Active'
        INACTIVE = 'inactive', 'Inactive'

    # Core
    name = models.CharField(max_length=255)
    industry = models.CharField(max_length=150, blank=True)
    description = models.TextField(blank=True)
    website = models.URLField(blank=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.ACTIVE)

    # Contact & address
    contact_email = models.EmailField(blank=True)
    contact_phone = models.CharField(max_length=20, blank=True)
    address = models.TextField(blank=True)

    # Marketing profile
    target_market = models.TextField(blank=True)
    target_audience = models.TextField(blank=True)
    products = models.JSONField(default=list, blank=True, help_text='List of product names.')
    services = models.JSONField(default=list, blank=True, help_text='List of service names.')
    usp = models.TextField(blank=True, verbose_name='USP')
    competitors = models.JSONField(default=list, blank=True, help_text='List of competitor names.')

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='companies_created',
        help_text='Admin who created this company.',
    )

    class Meta:
        ordering = ['-created_at']
        verbose_name_plural = 'Companies'

    def __str__(self):
        return self.name

    @property
    def is_active(self):
        return self.status == self.Status.ACTIVE

    @property
    def onboarding(self):
        """Onboarding checklist: which required fields/steps are complete."""
        missing_fields = [
            field for field in ONBOARDING_REQUIRED_FIELDS
            if not getattr(self, field)
        ]
        has_client = self.clients.exists()
        if not has_client:
            missing_fields.append('client')

        total_steps = len(ONBOARDING_REQUIRED_FIELDS) + 1  # +1 for having a client
        completed_steps = total_steps - len(missing_fields)

        return {
            'is_complete': not missing_fields,
            'missing_fields': missing_fields,
            'completion_percentage': round((completed_steps / total_steps) * 100),
        }


def _all_pages():
    """Default page_permissions for a new (or pre-existing, via migration) client -
    everything granted, matching how access already worked before this field existed.
    An admin restricts it afterward via the Access Control page, rather than every new
    client starting locked out of pages that used to just work.
    """
    return list(ClientProfile.Page.values)


class ClientProfile(TimeStampedModel):
    """Links a Client login (apps.authentication.User) to the Company they belong to."""

    class Page(models.TextChoices):
        """Every client-facing page an admin can grant/revoke individually (Epic 01:
        Role & Access). Enforced server-side by each app's CompanyScopedMixin, not just
        hidden in the frontend nav - see `required_page` on the relevant views.
        """
        DASHBOARD = 'dashboard', 'Dashboard'
        BRAND = 'brand', 'Brand'
        AI_STRATEGY = 'ai_strategy', 'AI Strategy'
        CALENDAR = 'calendar', 'Content Calendar'
        CREATIVE_GENERATION = 'creative_generation', 'Creative Generation'
        VIDEO_GENERATION = 'video_generation', 'Video Generation'

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='client_profile',
    )
    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name='clients',
    )
    designation = models.CharField(max_length=150, blank=True, help_text="Client's job title at the company.")
    is_primary_contact = models.BooleanField(default=False)
    page_permissions = models.JSONField(
        default=_all_pages, blank=True,
        help_text='List of Page keys this client can access, e.g. ["dashboard", "brand"].',
    )

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.user.email} @ {self.company.name}'

    def can_access(self, page):
        return page in (self.page_permissions or [])
