import re

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema
from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.activity_log.models import ActivityLog
from apps.activity_log.services import log_activity
from apps.notifications.models import Notification
from apps.notifications.services import notify, notify_admins
from common.emails import send_client_welcome_email
from common.permissions import IsAdmin

from .models import ClientProfile, Company
from .serializers import (
    AddClientToCompanySerializer,
    ClientProfileSerializer,
    ClientProfileUpdateSerializer,
    CompanySerializer,
    CompanyWriteSerializer,
)


class CompanyListCreateView(generics.ListCreateAPIView):
    """Admin: list all companies (with search/status filters) or create a new one."""

    permission_classes = [IsAdmin]

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return CompanyWriteSerializer
        return CompanySerializer

    def get_queryset(self):
        queryset = Company.objects.all()

        status_param = self.request.query_params.get('status')
        if status_param:
            queryset = queryset.filter(status=status_param)

        industry = self.request.query_params.get('industry')
        if industry:
            queryset = queryset.filter(industry__iexact=industry)

        search = self.request.query_params.get('search')
        if search:
            queryset = queryset.filter(name__icontains=search)

        return queryset

    def perform_create(self, serializer):
        company = serializer.save()
        log_activity(
            module=ActivityLog.Module.COMPANY, action='Company created',
            description=company.name, company=company, request=self.request,
        )
        notify_admins(
            actor=self.request.user,
            notification_type=Notification.NotificationType.COMPANY_CREATED,
            title=f'"{company.name}" was added',
            message=f'New company created by {self.request.user.get_short_name()}.',
            url=f'/companies/{company.id}',
            company=company,
        )


class CompanyDetailView(generics.RetrieveUpdateAPIView):
    """Admin: view/edit any company. Client: view their own company only (read-only)."""

    permission_classes = [IsAuthenticated]

    def get_serializer_class(self):
        if self.request.method in ('PUT', 'PATCH'):
            return CompanyWriteSerializer
        return CompanySerializer

    def get_queryset(self):
        user = self.request.user
        if user.is_admin:
            return Company.objects.all()
        return Company.objects.filter(clients__user=user)

    def check_permissions(self, request):
        super().check_permissions(request)
        if request.method not in ('GET', 'HEAD', 'OPTIONS') and not request.user.is_admin:
            self.permission_denied(request, message='Only admins can edit a company.')

    def perform_update(self, serializer):
        company = serializer.save()
        log_activity(
            module=ActivityLog.Module.COMPANY, action='Company updated',
            description=company.name, company=company, request=self.request,
        )


class MyCompanyView(generics.RetrieveAPIView):
    """The authenticated client's own company (Epic 03: client's view of their company)."""

    serializer_class = CompanySerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        from rest_framework.exceptions import NotFound

        profile = getattr(self.request.user, 'client_profile', None)
        if profile is None:
            raise NotFound('No company is associated with this account.')
        if not self.request.user.is_admin and not profile.can_access(ClientProfile.Page.DASHBOARD):
            raise NotFound('No company is associated with this account.')
        self._client_profile = profile
        return profile.company

    def retrieve(self, request, *args, **kwargs):
        """Adds `page_permissions` alongside the company data - the client dashboard
        (Epic 01: Access Control) needs to know which of its own pages it can reach,
        to only ever link to pages it's actually been granted, matching what an
        admin configured on the Access Control page one-for-one.
        """
        response = super().retrieve(request, *args, **kwargs)
        response.data['page_permissions'] = list(self._client_profile.page_permissions or [])
        return response


class CompanyStatusView(APIView):
    """Admin: activate or deactivate a company."""

    permission_classes = [IsAdmin]
    serializer_class = CompanySerializer

    def post(self, request, pk, action):
        try:
            company = Company.objects.get(pk=pk)
        except Company.DoesNotExist:
            return Response({'detail': 'Company not found.'}, status=status.HTTP_404_NOT_FOUND)

        if action == 'activate':
            company.status = Company.Status.ACTIVE
        elif action == 'deactivate':
            company.status = Company.Status.INACTIVE
        else:
            return Response({'detail': 'Invalid action.'}, status=status.HTTP_400_BAD_REQUEST)

        company.save(update_fields=['status', 'updated_at'])
        log_activity(
            module=ActivityLog.Module.COMPANY, action=f'Company {action}d',
            description=company.name, company=company, request=request,
        )
        return Response(CompanySerializer(company).data)


