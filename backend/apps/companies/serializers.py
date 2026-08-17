import secrets

from django.contrib.auth import password_validation
from rest_framework import serializers

from apps.authentication.models import User
from apps.authentication.serializers import UserSerializer

from .models import ClientProfile, Company


class CompanySerializer(serializers.ModelSerializer):
    """Read representation of a company, including its onboarding checklist."""

    onboarding = serializers.SerializerMethodField()
    client_count = serializers.IntegerField(source='clients.count', read_only=True)

    def get_onboarding(self, obj) -> dict:
        return obj.onboarding

    class Meta:
        model = Company
        fields = [
            'id', 'name', 'industry', 'description', 'website', 'status',
            'contact_email', 'contact_phone', 'address',
            'target_market', 'target_audience', 'products', 'services', 'usp', 'competitors',
            'onboarding', 'client_count', 'created_by', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'status', 'created_by', 'created_at', 'updated_at']


class CompanyWriteSerializer(serializers.ModelSerializer):
    """Used by an Admin to create or edit a company's business information."""

    class Meta:
        model = Company
        fields = [
            'id', 'name', 'industry', 'description', 'website',
            'contact_email', 'contact_phone', 'address',
            'target_market', 'target_audience', 'products', 'services', 'usp', 'competitors',
        ]
        read_only_fields = ['id']

    def create(self, validated_data):
        request = self.context.get('request')
        return Company.objects.create(created_by=getattr(request, 'user', None), **validated_data)


class ClientProfileUpdateSerializer(serializers.ModelSerializer):
    """Used by an Admin to edit a client's designation/primary-contact flag within a company."""

    class Meta:
        model = ClientProfile
        fields = ['designation', 'is_primary_contact']


class ClientProfileSerializer(serializers.ModelSerializer):
    """Read representation of a client's membership in a company."""

    user = UserSerializer(read_only=True)

    class Meta:
        model = ClientProfile
        fields = ['id', 'user', 'company', 'designation', 'is_primary_contact', 'created_at']
        read_only_fields = fields


class AddClientToCompanySerializer(serializers.Serializer):
    """Assigns a client to a company - either an existing standalone client login,
    or a brand-new one created on the spot (Epic 02: Create client / Assign client / Create login).
    """

    # Assign an existing client login
    user_id = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.filter(role=User.Role.CLIENT), required=False, source='user',
    )

    # Or create a new client login
    email = serializers.EmailField(required=False)
    first_name = serializers.CharField(required=False, allow_blank=True)
    last_name = serializers.CharField(required=False, allow_blank=True)
    phone_number = serializers.CharField(required=False, allow_blank=True)
    password = serializers.CharField(required=False, allow_blank=True, write_only=True)

    designation = serializers.CharField(required=False, allow_blank=True)
    is_primary_contact = serializers.BooleanField(required=False, default=False)

    generated_password = serializers.SerializerMethodField()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._plain_password = None

    def get_generated_password(self, obj) -> str | None:
        return self._plain_password

    def validate(self, attrs):
        has_existing_user = 'user' in attrs
        has_new_user_fields = bool(attrs.get('email'))

        if has_existing_user and has_new_user_fields:
            raise serializers.ValidationError('Provide either user_id or email, not both.')
        if not has_existing_user and not has_new_user_fields:
            raise serializers.ValidationError('Provide either user_id (existing client) or email (new client).')

        if has_existing_user and hasattr(attrs['user'], 'client_profile'):
            raise serializers.ValidationError('This client is already assigned to a company.')

        if has_new_user_fields and User.objects.filter(email__iexact=attrs['email']).exists():
            raise serializers.ValidationError({'email': 'A user with this email already exists.'})

        password = attrs.get('password')
        if password:
            password_validation.validate_password(password)

        return attrs

    def save(self, **kwargs):
        company = self.context['company']
        request = self.context.get('request')

        if 'user' in self.validated_data:
            user = self.validated_data['user']
        else:
            password = self.validated_data.get('password') or secrets.token_urlsafe(10)
            self._plain_password = password
            user = User(
                email=self.validated_data['email'],
                first_name=self.validated_data.get('first_name', ''),
                last_name=self.validated_data.get('last_name', ''),
                phone_number=self.validated_data.get('phone_number', ''),
                role=User.Role.CLIENT,
                created_by=getattr(request, 'user', None),
            )
            user.set_password(password)
            user.save()

        self.instance = ClientProfile.objects.create(
            user=user,
            company=company,
            designation=self.validated_data.get('designation', ''),
            is_primary_contact=self.validated_data.get('is_primary_contact', False),
        )
        return self.instance
