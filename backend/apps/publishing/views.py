import calendar
import datetime

from django.db.models import Count, Q
from django.utils import timezone
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema
from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.activity_log.models import ActivityLog
from apps.activity_log.services import log_activity
from apps.companies.models import ClientProfile
from apps.content_calendar.models import ContentCalendarItem
from apps.creative_generation.serializers import GenerationRequestSerializer
from apps.social_accounts.models import SocialAccount
from apps.social_accounts.serializers import SocialAccountSerializer
from apps.video_generation.serializers import VideoGenerationRequestSerializer
from common.mixins import AdminWriteMixin, CompanyScopedMixin
from common.permissions import IsAdmin

from . import media as media_utils
from . import services
from .models import PublishJob
from .platforms import validate_job_for_platform
from .serializers import PublishJobCreateSerializer, PublishJobSerializer, PublishJobUpdateSerializer


def _filter_jobs(queryset, params):
    status_param = params.get('status')
    if status_param:
        queryset = queryset.filter(status__in=status_param.split(','))
    platform = params.get('platform')
    if platform:
        queryset = queryset.filter(platform=platform)
    item = params.get('item')
    if item:
        queryset = queryset.filter(content_calendar_item_id=item)
    month = params.get('month')
    if month:
        try:
            year, month_number = (int(part) for part in month.split('-', 1))
            start = datetime.date(year, month_number, 1)
            end = datetime.date(year, month_number, calendar.monthrange(year, month_number)[1])
            queryset = queryset.filter(scheduled_at__date__gte=start, scheduled_at__date__lte=end)
        except (TypeError, ValueError):
            pass
    if params.get('upcoming') in ('1', 'true'):
        queryset = queryset.filter(status__in=PublishJob.ACTIVE_STATUSES).order_by('scheduled_at')
    search = params.get('search')
    if search:
        queryset = queryset.filter(Q(content_calendar_item__topic__icontains=search) | Q(caption__icontains=search))
    return queryset


class PublishJobListCreateView(CompanyScopedMixin, AdminWriteMixin, generics.ListCreateAPIView):
    """A company's publishing queue + history (Epic 11: Publishing queue / History).
    Clients can view it (Publishing page permission); only admins schedule posts."""

    permission_classes = [IsAuthenticated]
    required_page = ClientProfile.Page.PUBLISHING
    admin_write_message = 'Only admins can schedule or publish content.'

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return PublishJobCreateSerializer
        return PublishJobSerializer

    def get_queryset(self):
        queryset = PublishJob.objects.filter(company=self.get_company()).select_related(
            'social_account', 'content_calendar_item', 'company',
        )
        return _filter_jobs(queryset, self.request.query_params)

    def create(self, request, *args, **kwargs):
        company = self.get_company()
        serializer = PublishJobCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        item = data['content_calendar_item']
        if item.company_id != company.id:
            return Response({'detail': 'This content does not belong to this company.'}, status=status.HTTP_400_BAD_REQUEST)
        accounts = list(SocialAccount.objects.filter(company=company, pk__in=data['social_account_ids']))
        if len(accounts) != len(set(data['social_account_ids'])):
            return Response({'detail': 'One or more selected accounts were not found.'}, status=status.HTTP_400_BAD_REQUEST)

        scheduled_at = data.get('scheduled_at')
        if scheduled_at and scheduled_at < timezone.now() - datetime.timedelta(minutes=1):
            return Response({'detail': 'The scheduled time is in the past.'}, status=status.HTTP_400_BAD_REQUEST)

        jobs = services.create_publish_jobs(
            item, accounts, scheduled_at=scheduled_at, actor=request.user,
            caption=data.get('caption') if data.get('caption') else None, post_type=data.get('post_type') or None,
        )
        # "Publish now" = scheduled for now; hand them to a worker immediately rather than
        # waiting up to a minute for the dispatcher.
        if not scheduled_at or scheduled_at <= timezone.now():
            from apps.platform_settings.models import PlatformSettings

            if PlatformSettings.load().publishing_enabled:
                jobs = [services.enqueue_job(job) for job in jobs]

        return Response(
            PublishJobSerializer(jobs, many=True, context={'request': request}).data, status=status.HTTP_201_CREATED,
        )


