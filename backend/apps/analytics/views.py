import datetime

from django.utils import timezone
from django.utils.dateparse import parse_date
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema
from rest_framework import generics, serializers, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.activity_log.models import ActivityLog
from apps.activity_log.services import log_activity
from apps.companies.models import ClientProfile
from common.mixins import CompanyScopedMixin
from common.permissions import IsAdmin

from . import services
from .models import AnalyticsSyncLog, PostMetrics


def _date_param(request, key):
    value = request.query_params.get(key)
    return parse_date(value) if value else None


class AnalyticsSummaryView(CompanyScopedMixin, APIView):
    """Company performance dashboard data (Epic 15) - admin, or a client with the
    Analytics page. ?start=YYYY-MM-DD&end=YYYY-MM-DD&platform=instagram"""

    permission_classes = [IsAuthenticated]
    required_page = ClientProfile.Page.ANALYTICS

    @extend_schema(responses=OpenApiTypes.OBJECT)
    def get(self, request, company_id):
        company = self.get_company()
        data = services.summary(
            company, start=_date_param(request, 'start'), end=_date_param(request, 'end'),
            platform=request.query_params.get('platform') or None, request=request,
        )
        return Response(data)


class PostMetricsSerializer(serializers.ModelSerializer):
    topic = serializers.SerializerMethodField()
    url = serializers.CharField(source='publish_job.external_url', read_only=True)
    account_name = serializers.SerializerMethodField()

    class Meta:
        model = PostMetrics
        fields = [
            'id', 'publish_job', 'topic', 'platform', 'account_name', 'post_type', 'content_type', 'campaign',
            'published_at', 'url', 'reach', 'impressions', 'views', 'likes', 'comments', 'shares', 'saves',
            'clicks', 'engagements', 'engagement_rate', 'last_synced_at', 'sync_error',
        ]

    def get_topic(self, obj) -> str:
        item = obj.publish_job.content_calendar_item
        return item.topic if item else ''

    def get_account_name(self, obj) -> str:
        account = obj.publish_job.social_account
        return account.account_name if account else ''


ORDERING = {
    'engagements', '-engagements', 'reach', '-reach', 'published_at', '-published_at',
    'engagement_rate', '-engagement_rate',
}


class PostMetricsListView(CompanyScopedMixin, generics.ListAPIView):
    serializer_class = PostMetricsSerializer
    permission_classes = [IsAuthenticated]
    required_page = ClientProfile.Page.ANALYTICS

    def get_queryset(self):
        queryset = PostMetrics.objects.filter(company=self.get_company()).select_related(
            'publish_job__content_calendar_item', 'publish_job__social_account',
        )
        params = self.request.query_params
        if params.get('platform'):
            queryset = queryset.filter(platform=params['platform'])
        start, end = _date_param(self.request, 'start'), _date_param(self.request, 'end')
        if start:
            queryset = queryset.filter(published_at__date__gte=start)
        if end:
            queryset = queryset.filter(published_at__date__lte=end)
        ordering = params.get('ordering')
        return queryset.order_by(ordering if ordering in ORDERING else '-published_at')


class SyncLogSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = AnalyticsSyncLog
        fields = [
            'id', 'status', 'status_display', 'started_at', 'finished_at', 'posts_synced', 'posts_failed',
            'accounts_synced', 'errors', 'triggered_by',
        ]


class AnalyticsSyncView(CompanyScopedMixin, APIView):
    """Admin: fetch the latest metrics now (Epic 15: Fetch analytics / Retry)."""

    permission_classes = [IsAdmin]

    @extend_schema(responses=OpenApiTypes.OBJECT, request=OpenApiTypes.OBJECT)
    def post(self, request, company_id):
        from .tasks import sync_company_analytics

        company = self.get_company()
        running = company.analytics_sync_logs.filter(
            status=AnalyticsSyncLog.Status.RUNNING, started_at__gte=timezone.now() - datetime.timedelta(minutes=10),
        ).exists()
        if running:
            return Response({'detail': 'A sync is already running for this company.'}, status=status.HTTP_409_CONFLICT)
        sync_company_analytics.delay(company.id, request.user.id)
        log_activity(
            module=ActivityLog.Module.ANALYTICS, action='Analytics sync started',
            description=company.name, company=company, request=request,
        )
        return Response(
            {'detail': 'Analytics sync started - numbers refresh in a minute or two.'}, status=status.HTTP_202_ACCEPTED,
        )


class AnalyticsSyncLogListView(CompanyScopedMixin, generics.ListAPIView):
    serializer_class = SyncLogSerializer
    permission_classes = [IsAdmin]

    def get_queryset(self):
        return AnalyticsSyncLog.objects.filter(company=self.get_company())


class AnalyticsOverviewView(APIView):
    """Admin: platform-wide performance across companies."""

    permission_classes = [IsAdmin]

    @extend_schema(responses=OpenApiTypes.OBJECT)
    def get(self, request):
        try:
            days = max(1, min(int(request.query_params.get('days', 30)), 365))
        except ValueError:
            days = 30
        return Response(services.platform_overview(days))
