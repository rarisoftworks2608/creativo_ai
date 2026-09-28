from rest_framework import serializers

from .models import PromptTemplate


class PromptTemplateSerializer(serializers.ModelSerializer):
    category_display = serializers.CharField(source='get_category_display', read_only=True)
    created_by_name = serializers.CharField(source='created_by.get_full_name', read_only=True, default='')

    class Meta:
        model = PromptTemplate
        fields = [
            'id', 'slug', 'category', 'category_display', 'platform', 'creative_type', 'name', 'body',
            'version', 'is_active', 'created_by_name', 'created_at', 'updated_at',
        ]
        read_only_fields = ['version', 'is_active', 'created_at', 'updated_at']


class PromptTemplateCreateSerializer(serializers.ModelSerializer):
    """Creates the first version (version=1, inactive until explicitly activated)."""

    class Meta:
        model = PromptTemplate
        fields = ['slug', 'category', 'platform', 'creative_type', 'name', 'body']

    def validate_slug(self, value):
        if PromptTemplate.objects.filter(slug=value).exists():
            raise serializers.ValidationError('A template with this slug already exists - use "new version" instead.')
        return value


class NewVersionSerializer(serializers.Serializer):
    name = serializers.CharField(required=False, allow_blank=False)
    body = serializers.CharField(required=False, allow_blank=False)
