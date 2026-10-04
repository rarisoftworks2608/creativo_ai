from decimal import Decimal

from django.conf import settings
from django.db import models

from apps.companies.models import Company
from common.models import TimeStampedModel


class Plan(TimeStampedModel):
    """A subscription plan an admin assigns manually (Epic 17: Plans). There is no
    online checkout - plans are a catalogue of limits + a reference price.

    Every limit is per monthly usage period; 0 means unlimited.
    """

    class BillingCycle(models.TextChoices):
        MONTHLY = 'monthly', 'Monthly'
        QUARTERLY = 'quarterly', 'Quarterly'
        HALF_YEARLY = 'half_yearly', 'Half-yearly'
        YEARLY = 'yearly', 'Yearly'
        CUSTOM = 'custom', 'Custom'

    name = models.CharField(max_length=100)
    slug = models.SlugField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    price = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0'))
    currency = models.CharField(max_length=3, default='INR')
    billing_cycle = models.CharField(max_length=15, choices=BillingCycle.choices, default=BillingCycle.MONTHLY)

    creative_limit = models.PositiveIntegerField(default=0, help_text='Creative generations per month. 0 = unlimited.')
    video_limit = models.PositiveIntegerField(default=0, help_text='Video generations per month. 0 = unlimited.')
    publishing_limit = models.PositiveIntegerField(default=0, help_text='Published posts per month. 0 = unlimited.')
    storage_limit_mb = models.PositiveIntegerField(default=0, help_text='Total media storage. 0 = unlimited.')
    social_account_limit = models.PositiveIntegerField(default=0, help_text='Connected social accounts. 0 = unlimited.')
    allowed_platforms = models.JSONField(
        default=list, blank=True, help_text='Platforms this plan may connect/publish to. Empty = all.',
    )
    features = models.JSONField(default=list, blank=True, help_text='Marketing feature bullets shown for the plan.')

    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['sort_order', 'price', 'name']

    def __str__(self):
        return self.name


class Subscription(TimeStampedModel):
    """A company's (manually managed) subscription to a plan (Epic 17: Subscription).

    Per-company `*_override` limits take precedence over the plan's - a negotiated deal
    doesn't need its own plan. Old subscriptions are kept as history.
    """

    class Status(models.TextChoices):
        TRIAL = 'trial', 'Trial'
        ACTIVE = 'active', 'Active'
        PAST_DUE = 'past_due', 'Payment overdue'
        SUSPENDED = 'suspended', 'Suspended'
        EXPIRED = 'expired', 'Expired'
        CANCELLED = 'cancelled', 'Cancelled'

    CURRENT_STATUSES = (Status.TRIAL, Status.ACTIVE, Status.PAST_DUE)

    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='subscriptions')
    plan = models.ForeignKey(Plan, on_delete=models.PROTECT, related_name='subscriptions')
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.ACTIVE)

    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True, help_text='Expiry date. Blank = open-ended.')
    renewal_date = models.DateField(null=True, blank=True)
    auto_renew = models.BooleanField(default=False, help_text='Reminder only - renewal is still recorded manually.')

    price_override = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    creative_limit_override = models.PositiveIntegerField(null=True, blank=True)
    video_limit_override = models.PositiveIntegerField(null=True, blank=True)
    publishing_limit_override = models.PositiveIntegerField(null=True, blank=True)
    storage_limit_mb_override = models.PositiveIntegerField(null=True, blank=True)
    social_account_limit_override = models.PositiveIntegerField(null=True, blank=True)

    notes = models.TextField(blank=True)
    last_reminder_sent_on = models.DateField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='+',
    )

    class Meta:
        ordering = ['-start_date', '-created_at']
        indexes = [models.Index(fields=['company', 'status'])]

    def __str__(self):
        return f'{self.company.name} - {self.plan.name} ({self.status})'

    def _limit(self, name):
        override = getattr(self, f'{name}_override')
        return override if override is not None else getattr(self.plan, name)

    @property
    def effective_limits(self):
        return {
            'creative': self._limit('creative_limit'),
            'video': self._limit('video_limit'),
            'publishing': self._limit('publishing_limit'),
            'storage_mb': self._limit('storage_limit_mb'),
            'social_accounts': self._limit('social_account_limit'),
        }

    @property
    def effective_price(self):
        return self.price_override if self.price_override is not None else self.plan.price


class BillingRecord(TimeStampedModel):
    """A manually recorded invoice/payment (Epic 17: Manual Billing)."""

    class PaymentStatus(models.TextChoices):
        PENDING = 'pending', 'Pending'
        PAID = 'paid', 'Paid'
        PARTIALLY_PAID = 'partially_paid', 'Partially paid'
        OVERDUE = 'overdue', 'Overdue'
        REFUNDED = 'refunded', 'Refunded'
        VOID = 'void', 'Void'

    class PaymentMethod(models.TextChoices):
        BANK_TRANSFER = 'bank_transfer', 'Bank transfer'
        UPI = 'upi', 'UPI'
        CASH = 'cash', 'Cash'
        CHEQUE = 'cheque', 'Cheque'
        CARD = 'card', 'Card'
        OTHER = 'other', 'Other'

    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='billing_records')
    subscription = models.ForeignKey(
        Subscription, null=True, blank=True, on_delete=models.SET_NULL, related_name='billing_records',
    )
    invoice_number = models.CharField(max_length=60, blank=True)
    invoice_date = models.DateField()
    due_date = models.DateField(null=True, blank=True)
    period_start = models.DateField(null=True, blank=True)
    period_end = models.DateField(null=True, blank=True)

    amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0'))
    tax_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0'))
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0'))
    amount_paid = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0'))
    currency = models.CharField(max_length=3, default='INR')

    payment_status = models.CharField(max_length=15, choices=PaymentStatus.choices, default=PaymentStatus.PENDING)
    payment_method = models.CharField(max_length=15, choices=PaymentMethod.choices, blank=True)
    payment_reference = models.CharField(max_length=120, blank=True, help_text='UTR / cheque no. / transaction ID.')
    paid_on = models.DateField(null=True, blank=True)
    invoice_file = models.FileField(upload_to='billing/%Y/%m/', null=True, blank=True)
    notes = models.TextField(blank=True)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='+',
    )

    class Meta:
        ordering = ['-invoice_date', '-created_at']

    def __str__(self):
        return f'{self.invoice_number or "Invoice"} - {self.company.name}'

    def save(self, *args, **kwargs):
        if not self.total_amount:
            self.total_amount = (self.amount or Decimal('0')) + (self.tax_amount or Decimal('0'))
        super().save(*args, **kwargs)

    @property
    def balance_due(self):
        return (self.total_amount or Decimal('0')) - (self.amount_paid or Decimal('0'))


class UsageSnapshot(models.Model):
    """Cached storage usage per company - walking every media file is too slow to do
    on each request, so it's recalculated daily (and on demand)."""

    company = models.OneToOneField(Company, on_delete=models.CASCADE, related_name='usage_snapshot')
    storage_bytes = models.PositiveBigIntegerField(default=0)
    file_count = models.PositiveIntegerField(default=0)
    breakdown = models.JSONField(default=dict, blank=True)
    calculated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'Usage for {self.company.name}'
