from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.brand.models import BrandProfile
from apps.companies.models import Company
from common.permissions import IsAdmin

from . import prompts, schemas
from .ai_client import AIProviderError, AIProviderNotConfigured, get_provider
from .models import BrandContext, StrategyOutput
from .serializers import BrandContextSerializer, GenerateStrategySerializer, StrategyOutputSerializer


def _get_company(company_id):
    return generics.get_object_or_404(Company, pk=company_id)


def _ai_error_response(exc):
    if isinstance(exc, AIProviderNotConfigured):
        return Response({'detail': str(exc)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
    return Response({'detail': str(exc)}, status=status.HTTP_502_BAD_GATEWAY)


class BrandContextView(generics.RetrieveAPIView):
    """Admin: view the company's most recently generated brand context (Epic 05: Create brand context)."""

    serializer_class = BrandContextSerializer
    permission_classes = [IsAdmin]

    def get_object(self):
        company = _get_company(self.kwargs['company_id'])
        return generics.get_object_or_404(BrandContext, company=company)


class BrandContextGenerateView(APIView):
    """Admin: (re)generate the brand context from Company + BrandProfile data (Epic 05: Brand Understanding).

    Analyzes the business, brand guidelines, products/services and audience in a single call and
    stores a synthesized summary that AI Planning / AI Strategy generations are grounded in.
    """

    permission_classes = [IsAdmin]
    serializer_class = BrandContextSerializer

    def post(self, request, company_id):
        company = _get_company(company_id)
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


class StrategyOutputListView(generics.ListAPIView):
    """Admin: list a company's past AI Planning / AI Strategy generations, optionally filtered by kind."""

    serializer_class = StrategyOutputSerializer
    permission_classes = [IsAdmin]

    def get_queryset(self):
        company = _get_company(self.kwargs['company_id'])
        queryset = StrategyOutput.objects.filter(company=company)
        kind = self.request.query_params.get('kind')
        if kind:
            queryset = queryset.filter(kind=kind)
        return queryset


class StrategyOutputDetailView(generics.RetrieveAPIView):
    """Admin: view a single past AI Planning / AI Strategy generation."""

    serializer_class = StrategyOutputSerializer
    permission_classes = [IsAdmin]

    def get_queryset(self):
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

        company = _get_company(company_id)
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