class CompanyClientListCreateView(generics.ListCreateAPIView):
    """Admin: list a company's clients, or add one (new login or existing client user)."""

    permission_classes = [IsAdmin]

    def get_queryset(self):
        return ClientProfile.objects.filter(company_id=self.kwargs['company_id'])

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return AddClientToCompanySerializer
        return ClientProfileSerializer

    def get_company(self):
        return generics.get_object_or_404(Company, pk=self.kwargs['company_id'])

    def create(self, request, *args, **kwargs):
        company = self.get_company()
        serializer = self.get_serializer(data=request.data, context={'request': request, 'company': company})
        serializer.is_valid(raise_exception=True)
        profile = serializer.save()
        plain_password = serializer._plain_password  # noqa: SLF001 - only known right after creation
        if plain_password:
            send_client_welcome_email(profile.user, plain_password)

        log_activity(
            module=ActivityLog.Module.CLIENT, action='Client added',
            description=f'{profile.user.email} added to {company.name}',
            company=company, request=request,
        )

        notify_admins(
            actor=request.user,
            notification_type=Notification.NotificationType.CLIENT_ADDED,
            title=f'{profile.user.get_short_name()} added to "{company.name}"',
            message=f'New client contact added by {request.user.get_short_name()}.',
            url=f'/companies/{company.id}',
            company=company,
        )
        notify(
            profile.user,
            Notification.NotificationType.CLIENT_ADDED,
            title=f'You were added to "{company.name}"',
            message='You now have access to this company on the platform.',
            url=f'/companies/{company.id}',
            company=company,
        )

        return Response(
            {
                **ClientProfileSerializer(profile).data,
                'generated_password': serializer.data.get('generated_password'),
            },
            status=status.HTTP_201_CREATED,
        )


class CompanyClientDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Admin: view/update a client's role/page access at the company, or remove them from it."""

    serializer_class = ClientProfileSerializer
    permission_classes = [IsAdmin]

    def get_queryset(self):
        return ClientProfile.objects.filter(company_id=self.kwargs['company_id'])

    def get_serializer_class(self):
        if self.request.method in ('PUT', 'PATCH'):
            return ClientProfileUpdateSerializer
        return ClientProfileSerializer

    def update(self, request, *args, **kwargs):
        """Validates/saves via ClientProfileUpdateSerializer (writable fields only), but
        always responds with the full ClientProfileSerializer representation - the Access
        Control page merges this response straight into local state on every checkbox
        toggle, so a write-only serializer's response (missing id/user/company) would
        break the very next toggle on that row, the same bug fixed on UserDetailView.
        """
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        log_activity(
            module=ActivityLog.Module.CLIENT, action='Client access updated',
            description=instance.user.email, company=instance.company, request=request,
        )
        return Response(ClientProfileSerializer(instance).data)


IMAGE_EXTENSION_RE = re.compile(r'\.(png|jpe?g|gif|webp|svg)$', re.IGNORECASE)


