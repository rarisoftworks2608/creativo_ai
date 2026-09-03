from rest_framework import serializers

from .models import GenerationRequest, GenerationVariation


class GenerationVariationSerializer(serializers.ModelSerializer):
    class Meta:
        model = GenerationVariation
        fields = [
            'id', 'variation_number', 'image', 'caption', 'headline', 'description',
            'cta', 'hashtags', 'keywords', 'is_selected', 'created_at',
        ]
        read_only_fields = fields


class GenerationRequestSerializer(serializers.ModelSerializer):
    creative_type_display = serializers.CharField(source='get_creative_type_display', read_only=True)
    platform_display = serializers.CharField(source='get_platform_display', read_only=True)
    variations = GenerationVariationSerializer(many=True, read_only=True)

    class Meta:
        model = GenerationRequest
        fields = [
            'id', 'company', 'content_calendar_item', 'creative_type', 'creative_type_display',
            'platform', 'platform_display', 'variation_count', 'prompt_brief', 'product_info', 'status',
            'error_message', 'retry_count', 'model_used', 'usage', 'cost_usd', 'created_by', 'created_at',
            'updated_at', 'variations',
        ]
        read_only_fields = fields


class GenerationRequestCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = GenerationRequest
        fields = [
            'id', 'content_calendar_item', 'creative_type', 'platform', 'variation_count',
            'prompt_brief', 'product_info',
        ]
        read_only_fields = ['id']

    def validate_content_calendar_item(self, item):
        company = self.context['company']
        if item is not None and item.company_id != company.id:
            raise serializers.ValidationError('This content calendar item does not belong to this company.')
        return item

    def validate_variation_count(self, value):
        if not 1 <= value <= 3:
            raise serializers.ValidationError('variation_count must be between 1 and 3.')
        return value