class PublishJobDetailView(CompanyScopedMixin, AdminWriteMixin, generics.RetrieveUpdateAPIView):
    """View a job, or (admin) reschedule / edit the caption of a job that hasn't gone out."""

    permission_classes = [IsAuthenticated]
    required_page = ClientProfile.Page.PUBLISHING

    def get_serializer_class(self):
        if self.request.method in ('PUT', 'PATCH'):
            return PublishJobUpdateSerializer
        return PublishJobSerializer

    def get_queryset(self):
        return PublishJob.objects.filter(company=self.get_company()).select_related('social_account', 'content_calendar_item')

    def update(self, request, *args, **kwargs):
        job = self.get_object()
        if job.status not in (PublishJob.Status.SCHEDULED, PublishJob.Status.FAILED, PublishJob.Status.CANCELLED):
            return Response({'detail': 'Only a scheduled, failed or cancelled post can be edited.'}, status=status.HTTP_400_BAD_REQUEST)
        serializer = PublishJobUpdateSerializer(job, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        scheduled_at = serializer.validated_data.get('scheduled_at')
        if scheduled_at and scheduled_at < timezone.now() - datetime.timedelta(minutes=1):
            return Response({'detail': 'The scheduled time is in the past.'}, status=status.HTTP_400_BAD_REQUEST)
        job = serializer.save()
        if scheduled_at and job.status in (PublishJob.Status.FAILED, PublishJob.Status.CANCELLED):
            job.status = PublishJob.Status.SCHEDULED
            job.attempts = 0
            job.save(update_fields=['status', 'attempts', 'updated_at'])
        log_activity(module=ActivityLog.Module.PUBLISHING, action='Scheduled post updated',
                     description=f'Job #{job.id} → {job.scheduled_at:%Y-%m-%d %H:%M}', company=job.company, request=request)
        return Response(PublishJobSerializer(job, context={'request': request}).data)


class PublishJobActionView(CompanyScopedMixin, APIView):
    """Admin: cancel / retry / publish-now a single job (Epic 11: Retry / Cancel / Publish now)."""

    permission_classes = [IsAdmin]
    action = None

    @extend_schema(responses=OpenApiTypes.OBJECT, request=OpenApiTypes.OBJECT)
    def post(self, request, company_id, pk):
        company = self.get_company()
        job = generics.get_object_or_404(PublishJob, pk=pk, company=company)

        if self.action == 'cancel':
            if job.status not in (PublishJob.Status.SCHEDULED, PublishJob.Status.QUEUED):
                return Response({'detail': 'Only a scheduled or queued post can be cancelled.'}, status=status.HTTP_400_BAD_REQUEST)
            if job.celery_task_id and job.status == PublishJob.Status.QUEUED:
                from config.celery import app as celery_app

                celery_app.control.revoke(job.celery_task_id)
            job.status = PublishJob.Status.CANCELLED
            job.save(update_fields=['status', 'updated_at'])
            log_activity(module=ActivityLog.Module.PUBLISHING, action='Scheduled post cancelled',
                         description=f'Job #{job.id}', company=company, request=request)
        elif self.action in ('retry', 'publish-now'):
            if job.status in (PublishJob.Status.PROCESSING, PublishJob.Status.PUBLISHED):
                return Response({'detail': 'This post is already being published or was published.'}, status=status.HTTP_400_BAD_REQUEST)
            if job.social_account is None or not job.social_account.is_usable:
                return Response({'detail': 'The social account is not connected - reconnect it first.'}, status=status.HTTP_400_BAD_REQUEST)
            job.attempts = 0
            job.scheduled_at = timezone.now()
            job.status = PublishJob.Status.SCHEDULED
            job.save(update_fields=['attempts', 'scheduled_at', 'status', 'updated_at'])
            job = services.enqueue_job(job)
            log_activity(module=ActivityLog.Module.PUBLISHING,
                         action='Publish retried' if self.action == 'retry' else 'Published now',
                         description=f'Job #{job.id}', company=company, request=request)
        else:
            return Response({'detail': 'Unknown action.'}, status=status.HTTP_404_NOT_FOUND)

        return Response(PublishJobSerializer(job, context={'request': request}).data)


class ReadyToPublishView(CompanyScopedMixin, APIView):
    """Admin: approved content that isn't scheduled anywhere yet - the publishing inbox."""

    permission_classes = [IsAdmin]

    @extend_schema(responses=OpenApiTypes.OBJECT)
    def get(self, request, company_id):
        company = self.get_company()
        items = ContentCalendarItem.objects.filter(
            company=company, status=ContentCalendarItem.Status.APPROVED,
        ).exclude(publish_jobs__status__in=[*PublishJob.ACTIVE_STATUSES, PublishJob.Status.PUBLISHED]).distinct()

        results = []
        for item in items.order_by('scheduled_date', 'scheduled_time'):
            creative = item.generation_requests.order_by('-created_at').first()
            video = item.video_generation_requests.order_by('-created_at').first()
            results.append({
                'id': item.id, 'topic': item.topic, 'content_type': item.content_type, 'platforms': item.platforms,
                'scheduled_date': item.scheduled_date, 'scheduled_time': item.scheduled_time,
                'suggested_publish_at': services.item_publish_datetime(item),
                'latest_generation_request': GenerationRequestSerializer(creative, context={'request': request}).data if creative else None,
                'latest_video_request': VideoGenerationRequestSerializer(video, context={'request': request}).data if video else None,
            })
        return Response({'count': len(results), 'results': results})


class PublishPreviewView(CompanyScopedMixin, APIView):
    """Admin: exactly what would be posted for an item, plus per-account pre-flight
    warnings, before scheduling it."""

    permission_classes = [IsAdmin]

    @extend_schema(responses=OpenApiTypes.OBJECT)
    def get(self, request, company_id, item_id):
        company = self.get_company()
        item = generics.get_object_or_404(ContentCalendarItem, pk=item_id, company=company)
        try:
            post_type, media, caption = media_utils.resolve_content(item)
        except media_utils.MediaUnavailable as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        accounts = SocialAccount.objects.filter(company=company).exclude(status=SocialAccount.Status.DISCONNECTED)
        return Response({
            'item_id': item.id,
            'topic': item.topic,
            'platforms': item.platforms,
            'post_type': post_type,
            'caption': caption,
            'media': media_utils.media_preview(media, request),
            'suggested_publish_at': services.item_publish_datetime(item),
            'timezone': str(services.platform_timezone()),
            'accounts': [
                {
                    **SocialAccountSerializer(account).data,
                    'suggested': account.platform in (item.platforms or []),
                    'warnings': validate_job_for_platform(account.platform, post_type, media),
                }
                for account in accounts
            ],
        })


class PublishingStatsView(CompanyScopedMixin, APIView):
    """Publishing statistics for a company (Epic 14: Publishing statistics)."""

    permission_classes = [IsAuthenticated]
    required_page = ClientProfile.Page.PUBLISHING

    @extend_schema(responses=OpenApiTypes.OBJECT)
    def get(self, request, company_id):
        company = self.get_company()
        jobs = PublishJob.objects.filter(company=company)
        counts = dict(jobs.values_list('status').annotate(total=Count('id')).values_list('status', 'total'))
        month_start = timezone.localdate().replace(day=1)
        next_job = jobs.filter(status=PublishJob.Status.SCHEDULED).order_by('scheduled_at').first()
        by_platform = dict(
            jobs.filter(status=PublishJob.Status.PUBLISHED).values_list('platform').annotate(total=Count('id'))
            .values_list('platform', 'total')
        )
        return Response({
            'scheduled': counts.get(PublishJob.Status.SCHEDULED, 0) + counts.get(PublishJob.Status.QUEUED, 0),
            'processing': counts.get(PublishJob.Status.PROCESSING, 0),
            'published': counts.get(PublishJob.Status.PUBLISHED, 0),
            'failed': counts.get(PublishJob.Status.FAILED, 0),
            'cancelled': counts.get(PublishJob.Status.CANCELLED, 0),
            'published_this_month': jobs.filter(status=PublishJob.Status.PUBLISHED, published_at__date__gte=month_start).count(),
            'published_by_platform': by_platform,
            'next_scheduled_at': next_job.scheduled_at if next_job else None,
            'ready_to_publish': ContentCalendarItem.objects.filter(company=company, status=ContentCalendarItem.Status.APPROVED)
            .exclude(publish_jobs__status__in=[*PublishJob.ACTIVE_STATUSES, PublishJob.Status.PUBLISHED]).distinct().count(),
        })


class GlobalPublishQueueView(generics.ListAPIView):
    """Admin: every company's publishing jobs in one list (Epic 11: Publishing monitoring)."""

    serializer_class = PublishJobSerializer
    permission_classes = [IsAdmin]

    def get_queryset(self):
        queryset = PublishJob.objects.select_related('social_account', 'content_calendar_item', 'company')
        company_id = self.request.query_params.get('company')
        if company_id:
            queryset = queryset.filter(company_id=company_id)
        return _filter_jobs(queryset, self.request.query_params)
