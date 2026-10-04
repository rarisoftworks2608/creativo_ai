import datetime

from django.db.models import Sum
from django.utils import timezone
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema
from rest_framework import generics, status
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.activity_log.models import ActivityLog
from apps.activity_log.services import log_activity
from apps.companies.models import ClientProfile, Company
from common.mixins import CompanyScopedMixin
from common.permissions import IsAdmin

from .models import BillingRecord, Plan, Subscription
from .serializers import BillingRecordSerializer, PlanSerializer, SubscriptionSerializer
from .usage import calculate_storage, compute_usage, get_current_subscription


class PlanListCreateView(generics.ListCreateAPIView):
    """Admin: the plan catalogue (Epic 17: Plans)."""

    serializer_class = PlanSerializer
    permission_classes = [IsAdmin]
    pagination_class = None

    def get_queryset(self):
        queryset = Plan.objects.all()
        if self.request.query_params.get('active') in ('1', 'true'):
            queryset = queryset.filter(is_active=True)
        return queryset

    def perform_create(self, serializer):
        plan = serializer.save()
        log_activity(module=ActivityLog.Module.SUBSCRIPTION, action='Plan created', description=plan.name, request=self.request)


class PlanDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = PlanSerializer
    permission_classes = [IsAdmin]
    queryset = Plan.objects.all()

    def perform_update(self, serializer):
        plan = serializer.save()
        log_activity(module=ActivityLog.Module.SUBSCRIPTION, action='Plan updated', description=plan.name, request=self.request)

    def destroy(self, request, *args, **kwargs):
        plan = self.get_object()
        if plan.subscriptions.exists():
            plan.is_active = False
            plan.save(update_fields=['is_active', 'updated_at'])
            return Response(
                {'detail': 'This plan has subscriptions, so it was deactivated instead of deleted.',
                 'plan': PlanSerializer(plan).data},
            )
        plan.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class SubscriptionListCreateView(generics.ListCreateAPIView):
    """Admin: every company's subscriptions (Epic 17: Create subscription / Assign plan)."""

    serializer_class = SubscriptionSerializer
    permission_classes = [IsAdmin]

    def get_queryset(self):
        queryset = Subscription.objects.select_related('company', 'plan')
        params = self.request.query_params
        if params.get('status'):
            queryset = queryset.filter(status__in=params['status'].split(','))
        if params.get('company'):
            queryset = queryset.filter(company_id=params['company'])
        if params.get('plan'):
            queryset = queryset.filter(plan_id=params['plan'])
        if params.get('expiring_within'):
            try:
                days = int(params['expiring_within'])
                today = timezone.localdate()
                queryset = queryset.filter(
                    status__in=Subscription.CURRENT_STATUSES, end_date__gte=today,
                    end_date__lte=today + datetime.timedelta(days=days),
                )
            except ValueError:
                pass
        if params.get('search'):
            queryset = queryset.filter(company__name__icontains=params['search'])
        return queryset

    def perform_create(self, serializer):
        company = serializer.validated_data['company']
        new_status = serializer.validated_data.get('status', Subscription.Status.ACTIVE)
        # A company has one current subscription - assigning a new current one closes the old.
        if new_status in Subscription.CURRENT_STATUSES:
            Subscription.objects.filter(company=company, status__in=Subscription.CURRENT_STATUSES).update(
                status=Subscription.Status.CANCELLED, updated_at=timezone.now(),
            )
        subscription = serializer.save(created_by=self.request.user)
        log_activity(
            module=ActivityLog.Module.SUBSCRIPTION, action='Subscription created',
            description=f'{company.name} → {subscription.plan.name} ({subscription.start_date} – {subscription.end_date or "open"})',
            company=company, request=self.request,
        )


class SubscriptionDetailView(generics.RetrieveUpdateAPIView):
    serializer_class = SubscriptionSerializer
    permission_classes = [IsAdmin]
    queryset = Subscription.objects.select_related('company', 'plan')

    def perform_update(self, serializer):
        before = SubscriptionSerializer(serializer.instance).data
        subscription = serializer.save()
        changed = {k: [before.get(k), v] for k, v in SubscriptionSerializer(subscription).data.items()
                   if k in ('status', 'plan', 'start_date', 'end_date', 'renewal_date') and before.get(k) != v}
        log_activity(
            module=ActivityLog.Module.SUBSCRIPTION, action='Subscription updated',
            description=f'{subscription.company.name} — {subscription.plan.name}',
            old_value={k: v[0] for k, v in changed.items()} or None,
            new_value={k: v[1] for k, v in changed.items()} or None,
            company=subscription.company, request=self.request,
        )


