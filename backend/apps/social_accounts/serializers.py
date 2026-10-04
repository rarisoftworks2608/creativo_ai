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
    has_refresh_token = serializers.SerializerMethodField()
    profile = serializers.SerializerMethodField()

    class Meta:
        model = SocialAccount
        fields = [
            'id', 'company', 'platform', 'platform_display', 'account_name', 'account_id',
            'has_token', 'token_masked', 'token_expires_at', 'has_refresh_token', 'refresh_token_expires_at',
            'status', 'connection_method', 'scopes', 'profile', 'last_error', 'last_checked_at', 'notes',
            'connected_by', 'created_at', 'updated_at',
        ]
        read_only_fields = fields

    # Only display-safe metadata keys ever leave the server.
    PROFILE_KEYS = ('account_type', 'username', 'picture_url', 'followers_count', 'page_id', 'page_name', 'vanity_name', 'category')

    def get_profile(self, obj) -> dict:
        metadata = obj.metadata or {}
        return {key: metadata.get(key) for key in self.PROFILE_KEYS if metadata.get(key) not in (None, '')}

    def get_has_refresh_token(self, obj) -> bool:
        return bool(obj.refresh_token)

    def get_has_token(self, obj) -> bool:
        return bool(obj.access_token)

    def get_token_masked(self, obj) -> str:
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
        fields = ['id', 'platform', 'account_name', 'account_id', 'access_token', 'token_expires_at', 'notes', 'metadata']
        read_only_fields = ['id']

    def validate_metadata(self, value):
        if value in (None, ''):
            return {}
        if not isinstance(value, dict):
            raise serializers.ValidationError('metadata must be an object.')
        # Manual connections may set the IDs publishing needs (e.g. an Instagram account's
        # parent page_id, or a LinkedIn author urn) - nothing else.
        allowed = {'page_id', 'urn', 'account_type', 'username'}
        return {k: str(v) for k, v in value.items() if k in allowed and v not in (None, '')}

    def create(self, validated_data):
        raw_token = validated_data.pop('access_token', '')
        validated_data['access_token'] = encrypt_secret(raw_token)
        return super().create(validated_data)

    def update(self, instance, validated_data):
        if 'access_token' in validated_data:
            raw_token = validated_data.pop('access_token')
            if raw_token:
                instance.access_token = encrypt_secret(raw_token)
                instance.last_error = ''
                if instance.status in (SocialAccount.Status.EXPIRED, SocialAccount.Status.DISCONNECTED):
                    instance.status = SocialAccount.Status.CONNECTED
        if 'metadata' in validated_data:
            validated_data['metadata'] = {**(instance.metadata or {}), **validated_data['metadata']}
        return super().update(instance, validated_data)


class OAuthCompleteSerializer(serializers.Serializer):
    code = serializers.CharField()
    state = serializers.CharField()


class OAuthConnectSerializer(serializers.Serializer):
    keys = serializers.ListField(child=serializers.CharField(), allow_empty=False)
