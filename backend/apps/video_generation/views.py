from django.http import Http404
from django.utils import timezone
from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.companies.models import ClientProfile, Company
from common.permissions import IsAdmin

from .models import VideoGenerationRequest
from .serializers import VideoGenerationRequestCreateSerializer, VideoGenerationRequestSerializer
from .tasks import generate_video

# Best-guess platform for an ad-hoc generation's auto-created calendar item
# (see _link_adhoc_calendar_item) - only used for the item's `platforms` list,
# it has no effect on what actually gets generated.
PLATFORM_BY_VIDEO_TYPE = {
    VideoGenerationRequest.VideoType.FACEBOOK_REEL: 'facebook',
    VideoGenerationRequest.VideoType.LINKEDIN_VIDEO: 'linkedin',
}


def _link_adhoc_calendar_item(video_request, user):
    """A video started without picking a content calendar item (the
    VideoGenerationPage "None (ad-hoc generation)" option) still needs a
    ContentCalendarItem behind it - that's the only thing the client's
    approval UI (Epic 09) and ContentCalendarApproveView/RejectView know how
    to review. Without this, an ad-hoc video would notify the client
    (notify_content_ready) but be otherwise invisible/unapprovable to them.
    """
    from apps.content_calendar.models import ContentCalendarItem

    platform = PLATFORM_BY_VIDEO_TYPE.get(video_request.video_type, 'instagram')
    topic = video_request.prompt_brief.strip()[:255] or video_request.get_video_type_display()

    calendar_item = ContentCalendarItem.objects.create(
        company=video_request.company,
        topic=topic,
        content_type=video_request.get_video_type_display(),
        platforms=[platform],
        scheduled_date=timezone.now().date(),
        source=ContentCalendarItem.Source.AD_HOC,
        created_by=user,
    )
    video_request.content_calendar_item = calendar_item
    video_request.save(update_fields=['content_calendar_item'])
    return video_request


def _enqueue(video_request):
    """Queues the render task and marks the request QUEUED - without clobbering a status
    the task may have already advanced past.

    See apps.creative_generation.views._enqueue for the full explanation: in
    eager/test mode `.delay()` can finish the whole task before this function's
    caller regains control, so the update below only applies while the row is
    still PENDING (i.e. the task genuinely hasn't started yet).
    """
    result = generate_video.delay(video_request.id)
    VideoGenerationRequest.objects.filter(pk=video_request.pk, status=VideoGenerationRequest.Status.PENDING).update(
        status=VideoGenerationRequest.Status.QUEUED, celery_task_id=result.id, updated_at=timezone.now(),
    )
    video_request.refresh_from_db()
    return video_request


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


class VideoGenerationRequestListCreateView(CompanyScopedMixin, generics.ListCreateAPIView):
    """List a company's video generation requests (admin or the owning client, read-only for
    the client), or start a new one (admin only) (Epic 07).
    """

    permission_classes = [IsAuthenticated]
    required_page = ClientProfile.Page.VIDEO_GENERATION

    def check_permissions(self, request):
        super().check_permissions(request)
        if request.method not in ('GET', 'HEAD', 'OPTIONS') and not (
            request.user.is_authenticated and request.user.is_admin
        ):
            self.permission_denied(request, message='Only admins can start a video generation request.')

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return VideoGenerationRequestCreateSerializer
        return VideoGenerationRequestSerializer

    def get_queryset(self):
        company = self.get_company()
        queryset = VideoGenerationRequest.objects.filter(company=company)

        status_param = self.request.query_params.get('status')
        if status_param:
            queryset = queryset.filter(status=status_param)

        video_type = self.request.query_params.get('video_type')
        if video_type:
            queryset = queryset.filter(video_type=video_type)

        content_calendar_item = self.request.query_params.get('content_calendar_item')
        if content_calendar_item:
            queryset = queryset.filter(content_calendar_item_id=content_calendar_item)

        return queryset

    def create(self, request, *args, **kwargs):
        company = self.get_company()
        serializer = self.get_serializer(data=request.data, context={'request': request, 'company': company})
        serializer.is_valid(raise_exception=True)
        video_request = serializer.save(company=company, created_by=request.user)
        if video_request.content_calendar_item_id is None:
            video_request = _link_adhoc_calendar_item(video_request, request.user)
        video_request = _enqueue(video_request)

        return Response(VideoGenerationRequestSerializer(video_request).data, status=status.HTTP_202_ACCEPTED)


class VideoGenerationRequestDetailView(CompanyScopedMixin, generics.RetrieveAPIView):
    """Poll a single video generation request's status/results - admin or the owning client (Epic 07)."""

    serializer_class = VideoGenerationRequestSerializer
    permission_classes = [IsAuthenticated]
    required_page = ClientProfile.Page.VIDEO_GENERATION

    def get_queryset(self):
        return VideoGenerationRequest.objects.filter(company=self.get_company())


class VideoGenerationRequestRetryView(CompanyScopedMixin, APIView):
    """Admin: retry a failed video generation request (Epic 07: Generation Management - Retry)."""

    permission_classes = [IsAdmin]
    serializer_class = VideoGenerationRequestSerializer

    def post(self, request, company_id, pk):
        company = self.get_company()
        video_request = generics.get_object_or_404(VideoGenerationRequest, pk=pk, company=company)

        if video_request.status != VideoGenerationRequest.Status.FAILED:
            return Response(
                {'detail': 'Only a failed video generation request can be retried.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        video_request.retry_count += 1
        video_request.error_message = ''
        video_request.status = VideoGenerationRequest.Status.PENDING
        video_request.save(update_fields=['retry_count', 'error_message', 'status', 'updated_at'])

        video_request = _enqueue(video_request)

        return Response(VideoGenerationRequestSerializer(video_request).data)
