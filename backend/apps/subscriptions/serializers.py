from django.utils.text import slugify
from rest_framework import serializers

from apps.social_accounts.models import SocialAccount

from .models import BillingRecord, Plan, Subscription


class PlanSerializer(serializers.ModelSerializer):
    billing_cycle_display = serializers.CharField(source='get_billing_cycle_display', read_only=True)
    active_subscriptions = serializers.SerializerMethodField()

    class Meta:
        model = Plan
        fields = [
            'id', 'name', 'slug', 'description', 'price', 'currency', 'billing_cycle', 'billing_cycle_display',
            'creative_limit', 'video_limit', 'publishing_limit', 'storage_limit_mb', 'social_account_limit',
            'allowed_platforms', 'features', 'is_active', 'sort_order', 'active_subscriptions',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'active_subscriptions']
        extra_kwargs = {'slug': {'required': False}}

    def get_active_subscriptions(self, obj) -> int:
        return obj.subscriptions.filter(status__in=Subscription.CURRENT_STATUSES).count()

    def validate_allowed_platforms(self, value):
        valid = {choice for choice, _ in SocialAccount.Platform.choices}
        if not isinstance(value, list) or any(v not in valid for v in value):
            raise serializers.ValidationError(f'Platforms must be a list drawn from: {", ".join(sorted(valid))}.')
        return value

    def validate_features(self, value):
        if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
            raise serializers.ValidationError('Features must be a list of strings.')
        return [v.strip() for v in value if v.strip()]

    def validate(self, attrs):
        if not attrs.get('slug') and attrs.get('name') and not getattr(self.instance, 'slug', None):
            base = slugify(attrs['name'])[:90] or 'plan'
            slug, n = base, 2
            while Plan.objects.filter(slug=slug).exists():
                slug, n = f'{base}-{n}', n + 1
            attrs['slug'] = slug
        return attrs


class SubscriptionSerializer(serializers.ModelSerializer):
    company_name = serializers.CharField(source='company.name', read_only=True)
    plan_name = serializers.CharField(source='plan.name', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    effective_limits = serializers.DictField(read_only=True)
    effective_price = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    currency = serializers.CharField(source='plan.currency', read_only=True)
    days_remaining = serializers.SerializerMethodField()

    class Meta:
        model = Subscription
        fields = [
            'id', 'company', 'company_name', 'plan', 'plan_name', 'status', 'status_display',
            'start_date', 'end_date', 'renewal_date', 'auto_renew', 'days_remaining',
            'price_override', 'creative_limit_override', 'video_limit_override', 'publishing_limit_override',
            'storage_limit_mb_override', 'social_account_limit_override',
            'effective_limits', 'effective_price', 'currency', 'notes', 'created_by', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_by', 'created_at', 'updated_at']

    def get_days_remaining(self, obj) -> int | None:
        from django.utils import timezone

        if not obj.end_date:
            return None
        return (obj.end_date - timezone.localdate()).days

    def validate(self, attrs):
        start = attrs.get('start_date', getattr(self.instance, 'start_date', None))
        end = attrs.get('end_date', getattr(self.instance, 'end_date', None))
        if start and end and end < start:
            raise serializers.ValidationError({'end_date': 'End date cannot be before the start date.'})
        plan = attrs.get('plan')
        if plan is not None and not plan.is_active and (self.instance is None or self.instance.plan_id != plan.id):
            raise serializers.ValidationError({'plan': 'This plan is inactive.'})
        return attrs


class BillingRecordSerializer(serializers.ModelSerializer):
    payment_status_display = serializers.CharField(source='get_payment_status_display', read_only=True)
    payment_method_display = serializers.CharField(source='get_payment_method_display', read_only=True)
    balance_due = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    company_name = serializers.CharField(source='company.name', read_only=True)

    class Meta:
        model = BillingRecord
        fields = [
            'id', 'company', 'company_name', 'subscription', 'invoice_number', 'invoice_date', 'due_date',
            'period_start', 'period_end', 'amount', 'tax_amount', 'total_amount', 'amount_paid', 'balance_due',
            'currency', 'payment_status', 'payment_status_display', 'payment_method', 'payment_method_display',
            'payment_reference', 'paid_on', 'invoice_file', 'notes', 'created_by', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'company', 'created_by', 'created_at', 'updated_at']
        extra_kwargs = {'total_amount': {'required': False}}

    def validate(self, attrs):
        subscription = attrs.get('subscription')
        company = self.context.get('company')
        if subscription is not None and company is not None and subscription.company_id != company.id:
            raise serializers.ValidationError({'subscription': 'This subscription belongs to another company.'})
        amount = attrs.get('amount', getattr(self.instance, 'amount', 0)) or 0
        tax = attrs.get('tax_amount', getattr(self.instance, 'tax_amount', 0)) or 0
        if 'amount' in attrs or 'tax_amount' in attrs or not attrs.get('total_amount'):
            attrs['total_amount'] = amount + tax
        return attrs
