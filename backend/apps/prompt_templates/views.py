from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.views import APIView

from common.permissions import IsAdmin

from .models import PromptTemplate
from .serializers import NewVersionSerializer, PromptTemplateCreateSerializer, PromptTemplateSerializer
from .services import activate_version, create_new_version, deactivate_version


class PromptTemplateListCreateView(generics.ListCreateAPIView):
    """Admin: browse the prompt library, or create a brand-new template (version 1).

    Only the latest version of each slug is returned by default so the list
    reads as "one row per template" - pass `?all_versions=1` to see everything,
    or use the history endpoint for one slug's full trail.
    """

    permission_classes = [IsAdmin]

    def get_serializer_class(self):
        return PromptTemplateCreateSerializer if self.request.method == 'POST' else PromptTemplateSerializer

    def get_queryset(self):
        queryset = PromptTemplate.objects.select_related('created_by')

        category = self.request.query_params.get('category')
        if category:
            queryset = queryset.filter(category=category)

        if self.request.query_params.get('all_versions'):
            return queryset

        latest_by_slug = {}
        for template in queryset.order_by('slug', '-version'):
            latest_by_slug.setdefault(template.slug, template.id)
        return queryset.filter(id__in=list(latest_by_slug.values()))

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        template = serializer.save(created_by=request.user, version=1)
        return Response(PromptTemplateSerializer(template).data, status=status.HTTP_201_CREATED)


class PromptTemplateDetailView(generics.RetrieveDestroyAPIView):
    """Admin: view one version, or delete it (only ever the safe thing to do on
    an inactive version - deleting the active one would silently blank out live
    generation guidance, so that's blocked below).
    """

    serializer_class = PromptTemplateSerializer
    permission_classes = [IsAdmin]
    queryset = PromptTemplate.objects.all()

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        if instance.is_active:
            return Response(
                {'detail': 'Deactivate this version before deleting it.'}, status=status.HTTP_400_BAD_REQUEST,
            )
        return super().destroy(request, *args, **kwargs)


class PromptTemplateHistoryView(generics.ListAPIView):
    """Admin: every version of one template, newest first (Epic 21: History)."""

    serializer_class = PromptTemplateSerializer
    permission_classes = [IsAdmin]

    def get_queryset(self):
        return PromptTemplate.objects.filter(slug=self.kwargs['slug']).order_by('-version')


class PromptTemplateNewVersionView(APIView):
    """Admin: create the next version under this template's slug (Epic 21: Create version)."""

    permission_classes = [IsAdmin]
    serializer_class = NewVersionSerializer

    def post(self, request, pk):
        template = generics.get_object_or_404(PromptTemplate, pk=pk)
        serializer = NewVersionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        new_version = create_new_version(template, user=request.user, **serializer.validated_data)
        return Response(PromptTemplateSerializer(new_version).data, status=status.HTTP_201_CREATED)


class PromptTemplateActivateView(APIView):
    permission_classes = [IsAdmin]
    serializer_class = PromptTemplateSerializer

    def post(self, request, pk):
        template = generics.get_object_or_404(PromptTemplate, pk=pk)
        activate_version(template)
        return Response(PromptTemplateSerializer(template).data)


class PromptTemplateDeactivateView(APIView):
    permission_classes = [IsAdmin]
    serializer_class = PromptTemplateSerializer

    def post(self, request, pk):
        template = generics.get_object_or_404(PromptTemplate, pk=pk)
        deactivate_version(template)
        return Response(PromptTemplateSerializer(template).data)