class UsageOverviewView(APIView):
    """Admin: every active company's plan + usage in one table (Epic 17: Usage monitoring)."""

    permission_classes = [IsAdmin]

    @extend_schema(responses=OpenApiTypes.OBJECT)
    def get(self, request):
        rows = []
        for company in Company.objects.filter(status=Company.Status.ACTIVE).order_by('name'):
            subscription = get_current_subscription(company)
            usage = compute_usage(company)
            rows.append({
                'company_id': company.id,
                'company_name': company.name,
                'subscription': SubscriptionSerializer(subscription).data if subscription else None,
                'usage': usage,
            })
        today = timezone.localdate()
        current = Subscription.objects.filter(status__in=Subscription.CURRENT_STATUSES)
        return Response({
            'results': rows,
            'summary': {
                'active': current.filter(status=Subscription.Status.ACTIVE).count(),
                'trial': current.filter(status=Subscription.Status.TRIAL).count(),
                'past_due': current.filter(status=Subscription.Status.PAST_DUE).count(),
                'expiring_30_days': current.filter(end_date__gte=today, end_date__lte=today + datetime.timedelta(days=30)).count(),
                'without_subscription': sum(1 for row in rows if row['subscription'] is None),
                'outstanding_amount': BillingRecord.objects.filter(
                    payment_status__in=[BillingRecord.PaymentStatus.PENDING, BillingRecord.PaymentStatus.OVERDUE,
                                        BillingRecord.PaymentStatus.PARTIALLY_PAID],
                ).aggregate(total=Sum('total_amount'), paid=Sum('amount_paid')),
            },
        })


class CompanySubscriptionView(CompanyScopedMixin, APIView):
    """A company's current subscription + usage (admin, or the client with the
    Subscription page). Admins also get the full history."""

    permission_classes = [IsAuthenticated]
    required_page = ClientProfile.Page.SUBSCRIPTION

    @extend_schema(responses=OpenApiTypes.OBJECT)
    def get(self, request, company_id):
        company = self.get_company()
        subscription = get_current_subscription(company)
        data = {
            'company_id': company.id,
            'company_name': company.name,
            'subscription': SubscriptionSerializer(subscription).data if subscription else None,
            'plan': PlanSerializer(subscription.plan).data if subscription else None,
            'usage': compute_usage(company),
        }
        if request.user.is_admin:
            data['history'] = SubscriptionSerializer(company.subscriptions.select_related('plan'), many=True).data
        return Response(data)


class CompanyStorageRecalculateView(CompanyScopedMixin, APIView):
    permission_classes = [IsAdmin]

    @extend_schema(responses=OpenApiTypes.OBJECT, request=OpenApiTypes.OBJECT)
    def post(self, request, company_id):
        company = self.get_company()
        snapshot = calculate_storage(company)
        return Response({'storage_bytes': snapshot.storage_bytes, 'file_count': snapshot.file_count,
                         'breakdown': snapshot.breakdown, 'usage': compute_usage(company, use_cache=False)})


class BillingRecordListCreateView(CompanyScopedMixin, generics.ListCreateAPIView):
    """Admin: a company's manual billing history (Epic 17: Manual Billing)."""

    serializer_class = BillingRecordSerializer
    permission_classes = [IsAdmin]
    parser_classes = [JSONParser, MultiPartParser, FormParser]

    def get_queryset(self):
        queryset = BillingRecord.objects.filter(company=self.get_company())
        if self.request.query_params.get('payment_status'):
            queryset = queryset.filter(payment_status=self.request.query_params['payment_status'])
        return queryset

    def get_serializer_context(self):
        return {**super().get_serializer_context(), 'company': self.get_company()}

    def perform_create(self, serializer):
        company = self.get_company()
        record = serializer.save(company=company, created_by=self.request.user)
        log_activity(
            module=ActivityLog.Module.SUBSCRIPTION, action='Billing record added',
            description=f'{record.invoice_number or "Invoice"} — {record.currency} {record.total_amount} ({record.get_payment_status_display()})',
            company=company, request=self.request,
        )


class BillingRecordDetailView(CompanyScopedMixin, generics.RetrieveUpdateDestroyAPIView):
    serializer_class = BillingRecordSerializer
    permission_classes = [IsAdmin]
    parser_classes = [JSONParser, MultiPartParser, FormParser]

    def get_queryset(self):
        return BillingRecord.objects.filter(company=self.get_company())

    def get_serializer_context(self):
        return {**super().get_serializer_context(), 'company': self.get_company()}

    def perform_update(self, serializer):
        record = serializer.save()
        log_activity(
            module=ActivityLog.Module.SUBSCRIPTION, action='Billing record updated',
            description=f'{record.invoice_number or "Invoice"} — {record.get_payment_status_display()}',
            company=record.company, request=self.request,
        )

    def perform_destroy(self, instance):
        log_activity(module=ActivityLog.Module.SUBSCRIPTION, action='Billing record deleted',
                     description=instance.invoice_number or f'Record #{instance.id}', company=instance.company,
                     request=self.request)
        instance.delete()
