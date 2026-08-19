from django.http import Http404
from rest_framework import generics, status
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.companies.models import Company
from common.permissions import IsAdmin

from .models import BrandAsset, BrandProfile
from .serializers import (
    BrandAssetSerializer,
    BrandAssetUploadSerializer,
    BrandProfileSerializer,
    BrandProfileWriteSerializer,
)

IMAGE_SLOTS = {'logo', 'secondary_logo', 'favicon'}


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


class AdminWriteMixin:
    """GET is open to the company's admin/client; any other method is admin-only."""

    def check_permissions(self, request):
        super().check_permissions(request)
        if request.method not in ('GET', 'HEAD', 'OPTIONS') and not (
            request.user.is_authenticated and request.user.is_admin
        ):
            self.permission_denied(request, message='Only admins can edit brand information.')


class BrandProfileView(CompanyScopedMixin, AdminWriteMixin, generics.RetrieveUpdateAPIView):
    """View or edit a company's brand profile (Epic 03: Brand Identity / Guidelines / Marketing Information).

    The profile is created on first access, so a company always has exactly one.
    """

    permission_classes = [IsAuthenticated]

    def get_serializer_class(self):
        if self.request.method in ('PUT', 'PATCH'):
            return BrandProfileWriteSerializer
        return BrandProfileSerializer

    def get_object(self):
        company = self.get_company()
        profile, _created = BrandProfile.objects.get_or_create(company=company)
        return profile

    def update(self, request, *args, **kwargs):
        super().update(request, *args, **kwargs)
        return Response(BrandProfileSerializer(self.get_object(), context=self.get_serializer_context()).data)


class BrandIdentityImageView(CompanyScopedMixin, APIView):
    """Admin: upload or remove a single brand identity image (logo / secondary logo / favicon)."""

    permission_classes = [IsAdmin]
    parser_classes = [MultiPartParser, FormParser]
    serializer_class = BrandProfileSerializer

    def _slot(self, slot):
        if slot not in IMAGE_SLOTS:
            raise Http404
        return slot

    def post(self, request, company_id, slot):
        slot = self._slot(slot)
        company = self.get_company()
        upload = request.FILES.get('file')
        if not upload:
            return Response({'detail': 'file is required.'}, status=status.HTTP_400_BAD_REQUEST)

        profile, _created = BrandProfile.objects.get_or_create(company=company)
        old_file = getattr(profile, slot)
        if old_file:
            old_file.delete(save=False)
        setattr(profile, slot, upload)
        profile.save(update_fields=[slot, 'updated_at'])
        return Response(BrandProfileSerializer(profile, context={'request': request}).data)

    def delete(self, request, company_id, slot):
        slot = self._slot(slot)
        company = self.get_company()
        profile, _created = BrandProfile.objects.get_or_create(company=company)
        old_file = getattr(profile, slot)
        if old_file:
            old_file.delete(save=False)
        setattr(profile, slot, None)
        profile.save(update_fields=[slot, 'updated_at'])
        return Response(BrandProfileSerializer(profile, context={'request': request}).data)


class BrandAssetListCreateView(CompanyScopedMixin, AdminWriteMixin, generics.ListCreateAPIView):
    """List a company's brand asset library, or upload a new file into it (Epic 03: Brand Assets)."""

    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return BrandAssetUploadSerializer
        return BrandAssetSerializer

    def get_queryset(self):
        queryset = BrandAsset.objects.filter(company=self.get_company())
        category = self.request.query_params.get('category')
        if category:
            queryset = queryset.filter(category=category)
        return queryset

    def create(self, request, *args, **kwargs):
        company = self.get_company()
        serializer = self.get_serializer(data=request.data, context={'request': request, 'company': company})
        serializer.is_valid(raise_exception=True)
        asset = serializer.save()
        return Response(BrandAssetSerializer(asset, context={'request': request}).data, status=status.HTTP_201_CREATED)


class BrandAssetDetailView(CompanyScopedMixin, AdminWriteMixin, generics.RetrieveDestroyAPIView):
    """View or delete a single brand asset."""

    serializer_class = BrandAssetSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return BrandAsset.objects.filter(company=self.get_company())

    def perform_destroy(self, instance):
        instance.file.delete(save=False)
        instance.delete()
