from rest_framework import serializers

from .models import BrandContext, StrategyOutput


class BrandContextSerializer(serializers.ModelSerializer):
    class Meta:
        model = BrandContext
        fields = [
            'id', 'company', 'business_analysis', 'brand_guidelines_analysis', 'products_services_analysis',
            'audience_analysis', 'summary', 'model_used', 'generated_by', 'created_at', 'updated_at',
        ]
        read_only_fields = fields


class StrategyOutputSerializer(serializers.ModelSerializer):
    kind_display = serializers.CharField(source='get_kind_display', read_only=True)

    class Meta:
        model = StrategyOutput
        fields = ['id', 'company', 'kind', 'kind_display', 'notes', 'result', 'model_used', 'created_by', 'created_at']
        read_only_fields = fields


class GenerateStrategySerializer(serializers.Serializer):
    """Input for triggering a new StrategyOutput generation."""

    notes = serializers.CharField(required=False, allow_blank=True, default='')
