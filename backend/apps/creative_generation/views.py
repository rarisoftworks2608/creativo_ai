import io
import zipfile

from django.db import transaction
from django.http import Http404, HttpResponse
from django.utils import timezone
from django.utils.text import slugify
from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.activity_log.models import ActivityLog
from apps.activity_log.services import log_activity
from apps.companies.models import ClientProfile, Company
from common.permissions import IsAdmin
from common.queueing import enqueue_or_undo, queue_failure_response

from .creative_types import festival_name, options_payload
from .models import GenerationRequest, GenerationVariation
from .serializers import GenerationRequestCreateSerializer, GenerationRequestSerializer, VariationEditSerializer
from .tasks import BrandKit, generate_creative_variations, regenerate_variation, render_variation


def _topic_for(generation_request):
    """A short title for the calendar entry behind an ad-hoc creative: the person's own topic, title, greeting or
    quote first, then the brief, then the creative type."""
    fields = generation_request.brief_fields or {}
    for value in (
        fields.get('topic'), fields.get('title'), fields.get('headline'),
        f'{festival_name(fields)} greeting' if fields.get('festival') else '',
        f'Testimonial: {fields["quote"]}' if fields.get('quote') else '',
        generation_request.prompt_brief.strip(),
    ):
        if value and str(value).strip():
            return str(value).strip()[:255]
    return generation_request.get_creative_type_display()