class AdminDashboardStatsView(APIView):
    """Admin: aggregate stats for the admin dashboard landing page (Epic 14) - companies,
    clients, content, approvals, publishing, AI usage, subscriptions and engagement."""

    permission_classes = [IsAdmin]

    @extend_schema(responses=OpenApiTypes.OBJECT)
    def get(self, request):
        import datetime

        from django.db.models import Sum
        from django.utils import timezone

        from apps.analytics.models import PostMetrics
        from apps.content_calendar.models import ContentCalendarItem
        from apps.creative_generation.models import GenerationRequest
        from apps.publishing.models import PublishJob
        from apps.subscriptions.models import Subscription
        from apps.video_generation.models import VideoGenerationRequest

        creative_succeeded = GenerationRequest.objects.filter(status=GenerationRequest.Status.SUCCEEDED).count()
        video_succeeded = VideoGenerationRequest.objects.filter(status=VideoGenerationRequest.Status.SUCCEEDED).count()
        creative_failed = GenerationRequest.objects.filter(status=GenerationRequest.Status.FAILED).count()
        video_failed = VideoGenerationRequest.objects.filter(status=VideoGenerationRequest.Status.FAILED).count()
        creative_cost = GenerationRequest.objects.aggregate(total=Sum('cost_usd'))['total'] or 0
        video_cost = VideoGenerationRequest.objects.aggregate(total=Sum('cost_usd'))['total'] or 0

        today = timezone.localdate()
        month_start = today.replace(day=1)
        last_30 = timezone.now() - datetime.timedelta(days=30)
        current_subscriptions = Subscription.objects.filter(status__in=Subscription.CURRENT_STATUSES)
        engagement = PostMetrics.objects.filter(published_at__gte=last_30).aggregate(
            reach=Sum('reach'), engagements=Sum('engagements'),
        )
        reach, engagements = engagement['reach'] or 0, engagement['engagements'] or 0

        return Response({
            'total_companies': Company.objects.count(),
            'active_companies': Company.objects.filter(status=Company.Status.ACTIVE).count(),
            'active_clients': ClientProfile.objects.filter(user__is_active=True).count(),
            'content_generated': creative_succeeded + video_succeeded,
            'pending_approvals': ContentCalendarItem.objects.filter(
                status=ContentCalendarItem.Status.PENDING_APPROVAL,
            ).count(),
            'failed_generations': creative_failed + video_failed,
            'ai_usage': {
                'total_cost_usd': creative_cost + video_cost,
                'creative_count': creative_succeeded,
                'video_count': video_succeeded,
            },
            'publishing': {
                'published_total': PublishJob.objects.filter(status=PublishJob.Status.PUBLISHED).count(),
                'published_this_month': PublishJob.objects.filter(
                    status=PublishJob.Status.PUBLISHED, published_at__date__gte=month_start,
                ).count(),
                'scheduled': PublishJob.objects.filter(
                    status__in=[PublishJob.Status.SCHEDULED, PublishJob.Status.QUEUED],
                ).count(),
                'failed': PublishJob.objects.filter(status=PublishJob.Status.FAILED).count(),
                'ready_to_publish': ContentCalendarItem.objects.filter(status=ContentCalendarItem.Status.APPROVED)
                .exclude(publish_jobs__status__in=[*PublishJob.ACTIVE_STATUSES, PublishJob.Status.PUBLISHED])
                .distinct().count(),
            },
            'subscriptions': {
                'active': current_subscriptions.count(),
                'expiring_soon': current_subscriptions.filter(
                    end_date__gte=today, end_date__lte=today + datetime.timedelta(days=14),
                ).count(),
                'expired': Subscription.objects.filter(status=Subscription.Status.EXPIRED).count(),
                'companies_without_plan': Company.objects.filter(status=Company.Status.ACTIVE).exclude(
                    subscriptions__status__in=Subscription.CURRENT_STATUSES,
                ).count(),
            },
            'engagement_30d': {
                'reach': reach,
                'engagements': engagements,
                'engagement_rate': round(engagements / reach * 100, 2) if reach else 0,
            },
        })


class JobQueueView(APIView):
    """Admin: unified view across all companies' background jobs (Epic 23: Job Status /
    Scheduler monitoring) - creative + video generation, publishing, report generation
    and analytics sync, filterable by ?type=creative|video|publishing|report|analytics.
    """

    permission_classes = [IsAdmin]

    @extend_schema(responses=OpenApiTypes.OBJECT)
    def get(self, request):
        from apps.creative_generation.models import GenerationRequest
        from apps.video_generation.models import VideoGenerationRequest

        status_filter = request.query_params.get('status')
        type_filter = request.query_params.get('type')
        company_id = request.query_params.get('company')

        jobs = []

        if type_filter in (None, '', 'creative'):
            queryset = GenerationRequest.objects.select_related('company')
            if status_filter:
                queryset = queryset.filter(status=status_filter)
            if company_id:
                queryset = queryset.filter(company_id=company_id)
            for job in queryset:
                jobs.append({
                    'id': job.id, 'type': 'creative', 'type_display': 'Creative Generation',
                    'company_id': job.company_id, 'company_name': job.company.name,
                    'status': job.status, 'status_display': job.get_status_display(),
                    'error_message': job.error_message, 'retry_count': job.retry_count,
                    'created_at': job.created_at, 'updated_at': job.updated_at,
                })

        if type_filter in (None, '', 'video'):
            queryset = VideoGenerationRequest.objects.select_related('company')
            if status_filter:
                queryset = queryset.filter(status=status_filter)
            if company_id:
                queryset = queryset.filter(company_id=company_id)
            for job in queryset:
                jobs.append({
                    'id': job.id, 'type': 'video', 'type_display': 'Video Generation',
                    'company_id': job.company_id, 'company_name': job.company.name,
                    'status': job.status, 'status_display': job.get_status_display(),
                    'error_message': job.error_message, 'retry_count': job.retry_count,
                    'created_at': job.created_at, 'updated_at': job.updated_at,
                })

        jobs.extend(_other_jobs(type_filter, status_filter, company_id))
        jobs.sort(key=lambda j: j['created_at'], reverse=True)
        return Response({'count': len(jobs), 'results': jobs[:200]})


