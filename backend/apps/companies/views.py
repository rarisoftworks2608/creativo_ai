import re

from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

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
        return Response(ClientProfileSerializer(instance).data)


IMAGE_EXTENSION_RE = re.compile(r'\.(png|jpe?g|gif|webp|svg)$', re.IGNORECASE)


class AdminDashboardStatsView(APIView):
    """Admin: aggregate stats for the admin dashboard landing page (Epic 14).

    Publishing/subscription-status widgets from the epic's full wishlist are
    intentionally left out - Epics 11 (Publishing) and 17 (Subscriptions) don't
    exist yet, and fabricating numbers for features that aren't built would be
    worse than just not showing them.
    """

    permission_classes = [IsAdmin]

    def get(self, request):
        from django.db.models import Sum

        from apps.content_calendar.models import ContentCalendarItem
        from apps.creative_generation.models import GenerationRequest
        from apps.video_generation.models import VideoGenerationRequest

        creative_succeeded = GenerationRequest.objects.filter(status=GenerationRequest.Status.SUCCEEDED).count()
        video_succeeded = VideoGenerationRequest.objects.filter(status=VideoGenerationRequest.Status.SUCCEEDED).count()
        creative_failed = GenerationRequest.objects.filter(status=GenerationRequest.Status.FAILED).count()
        video_failed = VideoGenerationRequest.objects.filter(status=VideoGenerationRequest.Status.FAILED).count()
        creative_cost = GenerationRequest.objects.aggregate(total=Sum('cost_usd'))['total'] or 0
        video_cost = VideoGenerationRequest.objects.aggregate(total=Sum('cost_usd'))['total'] or 0

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
        })


class MediaLibraryView(APIView):
    """Admin: a unified, read-mostly view across a company's media - brand assets,
    generated creative variations, and generated videos (Epic 08: Media Library).

    Only brand assets are renamable/deletable here (via the brand app's own
    endpoints, linked by `source_id`) - generated creatives/videos are browse/download
    only, since deleting one could corrupt approval history (an already-approved
    item's selected variation, a video a client has already reviewed, ...).
    """

    permission_classes = [IsAdmin]

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
