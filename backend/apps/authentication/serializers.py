import secrets

from django.contrib.auth import password_validation
from django.contrib.auth.tokens import default_token_generator
from django.core.exceptions import ValidationError as DjangoValidationError
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from .models import LoginHistory, User


class UserSerializer(serializers.ModelSerializer):
    """Read-only representation of a user, used for profile responses and admin listings."""

    full_name = serializers.CharField(source='get_full_name', read_only=True)

    class Meta:
        model = User
        fields = [
            'id', 'email', 'first_name', 'last_name', 'full_name', 'phone_number',
            'role', 'is_active', 'last_login', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'email', 'role', 'is_active', 'last_login', 'created_at', 'updated_at']


class ProfileUpdateSerializer(serializers.ModelSerializer):
    """Lets an authenticated user update their own profile fields."""

    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'phone_number']


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    """Adds user info to the token response and rejects inactive accounts."""

    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token['role'] = user.role
        token['email'] = user.email
        return token

    def validate(self, attrs):
        data = super().validate(attrs)
        if not self.user.is_active:
            raise serializers.ValidationError('This account has been deactivated.')
        data['user'] = UserSerializer(self.user).data
        return data


class CreateUserSerializer(serializers.ModelSerializer):
    """Used by an Admin to create a Client or (Epic 24: Team management) Admin login."""

    password = serializers.CharField(write_only=True, required=False, allow_blank=True)
    role = serializers.ChoiceField(choices=User.Role.choices, default=User.Role.CLIENT)
    generated_password = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ['id', 'email', 'first_name', 'last_name', 'phone_number', 'password', 'role', 'generated_password']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._plain_password = None

    def get_generated_password(self, obj) -> str | None:
        return self._plain_password

    def validate_password(self, value):
        if value:
            password_validation.validate_password(value)
        return value

    def create(self, validated_data):
        password = validated_data.pop('password', None) or secrets.token_urlsafe(10)
        self._plain_password = password
        request = self.context.get('request')
        user = User(
            created_by=getattr(request, 'user', None),
            **validated_data,
        )
        user.set_password(password)
        user.save()
        return user


class AdminUserUpdateSerializer(serializers.ModelSerializer):
    """Used by an Admin to edit a user's details, role, or active status."""

    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'phone_number', 'role', 'is_active']


class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True)

    def validate_old_password(self, value):
        user = self.context['request'].user
        if not user.check_password(value):
            raise serializers.ValidationError('Current password is incorrect.')
        return value

    def validate_new_password(self, value):
        user = self.context['request'].user
        try:
            password_validation.validate_password(value, user=user)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(list(exc.messages))
        return value

    def save(self, **kwargs):
        user = self.context['request'].user
        user.set_password(self.validated_data['new_password'])
        user.save(update_fields=['password'])
        return user


class ForgotPasswordSerializer(serializers.Serializer):
    email = serializers.EmailField()

    def get_user(self):
        return User.objects.filter(email__iexact=self.validated_data['email'], is_active=True).first()


class ResetPasswordSerializer(serializers.Serializer):
    uid = serializers.CharField()
    token = serializers.CharField()
    new_password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        try:
            user_id = force_str(urlsafe_base64_decode(attrs['uid']))
            user = User.objects.get(pk=user_id, is_active=True)
        except (User.DoesNotExist, ValueError, TypeError, OverflowError):
            raise serializers.ValidationError('Invalid or expired reset link.')

        if not default_token_generator.check_token(user, attrs['token']):
            raise serializers.ValidationError('Invalid or expired reset link.')

        try:
            password_validation.validate_password(attrs['new_password'], user=user)
        except DjangoValidationError as exc:
            raise serializers.ValidationError({'new_password': list(exc.messages)})

        attrs['user'] = user
        return attrs

    def save(self, **kwargs):
        user = self.validated_data['user']
        user.set_password(self.validated_data['new_password'])
        user.save(update_fields=['password'])
        return user


def build_uid_and_token(user):
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = default_token_generator.make_token(user)
    return uid, token


class RefreshTokenSerializer(serializers.Serializer):
    refresh = serializers.CharField()


class LoginHistorySerializer(serializers.ModelSerializer):
    class Meta:
        model = LoginHistory
        fields = ['id', 'user', 'email_attempted', 'ip_address', 'user_agent', 'was_successful', 'created_at']
        read_only_fields = fields
