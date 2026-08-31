from django.http import Http404
from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.brand.models import BrandProfile
from apps.companies.models import ClientProfile, Company
from common.permissions import IsAdmin

from . import prompts, schemas
from .ai_client import AIProviderError, AIProviderNotConfigured, get_provider
from .models import BrandContext, StrategyOutput
from .serializers import BrandContextSerializer, GenerateStrategySerializer, StrategyOutputSerializer


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


def _ai_error_response(exc):
    if isinstance(exc, AIProviderNotConfigured):
        return Response({'detail': str(exc)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
    return Response({'detail': str(exc)}, status=status.HTTP_502_BAD_GATEWAY)


class BrandContextView(CompanyScopedMixin, generics.RetrieveAPIView):
    """View the company's most recently generated brand context - admin or the owning
    client, read-only for the client (Epic 05: Create brand context).
    """

    serializer_class = BrandContextSerializer
    permission_classes = [IsAuthenticated]
    required_page = ClientProfile.Page.AI_STRATEGY

    def get_object(self):
        company = self.get_company()
        return generics.get_object_or_404(BrandContext, company=company)


class BrandContextGenerateView(APIView):
    """Admin: (re)generate the brand context from Company + BrandProfile data (Epic 05: Brand Understanding).

    Analyzes the business, brand guidelines, products/services and audience in a single call and
    stores a synthesized summary that AI Planning / AI Strategy generations are grounded in.
    """

    permission_classes = [IsAdmin]
    serializer_class = BrandContextSerializer

    def post(self, request, company_id):
        company = generics.get_object_or_404(Company, pk=company_id)
        brand_profile = BrandProfile.objects.filter(company=company).first()

        provider = get_provider()
        try:
            data = provider.generate_json(
                system=prompts.BRAND_CONTEXT_SYSTEM_PROMPT,
                prompt=prompts.build_brand_context_prompt(company, brand_profile),
                json_schema=schemas.BRAND_CONTEXT_SCHEMA,
            )
        except AIProviderError as exc:
            return _ai_error_response(exc)

        context, _created = BrandContext.objects.update_or_create(
            company=company,
            defaults={
                'business_analysis': data.get('business_analysis', ''),
                'brand_guidelines_analysis': data.get('brand_guidelines_analysis', ''),
                'products_services_analysis': data.get('products_services_analysis', ''),
                'audience_analysis': data.get('audience_analysis', ''),
                'summary': data.get('summary', ''),
                'model_used': getattr(provider, 'model', ''),
                'generated_by': request.user,
            },
        )
        return Response(BrandContextSerializer(context).data)


class StrategyOutputListView(CompanyScopedMixin, generics.ListAPIView):
    """List a company's past AI Planning / AI Strategy generations, optionally filtered
    by kind - admin or the owning client, read-only for the client.
    """

    serializer_class = StrategyOutputSerializer
    permission_classes = [IsAuthenticated]
    required_page = ClientProfile.Page.AI_STRATEGY

    def get_queryset(self):
        company = self.get_company()
        queryset = StrategyOutput.objects.filter(company=company)
        kind = self.request.query_params.get('kind')
        if kind:
            queryset = queryset.filter(kind=kind)
        return queryset


class StrategyOutputDetailView(CompanyScopedMixin, generics.RetrieveDestroyAPIView):
    """View a single past AI Planning / AI Strategy generation - admin or the owning
    client, read-only for the client. Deleting a history entry is admin-only.
    """

    serializer_class = StrategyOutputSerializer
    permission_classes = [IsAuthenticated]
    required_page = ClientProfile.Page.AI_STRATEGY

    def check_permissions(self, request):
        super().check_permissions(request)
        if request.method not in ('GET', 'HEAD', 'OPTIONS') and not (
            request.user.is_authenticated and request.user.is_admin
        ):
            self.permission_denied(request, message='Only admins can delete a strategy generation.')

    def get_queryset(self):
        self.get_company()
        return StrategyOutput.objects.filter(company_id=self.kwargs['company_id'])


class StrategyOutputGenerateView(APIView):
    """Admin: generate a new AI Planning / AI Strategy output of the given kind (Epic 05).

    `kind` is one of schemas.STRATEGY_KINDS (content_ideas, topic_suggestions, content_themes,
    campaign_suggestions, posting_suggestions, content_strategy, platform_strategy,
    audience_strategy, campaign_strategy). Requires a brand context to already exist.
    """

    permission_classes = [IsAdmin]
    serializer_class = GenerateStrategySerializer

    def post(self, request, company_id, kind):
        if kind not in schemas.STRATEGY_KINDS:
            return Response({'detail': f'Unknown strategy kind "{kind}".'}, status=status.HTTP_404_NOT_FOUND)

        company = generics.get_object_or_404(Company, pk=company_id)
        brand_context = BrandContext.objects.filter(company=company).first()
        if brand_context is None:
            return Response(
                {'detail': 'Generate the brand context for this company before requesting a strategy generation.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        input_serializer = GenerateStrategySerializer(data=request.data)
        input_serializer.is_valid(raise_exception=True)
        notes = input_serializer.validated_data['notes']

        spec = schemas.STRATEGY_KINDS[kind]
        provider = get_provider()
        try:
            data = provider.generate_json(
                system=prompts.STRATEGY_SYSTEM_PROMPT,
                prompt=prompts.build_strategy_prompt(brand_context, spec['instruction'], notes),
                json_schema=spec['schema'],
            )
        except AIProviderError as exc:
            return _ai_error_response(exc)

        output = StrategyOutput.objects.create(
            company=company,
            kind=kind,
            notes=notes,
            result=data,
            model_used=getattr(provider, 'model', ''),
            created_by=request.user,
        )
        return Response(StrategyOutputSerializer(output).data, status=status.HTTP_201_CREATED)
