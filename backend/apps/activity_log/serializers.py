from rest_framework import serializers

from .models import ActivityLog


class ActivityLogSerializer(serializers.ModelSerializer):
    user_name = serializers.SerializerMethodField()
    user_email = serializers.CharField(source='user.email', read_only=True, default='')
    module_display = serializers.CharField(source='get_module_display', read_only=True)
    company_name = serializers.CharField(source='company.name', read_only=True, default='')

    class Meta:
        model = ActivityLog
        fields = [
            'id', 'user', 'user_name', 'user_email', 'company', 'company_name',
            'module', 'module_display', 'action', 'description',
            'old_value', 'new_value', 'ip_address', 'created_at',
        ]

    def get_user_name(self, obj):
        return obj.user.get_full_name() if obj.user else 'System'
