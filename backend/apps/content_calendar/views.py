import calendar
import datetime

from django.http import Http404, HttpResponse
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema
from rest_framework import generics, status
from rest_framework.pagination import PageNumberPagination
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.activity_log.models import ActivityLog
from apps.activity_log.services import log_activity
from apps.companies.models import ClientProfile, Company
from apps.notifications.models import Notification
from apps.notifications.services import notify_admins
from common.permissions import IsAdmin

from . import excel
from . import services as review_services
from .models import ContentCalendarItem, ContentReviewEvent
from .serializers import (
    ApprovalQueueItemSerializer,
    ContentCalendarItemSerializer,
    ContentReviewEventSerializer,
    ExcelUploadSerializer,
)


class CompanyScopedMixin:
    """Resolves the company from the URL, 404ing if a client tries to reach a company that
    isn't theirs, or (if `required_page` is set on the view) one they haven't been
    granted access to (Epic 01: Role & Access - Access Control page).
    """

    required_page = None

    def get_company(self):
        company = generics.get_object_or_404(Company, pk=self.kwargs['company_id'])
        user = self.request.user
        if not user.is_admin:
            profile = getattr(user, 'client_profile', None)
            if not profile or profile.company_id != company.id:
                raise Http404
            if self.required_page and not profile.can_access(self.required_page):
                raise Http404
        return company


def _serialize_row(entry):
    data = dict(entry['data'])
    if data.get('scheduled_date'):
        data['scheduled_date'] = data['scheduled_date'].isoformat()
    if data.get('scheduled_time'):
        data['scheduled_time'] = data['scheduled_time'].isoformat()
    result = {'row': entry['row'], 'data': data}
    if 'errors' in entry:
        result['errors'] = entry['errors']
    return result


class CalendarPagination(PageNumberPagination):
    """A month of content rarely exceeds this, so the calendar view gets it all in one page."""

    page_size = 200


class ContentCalendarItemListCreateView(CompanyScopedMixin, generics.ListCreateAPIView):
    """List a company's content calendar, or manually add an item (Epic 04: Calendar Management)."""

    serializer_class = ContentCalendarItemSerializer
    permission_classes = [IsAuthenticated]
    required_page = ClientProfile.Page.CALENDAR
    pagination_class = CalendarPagination

    def check_permissions(self, request):
        super().check_permissions(request)
        if request.method not in ('GET', 'HEAD', 'OPTIONS') and not (
            request.user.is_authenticated and request.user.is_admin
        ):
            self.permission_denied(request, message='Only admins can edit the content calendar.')

    def get_queryset(self):
        company = self.get_company()
        queryset = ContentCalendarItem.objects.filter(company=company).prefetch_related('publish_jobs')

        status_param = self.request.query_params.get('status')
        if status_param:
            queryset = queryset.filter(status=status_param)

        platform = self.request.query_params.get('platform')
        if platform:
            queryset = queryset.filter(platforms__contains=[platform])

        category = self.request.query_params.get('category')
        if category:
            queryset = queryset.filter(category=category)

        search = self.request.query_params.get('search')
        if search:
            queryset = queryset.filter(topic__icontains=search)

        month_param = self.request.query_params.get('month')
        if month_param:
            try:
                year, month = (int(part) for part in month_param.split('-', 1))
                _, last_day = calendar.monthrange(year, month)
                queryset = queryset.filter(
                    scheduled_date__gte=datetime.date(year, month, 1),
                    scheduled_date__lte=datetime.date(year, month, last_day),
                )
            except (ValueError, TypeError):
                pass

        return queryset

    def perform_create(self, serializer):
        company = self.get_company()
        item = serializer.save(
            company=company,
            created_by=self.request.user,
            source=ContentCalendarItem.Source.MANUAL,
        )
        log_activity(
            module=ActivityLog.Module.CALENDAR, action='Calendar item created',
            description=item.topic, company=company, request=self.request,
        )


