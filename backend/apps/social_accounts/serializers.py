from rest_framework import serializers

from common.crypto import decrypt_secret, encrypt_secret

from .models import SocialAccount


class SocialAccountSerializer(serializers.ModelSerializer):
    """Read serializer - the raw token is never returned, only whether one is
    stored and a masked preview of its last 4 characters.
    """

    platform_display = serializers.CharField(source='get_platform_display', read_only=True)
    has_token = serializers.SerializerMethodField()
    token_masked = serializers.SerializerMethodField()

    class Meta:
        model = SocialAccount
        fields = [
            'id', 'company', 'platform', 'platform_display', 'account_name', 'account_id',
            'has_token', 'token_masked', 'token_expires_at', 'status', 'notes',
            'connected_by', 'created_at', 'updated_at',
        ]
        read_only_fields = fields

    def get_has_token(self, obj):
        return bool(obj.access_token)

    def get_token_masked(self, obj):
        if not obj.access_token:
            return ''
        plaintext = decrypt_secret(obj.access_token)
        if not plaintext:
            return ''
        return f'••••{plaintext[-4:]}' if len(plaintext) > 4 else '••••'


class SocialAccountConnectSerializer(serializers.ModelSerializer):
    """Write serializer for connecting a new account or updating an existing one
    (e.g. pasting a refreshed token). `access_token` is write-only and encrypted
    before it ever reaches the database.
    """

    access_token = serializers.CharField(write_only=True, required=False, allow_blank=True)

    class Meta:
        model = SocialAccount
        fields = ['id', 'platform', 'account_name', 'account_id', 'access_token', 'token_expires_at', 'notes']
        read_only_fields = ['id']

    def create(self, validated_data):
        raw_token = validated_data.pop('access_token', '')
        validated_data['access_token'] = encrypt_secret(raw_token)
        return super().create(validated_data)

    def update(self, instance, validated_data):
        if 'access_token' in validated_data:
            raw_token = validated_data.pop('access_token')
            if raw_token:
                instance.access_token = encrypt_secret(raw_token)
                if instance.status == SocialAccount.Status.EXPIRED:
                    instance.status = SocialAccount.Status.CONNECTED
        return super().update(instance, validated_data)
