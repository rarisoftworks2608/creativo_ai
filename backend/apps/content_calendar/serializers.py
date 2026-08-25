from rest_framework import serializers

from .models import ContentCalendarItem


class ContentCalendarItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = ContentCalendarItem
        fields = [
            'id', 'company', 'topic', 'category', 'weekly_theme', 'content_type', 'platforms',
            'objective', 'campaign', 'scheduled_date', 'scheduled_time',
            'caption_requirements', 'creative_requirements', 'cta', 'hashtags', 'source_notes',
            'status', 'source', 'client_feedback', 'regeneration_count', 'created_by', 'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'company', 'source', 'client_feedback', 'regeneration_count', 'created_by', 'created_at', 'updated_at',
        ]

    def validate_platforms(self, value):
        valid = {choice for choice, _label in ContentCalendarItem.Platform.choices}
        if not isinstance(value, list) or not value:
            raise serializers.ValidationError('Select at least one platform.')
        invalid = [v for v in value if v not in valid]
        if invalid:
            raise serializers.ValidationError(f'Invalid platform(s): {", ".join(invalid)}')
        return value

    def validate_hashtags(self, value):
        if value in (None, ''):
            return []
        if not isinstance(value, list):
            raise serializers.ValidationError('Hashtags must be a list of strings.')
        return value


class ExcelUploadSerializer(serializers.Serializer):
    file = serializers.FileField()