class ContentCalendarItemDetailView(CompanyScopedMixin, generics.RetrieveUpdateDestroyAPIView):
    """View, edit, or delete a single calendar item."""

    serializer_class = ContentCalendarItemSerializer
    permission_classes = [IsAuthenticated]
    required_page = ClientProfile.Page.CALENDAR

    def check_permissions(self, request):
        super().check_permissions(request)
        if request.method not in ('GET', 'HEAD', 'OPTIONS') and not (
            request.user.is_authenticated and request.user.is_admin
        ):
            self.permission_denied(request, message='Only admins can edit the content calendar.')

    def get_queryset(self):
        return ContentCalendarItem.objects.filter(company=self.get_company())

    def perform_update(self, serializer):
        item = serializer.save()
        log_activity(
            module=ActivityLog.Module.CALENDAR, action='Calendar item updated',
            description=item.topic, company=item.company, request=self.request,
        )


class ContentCalendarDuplicateView(CompanyScopedMixin, APIView):
    """Admin: duplicate a single calendar item as a new draft (Epic 04: Duplicate calendar)."""

    permission_classes = [IsAdmin]
    serializer_class = ContentCalendarItemSerializer

    def post(self, request, company_id, pk):
        company = self.get_company()
        item = generics.get_object_or_404(ContentCalendarItem, pk=pk, company=company)
        item.pk = None
        item._state.adding = True
        item.status = ContentCalendarItem.Status.DRAFT
        item.source = ContentCalendarItem.Source.MANUAL
        item.created_by = request.user
        item.save()
        return Response(ContentCalendarItemSerializer(item, context={'request': request}).data, status=status.HTTP_201_CREATED)


def _trigger_regeneration(item):
    """Re-runs whichever generation pipeline (creative or video) produced this item's
    most recent content, with the client's rejection feedback appended to the brief.
    Only ever called once per item (Epic 09: One-time regeneration) - the caller checks
    regeneration_count before calling this.
    """
    from apps.content_calendar.tasks import _enqueue_creative, _enqueue_video
    from apps.creative_generation.models import GenerationRequest
    from apps.video_generation.models import VideoGenerationRequest

    feedback_note = f'Client feedback on the previous version: {item.client_feedback}'
    last_video = item.video_generation_requests.order_by('-created_at').first()
    last_creative = item.generation_requests.order_by('-created_at').first()

    if last_video is not None and (last_creative is None or last_video.created_at > last_creative.created_at):
        video_request = VideoGenerationRequest.objects.create(
            company=item.company, content_calendar_item=item, video_type=last_video.video_type,
            aspect_ratio=last_video.aspect_ratio, target_duration_seconds=last_video.target_duration_seconds,
            prompt_brief=f'{last_video.prompt_brief}\n\n{feedback_note}'.strip(),
            product_info=last_video.product_info,
        )
        _enqueue_video(video_request)
    elif last_creative is not None:
        generation_request = GenerationRequest.objects.create(
            company=item.company, content_calendar_item=item, creative_type=last_creative.creative_type,
            platform=last_creative.platform, variation_count=last_creative.variation_count,
            include_text_overlay=last_creative.include_text_overlay,
            prompt_brief=f'{last_creative.prompt_brief}\n\n{feedback_note}'.strip(),
            product_info=last_creative.product_info,
        )
        _enqueue_creative(generation_request)
    else:
        return

    item.regeneration_count += 1
    item.status = ContentCalendarItem.Status.GENERATING
    item.save(update_fields=['regeneration_count', 'status', 'updated_at'])
    review_services.record_review_event(
        item, ContentReviewEvent.Action.REGENERATION_REQUESTED, feedback=item.client_feedback,
        metadata={'kind': 'video' if last_video is not None and (
            last_creative is None or last_video.created_at > last_creative.created_at
        ) else 'creative'},
    )


class ContentCalendarGenerateNowView(CompanyScopedMixin, APIView):
    """Admin: start generation for a queued (Draft/Scheduled) calendar item right away,
    instead of waiting for the next auto_generate_due_content sweep (Epic 22).
    """

    permission_classes = [IsAdmin]
    serializer_class = ContentCalendarItemSerializer

    def post(self, request, company_id, pk):
        from .tasks import generate_now

        company = self.get_company()
        item = generics.get_object_or_404(ContentCalendarItem, pk=pk, company=company)
        if item.status not in (ContentCalendarItem.Status.DRAFT, ContentCalendarItem.Status.SCHEDULED):
            return Response(
                {'detail': 'Only draft or scheduled content can be generated.'}, status=status.HTTP_400_BAD_REQUEST,
            )

        from apps.platform_settings.services import check_daily_generation_limit
        from apps.subscriptions.enforcement import check_quota

        from .tasks import _is_video

        check_daily_generation_limit(company)
        check_quota(company, 'video' if _is_video(item.content_type) else 'creative')

        item = generate_now(item)
        log_activity(
            module=ActivityLog.Module.CALENDAR, action='Generation started (manual)',
            description=item.topic, company=company, request=request,
        )
        return Response(ContentCalendarItemSerializer(item, context={'request': request}).data)