def _link_adhoc_calendar_item(generation_request, user):
    """A generation started without picking a content calendar item (the
    CreativeGenerationPage "None (ad-hoc generation)" option) still needs a
    ContentCalendarItem behind it - that's the only thing the client's
    approval UI (Epic 09) and ContentCalendarApproveView/RejectView know how
    to review. Without this, an ad-hoc generation would notify the client
    (notify_content_ready) but be otherwise invisible/unapprovable to them.
    """
    from apps.content_calendar.models import ContentCalendarItem

    # The calendar item's own `platforms` list is separate from the generation's
    # `platform` field, but for an auto-created item they should agree - "general"
    # (multi-platform) maps to Instagram as the calendar's default.
    platform = (
        generation_request.platform
        if generation_request.platform != GenerationRequest.Platform.GENERAL
        else ContentCalendarItem.Platform.INSTAGRAM
    )
    topic = _topic_for(generation_request)

    calendar_item = ContentCalendarItem.objects.create(
        company=generation_request.company,
        topic=topic,
        content_type=generation_request.get_creative_type_display(),
        platforms=[platform],
        scheduled_date=timezone.localdate(),
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
        from apps.platform_settings.services import check_daily_generation_limit
        from apps.subscriptions.enforcement import check_quota

        company = self.get_company()
        check_daily_generation_limit(company)
        check_quota(company, 'creative')
        serializer = self.get_serializer(data=request.data, context={'request': request, 'company': company})
        serializer.is_valid(raise_exception=True)
        generation_request = serializer.save(company=company, created_by=request.user)
        created_item_id = None
        if generation_request.content_calendar_item_id is None:
            generation_request = _link_adhoc_calendar_item(generation_request, request.user)
            created_item_id = generation_request.content_calendar_item_id
        generation_request, failure = enqueue_or_undo(
            _enqueue, generation_request, created_calendar_item_id=created_item_id,
        )
        if failure is not None:
            return failure

        log_activity(
            module=ActivityLog.Module.CREATIVE, action='Creative generation started',
            description=generation_request.get_creative_type_display(), company=company, request=request,
        )

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

        try:
            generation_request = _enqueue(generation_request)
        except Exception:  # noqa: BLE001 - broker unreachable: leave it failed so Retry stays available
            generation_request.status = GenerationRequest.Status.FAILED
            generation_request.error_message = 'Could not be queued - the background worker was unreachable.'
            generation_request.save(update_fields=['status', 'error_message', 'updated_at'])
            return queue_failure_response()

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

        if generation_request.content_calendar_item_id:
            from apps.content_calendar.models import ContentReviewEvent
            from apps.content_calendar.services import record_review_event

            record_review_event(
                generation_request.content_calendar_item, ContentReviewEvent.Action.VARIATION_SELECTED,
                actor=request.user, metadata={'variation_id': variation.id, 'variation_number': variation.variation_number},
            )

        return Response(GenerationRequestSerializer(generation_request).data)


class CreativeOptionsView(CompanyScopedMixin, APIView):
    """The options the creative form offers for each type (sizes, design styles, story objectives, announcement
    categories, festivals) - one source of truth shared with the backend's validation."""

    permission_classes = [IsAuthenticated]
    required_page = ClientProfile.Page.CREATIVE_GENERATION

    def get(self, request, company_id):
        from common.ai_config import get_provider_name

        self.get_company()
        payload = options_payload()
        # Only these image providers take a reference picture; the others can still design on the person's image.
        payload['reference'] = {'inspire_supported': get_provider_name('image') in ('gemini', 'openai')}
        return Response(payload)


def _variation_for(view, pk, variation_id):
    company = view.get_company()
    generation_request = generics.get_object_or_404(GenerationRequest, pk=pk, company=company)
    variation = generics.get_object_or_404(GenerationVariation, pk=variation_id, generation_request=generation_request)
    return generation_request, variation


class VariationEditView(CompanyScopedMixin, APIView):
    """Admin: edit one variation's or slide's copy. The text on the image is re-rendered onto the kept picture -
    exact spelling, no AI call and no credit used."""

    permission_classes = [IsAdmin]

    def patch(self, request, company_id, pk, variation_id):
        generation_request, variation = _variation_for(self, pk, variation_id)
        if variation.status == GenerationVariation.Status.PROCESSING:
            return Response({'detail': 'This image is being regenerated - try again when it is ready.'}, status=status.HTTP_409_CONFLICT)
        serializer = VariationEditSerializer(variation, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        on_image = {'eyebrow', 'headline', 'description', 'cta'} & set(serializer.validated_data)
        if on_image and not variation.background:
            return Response(
                {'detail': 'This creative was made before editable text was available - regenerate it to edit the text on the image.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        serializer.save()
        if on_image:
            render_variation(variation, BrandKit(generation_request.company))
            variation.save()
        log_activity(
            module=ActivityLog.Module.CREATIVE, action='Creative text edited',
            description=f'{generation_request.get_creative_type_display()} #{variation.variation_number}',
            company=generation_request.company, request=request,
        )
        return Response(GenerationRequestSerializer(generation_request).data)


class VariationRegenerateView(CompanyScopedMixin, APIView):
    """Admin: draw a new picture for one variation or one carousel slide, keeping its copy (one image credit)."""

    permission_classes = [IsAdmin]

    def post(self, request, company_id, pk, variation_id):
        from apps.platform_settings.services import check_daily_generation_limit
        from apps.subscriptions.enforcement import check_quota

        generation_request, variation = _variation_for(self, pk, variation_id)
        if generation_request.status != GenerationRequest.Status.SUCCEEDED:
            return Response({'detail': 'Only a finished creative can have an image regenerated.'}, status=status.HTTP_400_BAD_REQUEST)
        if variation.status == GenerationVariation.Status.PROCESSING:
            return Response({'detail': 'This image is already being regenerated.'}, status=status.HTTP_409_CONFLICT)
        check_daily_generation_limit(generation_request.company)
        check_quota(generation_request.company, 'creative')

        variation.status = GenerationVariation.Status.PROCESSING
        variation.error_message = ''
        variation.save(update_fields=['status', 'error_message', 'updated_at'])
        try:
            regenerate_variation.delay(variation.id)
        except Exception:  # noqa: BLE001 - broker unreachable: the image stays as it was
            variation.status = GenerationVariation.Status.READY
            variation.save(update_fields=['status', 'updated_at'])
            return queue_failure_response()
        log_activity(
            module=ActivityLog.Module.CREATIVE, action='Creative image regenerated',
            description=f'{generation_request.get_creative_type_display()} #{variation.variation_number}',
            company=generation_request.company, request=request,
        )
        generation_request.refresh_from_db()
        return Response(GenerationRequestSerializer(generation_request).data, status=status.HTTP_202_ACCEPTED)


class GenerationRequestDownloadView(CompanyScopedMixin, APIView):
    """Admin or the owning client: every image of a creative (all slides of a carousel) as one zip."""

    permission_classes = [IsAuthenticated]
    required_page = ClientProfile.Page.CREATIVE_GENERATION

    def get(self, request, company_id, pk):
        company = self.get_company()
        generation_request = generics.get_object_or_404(GenerationRequest, pk=pk, company=company)
        variations = [v for v in generation_request.variations.order_by('variation_number') if v.image]
        if not variations:
            return Response({'detail': 'This creative has no images yet.'}, status=status.HTTP_404_NOT_FOUND)
        is_carousel = generation_request.creative_type == GenerationRequest.CreativeType.CAROUSEL
        label = 'slide' if is_carousel else 'variation'
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as archive:
            for variation in variations:
                extension = variation.image.name.rsplit('.', 1)[-1] if '.' in variation.image.name else 'jpg'
                with variation.image.open('rb') as f:
                    archive.writestr(f'{label}_{variation.variation_number:02d}.{extension}', f.read())
        name = slugify(f'{company.name}-{generation_request.get_creative_type_display()}-{generation_request.id}') or 'creative'
        response = HttpResponse(buffer.getvalue(), content_type='application/zip')
        response['Content-Disposition'] = f'attachment; filename="{name}.zip"'
        return response
