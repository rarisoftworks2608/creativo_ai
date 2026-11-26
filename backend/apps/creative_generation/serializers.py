import json

from rest_framework import serializers

from .creative_types import (
    DESIGN_STYLES, SPECS, clean_brief_fields, missing_required, resolve_aspect_ratio, spec_for,
)
from .models import GenerationRequest, GenerationVariation

MAX_REFERENCE_BYTES = 10 * 1024 * 1024
REFERENCE_IMAGE_EXTENSIONS = ('.jpg', '.jpeg', '.png', '.webp')

MAX_PHOTO_BYTES = 5 * 1024 * 1024


class GenerationVariationSerializer(serializers.ModelSerializer):
    can_edit = serializers.SerializerMethodField()

    class Meta:
        model = GenerationVariation
        fields = [
            'id', 'variation_number', 'image', 'caption', 'eyebrow', 'headline', 'description',
            'cta', 'hashtags', 'keywords', 'is_selected', 'created_at', 'slide_role', 'status', 'error_message',
            'can_edit', 'updated_at',
        ]
        read_only_fields = fields

    def get_can_edit(self, variation):
        """The copy can be edited and re-rendered for free only when the picture before the text was kept."""
        return bool(variation.background)


class GenerationRequestSerializer(serializers.ModelSerializer):
    creative_type_display = serializers.CharField(source='get_creative_type_display', read_only=True)
    platform_display = serializers.CharField(source='get_platform_display', read_only=True)
    variations = GenerationVariationSerializer(many=True, read_only=True)
    resolved_aspect_ratio = serializers.SerializerMethodField()

    class Meta:
        model = GenerationRequest
        fields = [
            'id', 'company', 'content_calendar_item', 'creative_type', 'creative_type_display',
            'platform', 'platform_display', 'variation_count', 'include_text_overlay', 'prompt_brief',
            'product_info', 'status', 'error_message', 'retry_count', 'model_used', 'usage', 'cost_usd',
            'created_by', 'created_at', 'updated_at', 'variations',
            'brief_fields', 'design_style', 'aspect_ratio', 'resolved_aspect_ratio', 'slide_count', 'customer_photo',
            'reference_image', 'reference_mode',
        ]
        read_only_fields = fields

    def get_resolved_aspect_ratio(self, request):
        return resolve_aspect_ratio(request.creative_type, request.aspect_ratio)