class ContentCalendarApproveView(CompanyScopedMixin, APIView):
    """Client (or admin): approve a piece of content that's pending review (Epic 09: Approval)."""

    permission_classes = [IsAuthenticated]
    required_page = ClientProfile.Page.CALENDAR
    serializer_class = ContentCalendarItemSerializer

    def post(self, request, company_id, pk):
        company = self.get_company()
        item = generics.get_object_or_404(ContentCalendarItem, pk=pk, company=company)
        if item.status != ContentCalendarItem.Status.PENDING_APPROVAL:
            return Response({'detail': 'Only content pending approval can be approved.'}, status=status.HTTP_400_BAD_REQUEST)

        # Lock in which creative variation is being approved - it's the one that gets
        # published (Epic 06: Select preferred version). An explicit variation_id wins;
        # otherwise the client's earlier pick, otherwise variation 1.
        approved_variation = _resolve_approved_variation(item, request.data.get('variation_id'))
        if approved_variation is False:
            return Response({'detail': 'That variation does not belong to this content.'}, status=status.HTTP_400_BAD_REQUEST)

        item.status = ContentCalendarItem.Status.APPROVED
        item.save(update_fields=['status', 'updated_at'])

        note = (request.data.get('note') or '').strip()
        review_services.record_review_event(
            item, ContentReviewEvent.Action.APPROVED, actor=request.user, feedback=note,
            metadata={'variation_id': approved_variation.id if approved_variation else None},
        )

        log_activity(
            module=ActivityLog.Module.APPROVAL, action='Content approved',
            description=item.topic, company=company, request=request,
        )
        review_services._whatsapp(company, 'content_approved', {  # noqa: SLF001
            'topic': item.topic, 'approved_by': request.user.get_short_name(),
            'url': review_services.content_link(item),
        })

        # Epic 22 (Automation Engine - Publishing leg): approved content goes straight
        # into the publishing queue when Admin Settings > auto-schedule is on.
        from apps.publishing.services import auto_schedule_on_approval

        auto_schedule_on_approval(item, actor=request.user)

        notify_admins(
            actor=request.user,
            notification_type=Notification.NotificationType.CONTENT_APPROVED,
            title=f'"{item.topic}" was approved',
            message=f'Approved by {request.user.get_short_name()} for {company.name}.',
            url=f'/companies/{company.id}/calendar',
            company=company,
        )
        return Response(ContentCalendarItemSerializer(item, context={'request': request}).data)


class ContentCalendarRejectView(CompanyScopedMixin, APIView):
    """Client (or admin): reject pending content with required feedback, which triggers
    one automatic AI regeneration attempt (Epic 09: Rejection / Feedback / Regeneration).
    """

    permission_classes = [IsAuthenticated]
    required_page = ClientProfile.Page.CALENDAR
    serializer_class = ContentCalendarItemSerializer

    def post(self, request, company_id, pk):
        company = self.get_company()
        item = generics.get_object_or_404(ContentCalendarItem, pk=pk, company=company)
        if item.status != ContentCalendarItem.Status.PENDING_APPROVAL:
            return Response({'detail': 'Only content pending approval can be rejected.'}, status=status.HTTP_400_BAD_REQUEST)

        feedback = (request.data.get('feedback') or '').strip()
        if not feedback:
            return Response({'detail': 'Feedback is required to reject content.'}, status=status.HTTP_400_BAD_REQUEST)

        item.client_feedback = feedback
        item.status = ContentCalendarItem.Status.REJECTED
        item.save(update_fields=['client_feedback', 'status', 'updated_at'])

        review_services.record_review_event(
            item, ContentReviewEvent.Action.REJECTED, actor=request.user, feedback=feedback,
            metadata={'regeneration_available': item.regeneration_count < 1},
        )

        log_activity(
            module=ActivityLog.Module.APPROVAL, action='Content rejected',
            description=f'{item.topic} — {feedback}', company=company, request=request,
        )
        review_services._whatsapp(company, 'content_rejected', {  # noqa: SLF001
            'topic': item.topic, 'feedback': feedback[:500], 'url': review_services.content_link(item),
        })

        notify_admins(
            actor=request.user,
            notification_type=Notification.NotificationType.CONTENT_REJECTED,
            title=f'"{item.topic}" was rejected',
            message=feedback,
            url=f'/companies/{company.id}/calendar',
            company=company,
        )

        if item.regeneration_count < 1:
            _trigger_regeneration(item)

        return Response(ContentCalendarItemSerializer(item, context={'request': request}).data)


