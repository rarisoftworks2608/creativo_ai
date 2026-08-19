import re

from rest_framework import serializers

from .models import BrandAsset, BrandProfile

HEX_COLOR_RE = re.compile(r'^#(?:[0-9a-fA-F]{3}){1,2}$')


class BrandProfileSerializer(serializers.ModelSerializer):
    """Read representation of a company's brand profile, including its identity images."""

    class Meta:
        model = BrandProfile
        fields = [
            'id', 'company',
            'logo', 'secondary_logo', 'favicon', 'brand_colors', 'fonts', 'typography_notes',
            'brand_voice', 'tone', 'writing_style', 'visual_style', 'dos', 'donts', 'keywords', 'restricted_words',
            'customer_personas', 'offers', 'campaign_information',
            'created_at', 'updated_at',
        ]
        read_only_fields = fields


class BrandProfileWriteSerializer(serializers.ModelSerializer):
    """Used by an Admin to edit a brand profile's text/JSON fields (identity images are uploaded separately)."""

    class Meta:
        model = BrandProfile
        fields = [
            'brand_colors', 'fonts', 'typography_notes',
            'brand_voice', 'tone', 'writing_style', 'visual_style', 'dos', 'donts', 'keywords', 'restricted_words',
            'customer_personas', 'offers', 'campaign_information',
        ]

    def validate_brand_colors(self, value):
        if not isinstance(value, list):
            raise serializers.ValidationError('Brand colors must be a list.')
        for item in value:
            if not isinstance(item, dict) or 'hex' not in item:
                raise serializers.ValidationError('Each color must be an object with at least a "hex" value.')
            if not HEX_COLOR_RE.match(item['hex']):
                raise serializers.ValidationError(f'"{item["hex"]}" is not a valid hex color.')
        return value

    def validate_fonts(self, value):
        if not isinstance(value, list):
            raise serializers.ValidationError('Fonts must be a list.')
        for item in value:
            if not isinstance(item, dict) or not item.get('name'):
                raise serializers.ValidationError('Each font must be an object with at least a "name" value.')
        return value

    def _validate_string_list(self, value, field_label):
        if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
            raise serializers.ValidationError(f'{field_label} must be a list of strings.')
        return value

    def validate_dos(self, value):
        return self._validate_string_list(value, "Do's")

    def validate_donts(self, value):
        return self._validate_string_list(value, "Don'ts")

    def validate_keywords(self, value):
        return self._validate_string_list(value, 'Keywords')

    def validate_restricted_words(self, value):
        return self._validate_string_list(value, 'Restricted words')

    def validate_offers(self, value):
        return self._validate_string_list(value, 'Offers')

    def validate_customer_personas(self, value):
        if not isinstance(value, list):
            raise serializers.ValidationError('Customer personas must be a list.')
        for item in value:
            if not isinstance(item, dict) or not item.get('name'):
                raise serializers.ValidationError('Each persona must be an object with at least a "name" value.')
        return value


class BrandAssetSerializer(serializers.ModelSerializer):
    """Read representation of a brand asset library entry."""

    uploaded_by_email = serializers.EmailField(source='uploaded_by.email', read_only=True, default=None)

    class Meta:
        model = BrandAsset
        fields = ['id', 'company', 'category', 'file', 'name', 'uploaded_by', 'uploaded_by_email', 'created_at']
        read_only_fields = fields


class BrandAssetUploadSerializer(serializers.ModelSerializer):
    """Used by an Admin to upload a new file into the brand asset library."""

    class Meta:
        model = BrandAsset
        fields = ['category', 'file', 'name']

    def create(self, validated_data):
        request = self.context.get('request')
        return BrandAsset.objects.create(
            company=self.context['company'],
            uploaded_by=getattr(request, 'user', None),
            **validated_data,
        )