class GenerationRequestCreateSerializer(serializers.ModelSerializer):
    """Starts a generation. Accepts JSON or multipart (multipart when a testimonial carries the client's photo -
    `brief_fields` then arrives as a JSON string)."""

    brief_fields = serializers.JSONField(required=False)
    customer_photo = serializers.ImageField(required=False, allow_null=True)
    reference_image = serializers.ImageField(required=False, allow_null=True)
    reference_asset = serializers.IntegerField(required=False, allow_null=True, write_only=True)
    reference_mode = serializers.ChoiceField(
        choices=GenerationRequest.ReferenceMode.choices, required=False, allow_blank=True,
    )

    class Meta:
        model = GenerationRequest
        fields = [
            'id', 'content_calendar_item', 'creative_type', 'platform', 'variation_count',
            'include_text_overlay', 'prompt_brief', 'product_info',
            'brief_fields', 'design_style', 'aspect_ratio', 'slide_count', 'customer_photo',
            'reference_image', 'reference_asset', 'reference_mode',
        ]
        read_only_fields = ['id']

    def validate_content_calendar_item(self, item):
        company = self.context['company']
        if item is not None and item.company_id != company.id:
            raise serializers.ValidationError('This content calendar item does not belong to this company.')
        return item

    def validate_variation_count(self, value):
        from apps.platform_settings.models import PlatformSettings

        max_allowed = PlatformSettings.load().max_variation_count
        if not 1 <= value <= max_allowed:
            raise serializers.ValidationError(f'variation_count must be between 1 and {max_allowed}.')
        return value

    def validate_brief_fields(self, value):
        if isinstance(value, str):
            try:
                value = json.loads(value or '{}')
            except ValueError as exc:
                raise serializers.ValidationError('brief_fields must be a JSON object.') from exc
        if not isinstance(value, dict):
            raise serializers.ValidationError('brief_fields must be an object.')
        return value

    def validate_design_style(self, value):
        if value and value not in DESIGN_STYLES:
            raise serializers.ValidationError(f'Unknown design style "{value}".')
        return value

    def validate_customer_photo(self, photo):
        if photo and photo.size > MAX_PHOTO_BYTES:
            raise serializers.ValidationError('The photo must be 5 MB or smaller.')
        return photo

    def validate_reference_image(self, image):
        if image and image.size > MAX_REFERENCE_BYTES:
            raise serializers.ValidationError('The reference image must be 10 MB or smaller.')
        return image

    def validate_reference_asset(self, asset_id):
        """A brand asset of this company that is an image - it is copied onto the request at creation."""
        if not asset_id:
            return None
        from apps.brand.models import BrandAsset

        asset = BrandAsset.objects.filter(pk=asset_id, company=self.context['company']).first()
        if asset is None:
            raise serializers.ValidationError('That brand asset does not belong to this company.')
        if not asset.file.name.lower().endswith(REFERENCE_IMAGE_EXTENSIONS):
            raise serializers.ValidationError('Choose an image (JPG, PNG or WebP) from the brand assets.')
        return asset

    def validate(self, attrs):
        creative_type = attrs.get('creative_type', '')
        spec = spec_for(creative_type)
        sent_fields = 'brief_fields' in self.initial_data
        fields = clean_brief_fields(creative_type, attrs.get('brief_fields') or {})
        errors = {}

        # Type-specific inputs: checked whenever they are sent. A testimonial always needs a real quote - the
        # system never writes one.
        if creative_type in SPECS and (sent_fields or creative_type == 'testimonial_creative'):
            missing = missing_required(creative_type, fields)
            if missing:
                errors['brief_fields'] = [f'{spec.label} needs: {", ".join(missing)}.']
        if 'rating' in fields:
            try:
                rating = int(fields['rating'])
            except (TypeError, ValueError):
                rating = 0
            if not 1 <= rating <= 5:
                errors.setdefault('brief_fields', []).append('rating must be a whole number from 1 to 5.')
            else:
                fields['rating'] = rating
        if 'allow_shorten' in fields:
            fields['allow_shorten'] = fields['allow_shorten'] in (True, 'true', 'True', '1', 1)

        ratio = attrs.get('aspect_ratio') or ''
        if ratio and ratio not in spec.aspects:
            errors['aspect_ratio'] = [f'{spec.label} can be made at {", ".join(spec.aspects)}.']

        slide_count = attrs.get('slide_count') or 0
        if creative_type == GenerationRequest.CreativeType.CAROUSEL:
            slide_count = slide_count or 5
            if not 3 <= slide_count <= 10:
                errors['slide_count'] = ['A carousel has 3 to 10 slides.']
        else:
            slide_count = 0

        if attrs.get('customer_photo') and creative_type != 'testimonial_creative':
            errors['customer_photo'] = ['A client photo is only used on a testimonial creative.']

        if errors:
            raise serializers.ValidationError(errors)

        has_reference = bool(attrs.get('reference_image') or attrs.get('reference_asset'))
        if attrs.get('reference_image') and attrs.get('reference_asset'):
            errors['reference_image'] = ['Choose a brand asset or upload an image - not both.']
        if attrs.get('reference_mode') and not has_reference:
            errors['reference_mode'] = ['Choose or upload the reference image first.']
        if errors:
            raise serializers.ValidationError(errors)
        attrs['reference_mode'] = (attrs.get('reference_mode') or GenerationRequest.ReferenceMode.BASE) if has_reference else ''
        attrs['brief_fields'] = fields
        attrs['slide_count'] = slide_count
        if spec.force_overlay and creative_type in SPECS:
            attrs['include_text_overlay'] = True
        if creative_type == GenerationRequest.CreativeType.CAROUSEL:
            attrs['variation_count'] = 1  # a carousel is one design; its images are its slides
        return attrs

    def create(self, validated_data):
        asset = validated_data.pop('reference_asset', None)
        instance = super().create(validated_data)
        if asset is not None:
            import os

            from django.core.files.base import ContentFile

            with asset.file.open('rb') as source:
                instance.reference_image.save(os.path.basename(asset.file.name), ContentFile(source.read()), save=True)
        return instance


class VariationEditSerializer(serializers.ModelSerializer):
    """The copy of one variation or slide, edited by hand - re-rendered onto the kept picture, no AI call."""

    class Meta:
        model = GenerationVariation
        fields = ['eyebrow', 'headline', 'description', 'cta', 'caption', 'hashtags']
        extra_kwargs = {name: {'required': False} for name in fields}

    def validate_hashtags(self, value):
        if not isinstance(value, list):
            raise serializers.ValidationError('hashtags must be a list.')
        return [str(tag).strip() for tag in value if str(tag).strip()][:30]
