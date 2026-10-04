from rest_framework import serializers

from .models import Event, WhatsAppConfig, WhatsAppMessage, WhatsAppTemplate
from .providers import normalize_phone


def _validate_numbers(value, label):
    if value in (None, ''):
        return []
    if not isinstance(value, list):
        raise serializers.ValidationError(f'{label} must be a list.')
    cleaned, seen = [], set()
    for entry in value:
        if not isinstance(entry, dict):
            raise serializers.ValidationError(f'Each {label.lower()} entry must have a name and phone.')
        phone = normalize_phone(entry.get('phone'))
        if not phone:
            raise serializers.ValidationError(
                f'"{entry.get("phone", "")}" is not a valid WhatsApp number - include the country code, e.g. +919876543210.'
            )
        if phone in seen:
            continue
        seen.add(phone)
        cleaned.append({'name': str(entry.get('name', '')).strip()[:100], 'phone': f'+{phone}'})
    return cleaned


class WhatsAppConfigSerializer(serializers.ModelSerializer):
    group_status_display = serializers.CharField(source='get_group_status_display', read_only=True)
    recipients = serializers.SerializerMethodField()
    available_events = serializers.SerializerMethodField()

    class Meta:
        model = WhatsAppConfig
        fields = [
            'id', 'company', 'is_enabled', 'business_number', 'client_numbers', 'internal_numbers',
            'include_client_users', 'group_name', 'group_description', 'group_status', 'group_status_display',
            'group_invite_link', 'group_created_at', 'enabled_events', 'language_code', 'recipients',
            'available_events', 'updated_at',
        ]
        read_only_fields = ['id', 'company', 'group_created_at', 'updated_at']

    def get_recipients(self, obj) -> list:
        from .services import recipients_for

        return recipients_for(obj)

    def get_available_events(self, obj) -> list:
        from .models import EVENT_AUDIENCE

        return [{'value': value, 'label': label, 'audience': EVENT_AUDIENCE.get(value, 'all')} for value, label in Event.choices]

    def validate_client_numbers(self, value):
        return _validate_numbers(value, 'Client numbers')

    def validate_internal_numbers(self, value):
        return _validate_numbers(value, 'Internal numbers')

    def validate_business_number(self, value):
        if value and not normalize_phone(value):
            raise serializers.ValidationError('Enter the business number with country code, e.g. +919876543210.')
        return f'+{normalize_phone(value)}' if value else ''

    def validate_enabled_events(self, value):
        valid = set(Event.values)
        if not isinstance(value, list) or any(v not in valid for v in value):
            raise serializers.ValidationError('Unknown event in enabled_events.')
        return value


class WhatsAppTemplateSerializer(serializers.ModelSerializer):
    event_display = serializers.CharField(source='get_event_display', read_only=True)
    meta_status_display = serializers.CharField(source='get_meta_status_display', read_only=True)
    placeholder_count = serializers.SerializerMethodField()

    class Meta:
        model = WhatsAppTemplate
        fields = [
            'id', 'event', 'event_display', 'name', 'language_code', 'category', 'body', 'variables',
            'placeholder_count', 'is_active', 'meta_status', 'meta_status_display', 'last_synced_at',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'meta_status', 'last_synced_at', 'created_at', 'updated_at']

    AVAILABLE_VARIABLES = {
        'company_name', 'topic', 'scheduled_date', 'link', 'approved_by', 'feedback', 'platform', 'error',
        'hours_waiting', 'period',
    }

    def get_placeholder_count(self, obj) -> int:
        import re

        return len(set(re.findall(r'\{\{(\d+)\}\}', obj.body or '')))

    def validate_variables(self, value):
        if not isinstance(value, list) or any(v not in self.AVAILABLE_VARIABLES for v in value):
            raise serializers.ValidationError(f'Variables must come from: {", ".join(sorted(self.AVAILABLE_VARIABLES))}.')
        return value

    def validate(self, attrs):
        import re

        body = attrs.get('body', getattr(self.instance, 'body', ''))
        variables = attrs.get('variables', getattr(self.instance, 'variables', []))
        placeholders = len(set(re.findall(r'\{\{(\d+)\}\}', body or '')))
        if placeholders != len(variables):
            raise serializers.ValidationError(
                {'variables': f'The body has {placeholders} placeholder(s) but {len(variables)} variable(s) are mapped.'}
            )
        return attrs


class WhatsAppMessageSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    company_name = serializers.SerializerMethodField()

    class Meta:
        model = WhatsAppMessage
        fields = [
            'id', 'company', 'company_name', 'event', 'to_number', 'recipient_name', 'recipient_type',
            'template_name', 'language_code', 'body', 'status', 'status_display', 'provider', 'provider_message_id',
            'error', 'attempts', 'sent_at', 'delivered_at', 'read_at', 'created_at',
        ]
        read_only_fields = fields

    def get_company_name(self, obj) -> str:
        return obj.company.name if obj.company else ''
