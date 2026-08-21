from django.http import Http404
from django.utils import timezone
from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.companies.models import Company
from common.permissions import IsAdmin

from .models import VideoGenerationRequest
from .serializers import VideoGenerationRequestCreateSerializer, VideoGenerationRequestSerializer
from .tasks import generate_video


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
    """Resolves the company from the URL, 404ing if a client tries to reach a company that isn't theirs."""

    def get_company(self):
        company = generics.get_object_or_404(Company, pk=self.kwargs['company_id'])
        user = self.request.user
        if not user.is_admin:
            profile = getattr(user, 'client_profile', None)
            if not profile or profile.company_id != company.id:
                raise Http404
        return company


class VideoGenerationRequestListCreateView(CompanyScopedMixin, generics.ListCreateAPIView):
    """Admin: list a company's video generation requests, or start a new one (Epic 07)."""

    permission_classes = [IsAdmin]

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
        video_request = _enqueue(video_request)

        return Response(VideoGenerationRequestSerializer(video_request).data, status=status.HTTP_202_ACCEPTED)


class VideoGenerationRequestDetailView(CompanyScopedMixin, generics.RetrieveAPIView):
    """Admin: poll a single video generation request's status/results (Epic 07)."""

    serializer_class = VideoGenerationRequestSerializer
    permission_classes = [IsAdmin]

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