def _resolve_approved_variation(item, variation_id):
    """Returns the variation being approved (marking it selected), None when the item has
    no creative variations (e.g. a video), or False if `variation_id` isn't one of this
    item's variations."""
    from django.db import transaction

    from apps.creative_generation.models import GenerationVariation

    generation_request = item.generation_requests.order_by('-created_at').first()
    if generation_request is None:
        return None
    variations = generation_request.variations.all()
    if not variations.exists():
        return None

    if variation_id:
        try:
            chosen = variations.get(pk=int(variation_id))
        except (GenerationVariation.DoesNotExist, ValueError, TypeError):
            return False
    else:
        chosen = variations.filter(is_selected=True).first() or variations.order_by('variation_number').first()

    if not chosen.is_selected:
        with transaction.atomic():
            variations.exclude(pk=chosen.pk).update(is_selected=False)
            chosen.is_selected = True
            chosen.save(update_fields=['is_selected'])
    return chosen


class ContentCalendarHistoryView(CompanyScopedMixin, APIView):
    """Full review history of one calendar item (Epic 09: History) - every review event
    plus every generation attempt (original + regenerated) with its variations, so the
    previous version and the regenerated one can be compared side by side."""

    permission_classes = [IsAuthenticated]
    required_page = ClientProfile.Page.CALENDAR
    serializer_class = ContentReviewEventSerializer

    def get(self, request, company_id, pk):
        from apps.creative_generation.serializers import GenerationRequestSerializer
        from apps.video_generation.serializers import VideoGenerationRequestSerializer

        company = self.get_company()
        item = generics.get_object_or_404(ContentCalendarItem, pk=pk, company=company)
        events = item.review_events.select_related('actor')
        generations = [
            {'kind': 'creative', 'created_at': g.created_at, 'request': GenerationRequestSerializer(g, context={'request': request}).data}
            for g in item.generation_requests.prefetch_related('variations')
        ] + [
            {'kind': 'video', 'created_at': v.created_at, 'request': VideoGenerationRequestSerializer(v, context={'request': request}).data}
            for v in item.video_generation_requests.prefetch_related('scenes')
        ]
        generations.sort(key=lambda g: g['created_at'], reverse=True)

        publish_jobs = []
        if request.user.is_admin or _client_can(request.user, ClientProfile.Page.PUBLISHING):
            from apps.publishing.serializers import PublishJobSerializer

            publish_jobs = PublishJobSerializer(
                item.publish_jobs.select_related('social_account'), many=True, context={'request': request},
            ).data

        return Response({
            'item': ContentCalendarItemSerializer(item, context={'request': request}).data,
            'events': ContentReviewEventSerializer(events, many=True).data,
            'generations': generations,
            'publish_jobs': publish_jobs,
        })


def _client_can(user, page):
    profile = getattr(user, 'client_profile', None)
    return bool(profile and profile.can_access(page))


