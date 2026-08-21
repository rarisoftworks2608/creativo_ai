from rest_framework import serializers

from .models import Notification


class UnreadCountSerializer(serializers.Serializer):
    count = serializers.IntegerField()


class MarkAllReadResultSerializer(serializers.Serializer):
    updated = serializers.IntegerField()


class NotificationSerializer(serializers.ModelSerializer):
    notification_type_display = serializers.CharField(source='get_notification_type_display', read_only=True)
    company_name = serializers.CharField(source='company.name', read_only=True, default='')

    class Meta:
        model = Notification
        fields = [
            'id', 'notification_type', 'notification_type_display', 'title', 'message', 'url',
            'company', 'company_name', 'content_calendar_item', 'is_read', 'read_at', 'created_at',
        ]
        read_only_fields = fields