# Maps each new job type's own statuses onto the queue's pending/queued/processing/
# succeeded/failed vocabulary so the Jobs page can filter them uniformly.
PUBLISH_STATUS_MAP = {
    'scheduled': 'pending', 'queued': 'queued', 'processing': 'processing',
    'published': 'succeeded', 'failed': 'failed', 'cancelled': 'failed',
}
REPORT_STATUS_MAP = {'pending': 'queued', 'generating': 'processing', 'ready': 'succeeded', 'failed': 'failed'}
SYNC_STATUS_MAP = {'running': 'processing', 'succeeded': 'succeeded', 'partial': 'succeeded', 'failed': 'failed'}


def _other_jobs(type_filter, status_filter, company_id):
    """Publishing, report and analytics-sync jobs for the unified queue (Epic 23)."""
    from apps.analytics.models import AnalyticsSyncLog
    from apps.publishing.models import PublishJob
    from apps.reports.models import Report

    jobs = []
    if type_filter in (None, '', 'publishing'):
        queryset = PublishJob.objects.select_related('company', 'content_calendar_item')
        if company_id:
            queryset = queryset.filter(company_id=company_id)
        if status_filter:
            queryset = queryset.filter(status__in=[k for k, v in PUBLISH_STATUS_MAP.items() if v == status_filter])
        for job in queryset[:200]:
            jobs.append({
                'id': job.id, 'type': 'publishing', 'type_display': f'Publishing ({job.get_platform_display()})',
                'company_id': job.company_id, 'company_name': job.company.name,
                'status': PUBLISH_STATUS_MAP.get(job.status, job.status), 'status_display': job.get_status_display(),
                'error_message': job.last_error, 'retry_count': max(job.attempts - 1, 0),
                'created_at': job.created_at, 'updated_at': job.updated_at,
                'detail': job.content_calendar_item.topic if job.content_calendar_item else '',
                'scheduled_at': job.scheduled_at,
            })
    if type_filter in (None, '', 'report'):
        queryset = Report.objects.select_related('company')
        if company_id:
            queryset = queryset.filter(company_id=company_id)
        if status_filter:
            queryset = queryset.filter(status__in=[k for k, v in REPORT_STATUS_MAP.items() if v == status_filter])
        for report in queryset[:100]:
            jobs.append({
                'id': report.id, 'type': 'report', 'type_display': 'Report generation',
                'company_id': report.company_id, 'company_name': report.company.name if report.company else 'All companies',
                'status': REPORT_STATUS_MAP.get(report.status, report.status), 'status_display': report.get_status_display(),
                'error_message': report.error, 'retry_count': 0,
                'created_at': report.created_at, 'updated_at': report.updated_at, 'detail': report.title,
            })
    if type_filter in (None, '', 'analytics'):
        queryset = AnalyticsSyncLog.objects.select_related('company')
        if company_id:
            queryset = queryset.filter(company_id=company_id)
        if status_filter:
            queryset = queryset.filter(status__in=[k for k, v in SYNC_STATUS_MAP.items() if v == status_filter])
        for log in queryset[:100]:
            jobs.append({
                'id': log.id, 'type': 'analytics', 'type_display': 'Analytics sync',
                'company_id': log.company_id, 'company_name': log.company.name,
                'status': SYNC_STATUS_MAP.get(log.status, log.status), 'status_display': log.get_status_display(),
                'error_message': '; '.join(e.get('message', '') for e in (log.errors or [])[:3]), 'retry_count': 0,
                'created_at': log.started_at, 'updated_at': log.finished_at or log.started_at,
                'detail': f'{log.posts_synced} posts, {log.accounts_synced} accounts',
            })
    return jobs