class ApprovalQueueView(generics.ListAPIView):
    """Admin: every company's content in the review pipeline in one queue (Epic 09:
    Approval monitoring) - filterable by status (default pending_approval), company and
    platform, oldest-waiting first so nothing sits forgotten."""

    serializer_class = ApprovalQueueItemSerializer
    permission_classes = [IsAdmin]

    def get_queryset(self):
        status_param = self.request.query_params.get('status') or ContentCalendarItem.Status.PENDING_APPROVAL
        queryset = ContentCalendarItem.objects.select_related('company').filter(status=status_param)
        company_id = self.request.query_params.get('company')
        if company_id:
            queryset = queryset.filter(company_id=company_id)
        platform = self.request.query_params.get('platform')
        if platform:
            queryset = queryset.filter(platforms__contains=[platform])
        search = self.request.query_params.get('search')
        if search:
            queryset = queryset.filter(topic__icontains=search)
        return queryset.order_by('updated_at')


class ApprovalStatsView(APIView):
    """Admin: counts per review status, plus how many have waited past the reminder window."""

    permission_classes = [IsAdmin]

    @extend_schema(responses=OpenApiTypes.OBJECT)
    def get(self, request):
        from datetime import timedelta

        from django.db.models import Count
        from django.utils import timezone

        from apps.platform_settings.models import PlatformSettings

        counts = dict(
            ContentCalendarItem.objects.values_list('status').annotate(total=Count('id')).values_list('status', 'total')
        )
        hours = PlatformSettings.load().approval_reminder_hours or 24
        overdue = ContentCalendarItem.objects.filter(
            status=ContentCalendarItem.Status.PENDING_APPROVAL,
            updated_at__lte=timezone.now() - timedelta(hours=hours),
        ).count()
        return Response({
            'pending_approval': counts.get(ContentCalendarItem.Status.PENDING_APPROVAL, 0),
            'approved': counts.get(ContentCalendarItem.Status.APPROVED, 0),
            'rejected': counts.get(ContentCalendarItem.Status.REJECTED, 0),
            'generating': counts.get(ContentCalendarItem.Status.GENERATING, 0),
            'published': counts.get(ContentCalendarItem.Status.PUBLISHED, 0),
            'failed': counts.get(ContentCalendarItem.Status.FAILED, 0),
            'overdue': overdue,
            'overdue_hours': hours,
        })


class ContentCalendarTemplateView(APIView):
    """Admin: download a blank Excel template for the content calendar (Epic 04: Excel template)."""

    permission_classes = [IsAdmin]

    @extend_schema(responses={200: OpenApiTypes.BINARY})
    def get(self, request, company_id):
        buffer = excel.build_template_workbook()
        response = HttpResponse(
            buffer.getvalue(),
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        )
        response['Content-Disposition'] = 'attachment; filename="content_calendar_template.xlsx"'
        return response


class ContentCalendarImportPreviewView(CompanyScopedMixin, APIView):
    """Admin: parse and validate an uploaded Excel file without saving anything (Epic 04: Import preview)."""

    permission_classes = [IsAdmin]
    parser_classes = [MultiPartParser, FormParser]
    serializer_class = ExcelUploadSerializer

    def post(self, request, company_id):
        self.get_company()
        upload = request.FILES.get('file')
        if not upload:
            return Response({'detail': 'file is required.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            valid_rows, invalid_rows = excel.parse_and_validate(upload)
        except excel.WorkbookParseError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response({
            'valid_count': len(valid_rows),
            'invalid_count': len(invalid_rows),
            'valid_rows': [_serialize_row(r) for r in valid_rows],
            'invalid_rows': [_serialize_row(r) for r in invalid_rows],
        })


class ContentCalendarImportCommitView(CompanyScopedMixin, APIView):
    """Admin: parse an uploaded Excel file and create calendar items for every valid row."""

    permission_classes = [IsAdmin]
    parser_classes = [MultiPartParser, FormParser]
    serializer_class = ExcelUploadSerializer

    def post(self, request, company_id):
        company = self.get_company()
        upload = request.FILES.get('file')
        if not upload:
            return Response({'detail': 'file is required.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            valid_rows, invalid_rows = excel.parse_and_validate(upload)
        except excel.WorkbookParseError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        created_items = [
            ContentCalendarItem.objects.create(
                company=company,
                created_by=request.user,
                source=ContentCalendarItem.Source.EXCEL_IMPORT,
                **entry['data'],
            )
            for entry in valid_rows
        ]

        return Response({
            'created_count': len(created_items),
            'invalid_count': len(invalid_rows),
            'invalid_rows': [_serialize_row(r) for r in invalid_rows],
        }, status=status.HTTP_201_CREATED)
