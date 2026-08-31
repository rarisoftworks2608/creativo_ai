from django.db import transaction
from django.http import Http404
from django.utils import timezone
from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.companies.models import ClientProfile, Company
from common.permissions import IsAdmin

from .models import GenerationRequest, GenerationVariation
from .serializers import GenerationRequestCreateSerializer, GenerationRequestSerializer
from .tasks import generate_creative_variations

# Best-guess platform for an ad-hoc generation's auto-created calendar item
# (see _link_adhoc_calendar_item) - only used for the item's `platforms` list,
# it has no effect on which provider/prompt actually generates the creative.
PLATFORM_BY_CREATIVE_TYPE = {
    GenerationRequest.CreativeType.FACEBOOK_POST: 'facebook',
    GenerationRequest.CreativeType.LINKEDIN_POST: 'linkedin',
}


def _link_adhoc_calendar_item(generation_request, user):
    """A generation started without picking a content calendar item (the
    CreativeGenerationPage "None (ad-hoc generation)" option) still needs a
    ContentCalendarItem behind it - that's the only thing the client's
    approval UI (Epic 09) and ContentCalendarApproveView/RejectView know how
    to review. Without this, an ad-hoc generation would notify the client
    (notify_content_ready) but be otherwise invisible/unapprovable to them.
    """
    from apps.content_calendar.models import ContentCalendarItem

    platform = PLATFORM_BY_CREATIVE_TYPE.get(generation_request.creative_type, 'instagram')
    topic = generation_request.prompt_brief.strip()[:255] or generation_request.get_creative_type_display()

    calendar_item = ContentCalendarItem.objects.create(
        company=generation_request.company,
        topic=topic,
        content_type=generation_request.get_creative_type_display(),
        platforms=[platform],
        scheduled_date=timezone.now().date(),
        source=ContentCalendarItem.Source.AD_HOC,
        created_by=user,
    )
    generation_request.content_calendar_item = calendar_item
    generation_request.save(update_fields=['content_calendar_item'])
    return generation_request


def _enqueue(generation_request):
    """Queues the generation task and marks the request QUEUED - without clobbering a
    status the task may have already advanced past.

    In eager/test mode (and in principle under a fast enough real worker), `.delay()`
    can finish running the whole task - including saving its own final status - before
    this function's caller gets control back. Blindly overwriting `status` afterwards
    from the pre-delay in-memory object would stomp on that real result back to
    "queued" forever. The conditional `.filter(status=PENDING)` only applies here if
    the task genuinely hasn't started yet.
    """
    result = generate_creative_variations.delay(generation_request.id)
    GenerationRequest.objects.filter(pk=generation_request.pk, status=GenerationRequest.Status.PENDING).update(
        status=GenerationRequest.Status.QUEUED, celery_task_id=result.id, updated_at=timezone.now(),
    )
    generation_request.refresh_from_db()
    return generation_request


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


class GenerationRequestListCreateView(CompanyScopedMixin, generics.ListCreateAPIView):
    """List a company's creative generation requests (admin or the owning client, read-only
    for the client - Epic 06/09: client needs to see what's pending their approval), or
    start a new one (admin only).
    """

    permission_classes = [IsAuthenticated]
    required_page = ClientProfile.Page.CREATIVE_GENERATION

    def check_permissions(self, request):
        super().check_permissions(request)
        if request.method not in ('GET', 'HEAD', 'OPTIONS') and not (
            request.user.is_authenticated and request.user.is_admin
        ):
            self.permission_denied(request, message='Only admins can start a generation request.')

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return GenerationRequestCreateSerializer
        return GenerationRequestSerializer

    def get_queryset(self):
        company = self.get_company()
        queryset = GenerationRequest.objects.filter(company=company)

        status_param = self.request.query_params.get('status')
        if status_param:
            queryset = queryset.filter(status=status_param)

        creative_type = self.request.query_params.get('creative_type')
        if creative_type:
            queryset = queryset.filter(creative_type=creative_type)

        content_calendar_item = self.request.query_params.get('content_calendar_item')
        if content_calendar_item:
            queryset = queryset.filter(content_calendar_item_id=content_calendar_item)

        return queryset

    def create(self, request, *args, **kwargs):
        company = self.get_company()
        serializer = self.get_serializer(data=request.data, context={'request': request, 'company': company})
        serializer.is_valid(raise_exception=True)
        generation_request = serializer.save(company=company, created_by=request.user)
        if generation_request.content_calendar_item_id is None:
            generation_request = _link_adhoc_calendar_item(generation_request, request.user)
        generation_request = _enqueue(generation_request)

        return Response(GenerationRequestSerializer(generation_request).data, status=status.HTTP_202_ACCEPTED)


class GenerationRequestDetailView(CompanyScopedMixin, generics.RetrieveAPIView):
    """Poll a single generation request's status/results - admin or the owning client (Epic 06)."""

    serializer_class = GenerationRequestSerializer
    permission_classes = [IsAuthenticated]
    required_page = ClientProfile.Page.CREATIVE_GENERATION

    def get_queryset(self):
        return GenerationRequest.objects.filter(company=self.get_company())


class GenerationRequestRetryView(CompanyScopedMixin, APIView):
    """Admin: retry a failed generation request (Epic 06: Generation Management - Retry)."""

    permission_classes = [IsAdmin]
    serializer_class = GenerationRequestSerializer

    def post(self, request, company_id, pk):
        company = self.get_company()
        generation_request = generics.get_object_or_404(GenerationRequest, pk=pk, company=company)

        if generation_request.status != GenerationRequest.Status.FAILED:
            return Response(
                {'detail': 'Only a failed generation request can be retried.'}, status=status.HTTP_400_BAD_REQUEST,
            )

        generation_request.retry_count += 1
        generation_request.error_message = ''
        generation_request.status = GenerationRequest.Status.PENDING
        generation_request.save(update_fields=['retry_count', 'error_message', 'status', 'updated_at'])

        generation_request = _enqueue(generation_request)

        return Response(GenerationRequestSerializer(generation_request).data)


class VariationSelectView(CompanyScopedMixin, APIView):
    """Admin or client: mark one variation as the preferred version (Epic 06: Select
    preferred version; Epic 09: the client picks their favorite before approving).
    """

    permission_classes = [IsAuthenticated]
    required_page = ClientProfile.Page.CREATIVE_GENERATION
    serializer_class = GenerationRequestSerializer

    def post(self, request, company_id, pk, variation_id):
        company = self.get_company()
        generation_request = generics.get_object_or_404(GenerationRequest, pk=pk, company=company)
        variation = generics.get_object_or_404(GenerationVariation, pk=variation_id, generation_request=generation_request)

        with transaction.atomic():
            generation_request.variations.exclude(pk=variation.pk).update(is_selected=False)
            variation.is_selected = True
            variation.save(update_fields=['is_selected'])

        return Response(GenerationRequestSerializer(generation_request).data)