class JobCancelView(APIView):
    """Admin: cancel a queued/pending job before it starts processing (Epic 23: Cancel).

    There's no separate "cancelled" status - a cancelled job is marked FAILED with
    a clear message, since every other part of the system (approval flow, retry)
    already knows how to handle FAILED and a new status would need to be taught
    to all of them for no real behavioral difference.
    """

    permission_classes = [IsAdmin]

    @extend_schema(responses=OpenApiTypes.OBJECT, request=OpenApiTypes.OBJECT)
    def post(self, request, job_type, job_id):
        from apps.creative_generation.models import GenerationRequest
        from apps.video_generation.models import VideoGenerationRequest
        from config.celery import app as celery_app

        if job_type == 'publishing':
            from apps.publishing.models import PublishJob

            job = generics.get_object_or_404(PublishJob, pk=job_id)
            if job.status not in (PublishJob.Status.SCHEDULED, PublishJob.Status.QUEUED):
                return Response({'detail': 'Only a scheduled or queued post can be cancelled.'}, status=status.HTTP_400_BAD_REQUEST)
            if job.celery_task_id and job.status == PublishJob.Status.QUEUED:
                celery_app.control.revoke(job.celery_task_id)
            job.status = PublishJob.Status.CANCELLED
            job.save(update_fields=['status', 'updated_at'])
            log_activity(module=ActivityLog.Module.PUBLISHING, action='Scheduled post cancelled',
                         description=f'Job #{job_id}', company=job.company, request=request)
            return Response({'detail': 'Job cancelled.'})

        model = {'creative': GenerationRequest, 'video': VideoGenerationRequest}.get(job_type)
        if model is None:
            return Response({'detail': 'Unknown job type.'}, status=status.HTTP_404_NOT_FOUND)

        job = generics.get_object_or_404(model, pk=job_id)
        if job.status not in (model.Status.PENDING, model.Status.QUEUED):
            return Response(
                {'detail': 'Only a pending or queued job can be cancelled.'}, status=status.HTTP_400_BAD_REQUEST,
            )

        if job.celery_task_id:
            celery_app.control.revoke(job.celery_task_id)

        job.status = model.Status.FAILED
        job.error_message = f'Cancelled by {request.user.get_short_name()}.'
        job.save(update_fields=['status', 'error_message', 'updated_at'])

        log_activity(
            module=ActivityLog.Module.CREATIVE if job_type == 'creative' else ActivityLog.Module.VIDEO,
            action='Generation cancelled', description=f'{job_type} job #{job_id}', company=job.company, request=request,
        )

        return Response({'detail': 'Job cancelled.'})


class MediaLibraryView(APIView):
    """Admin: a unified, read-mostly view across a company's media - brand assets,
    generated creative variations, and generated videos (Epic 08: Media Library).

    Only brand assets are renamable/deletable here (via the brand app's own
    endpoints, linked by `source_id`) - generated creatives/videos are browse/download
    only, since deleting one could corrupt approval history (an already-approved
    item's selected variation, a video a client has already reviewed, ...).
    """

    permission_classes = [IsAdmin]

    @extend_schema(responses=OpenApiTypes.OBJECT)
    def get(self, request, company_id):
        from apps.brand.models import BrandAsset
        from apps.creative_generation.models import GenerationVariation
        from apps.video_generation.models import VideoGenerationRequest

        company = generics.get_object_or_404(Company, pk=company_id)
        type_filter = request.query_params.get('type')
        search = request.query_params.get('search', '').strip()

        items = []

        assets = BrandAsset.objects.filter(company=company)
        if search:
            assets = assets.filter(name__icontains=search)
        for asset in assets:
            is_image = bool(asset.file) and bool(IMAGE_EXTENSION_RE.search(asset.file.name))
            url = request.build_absolute_uri(asset.file.url) if asset.file else ''
            items.append({
                'id': f'brand_asset-{asset.id}', 'source': 'brand_asset', 'source_id': asset.id,
                'type': 'image' if is_image else 'document', 'name': asset.name,
                'url': url, 'thumbnail_url': url if is_image else '',
                'category': asset.get_category_display(), 'created_at': asset.created_at,
                'renamable': True, 'deletable': True,
            })

        variations = GenerationVariation.objects.filter(
            generation_request__company=company,
        ).select_related('generation_request')
        if search:
            variations = variations.filter(caption__icontains=search)
        for variation in variations:
            if not variation.image:
                continue
            url = request.build_absolute_uri(variation.image.url)
            name = variation.headline or (variation.caption[:60] if variation.caption else f'Variation {variation.variation_number}')
            items.append({
                'id': f'creative_variation-{variation.id}', 'source': 'creative_variation', 'source_id': variation.id,
                'type': 'image', 'name': name, 'url': url, 'thumbnail_url': url,
                'category': variation.generation_request.get_creative_type_display(), 'created_at': variation.created_at,
                'renamable': False, 'deletable': False,
            })

        videos = VideoGenerationRequest.objects.filter(
            company=company, status=VideoGenerationRequest.Status.SUCCEEDED,
        )
        if search:
            videos = videos.filter(prompt_brief__icontains=search)
        for video in videos:
            if not video.video_file:
                continue
            items.append({
                'id': f'video-{video.id}', 'source': 'video', 'source_id': video.id,
                'type': 'video', 'name': video.prompt_brief.strip()[:60] or video.get_video_type_display(),
                'url': request.build_absolute_uri(video.video_file.url),
                'thumbnail_url': request.build_absolute_uri(video.thumbnail.url) if video.thumbnail else '',
                'category': video.get_video_type_display(), 'created_at': video.created_at,
                'renamable': False, 'deletable': False,
            })

        if type_filter:
            items = [item for item in items if item['type'] == type_filter]
        items.sort(key=lambda item: item['created_at'], reverse=True)

        return Response({'count': len(items), 'results': items})
