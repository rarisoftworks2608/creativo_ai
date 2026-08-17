from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from common.permissions import IsAdmin

from .models import ClientProfile, Company
from .serializers import (
    AddClientToCompanySerializer,
    ClientProfileSerializer,
    ClientProfileUpdateSerializer,
    CompanySerializer,
    CompanyWriteSerializer,
)


class CompanyListCreateView(generics.ListCreateAPIView):
    """Admin: list all companies (with search/status filters) or create a new one."""

    permission_classes = [IsAdmin]

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return CompanyWriteSerializer
        return CompanySerializer

    def get_queryset(self):
        queryset = Company.objects.all()

        status_param = self.request.query_params.get('status')
        if status_param:
            queryset = queryset.filter(status=status_param)

        industry = self.request.query_params.get('industry')
        if industry:
            queryset = queryset.filter(industry__iexact=industry)

        search = self.request.query_params.get('search')
        if search:
            queryset = queryset.filter(name__icontains=search)

        return queryset


class CompanyDetailView(generics.RetrieveUpdateAPIView):
    """Admin: view/edit any company. Client: view their own company only (read-only)."""

    permission_classes = [IsAuthenticated]

    def get_serializer_class(self):
        if self.request.method in ('PUT', 'PATCH'):
            return CompanyWriteSerializer
        return CompanySerializer

    def get_queryset(self):
        user = self.request.user
        if user.is_admin:
            return Company.objects.all()
        return Company.objects.filter(clients__user=user)

    def check_permissions(self, request):
        super().check_permissions(request)
        if request.method not in ('GET', 'HEAD', 'OPTIONS') and not request.user.is_admin:
            self.permission_denied(request, message='Only admins can edit a company.')


class MyCompanyView(generics.RetrieveAPIView):
    """The authenticated client's own company (Epic 03: client's view of their company)."""

    serializer_class = CompanySerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        profile = getattr(self.request.user, 'client_profile', None)
        if profile is None:
            from rest_framework.exceptions import NotFound
            raise NotFound('No company is associated with this account.')
        return profile.company


class CompanyStatusView(APIView):
    """Admin: activate or deactivate a company."""

    permission_classes = [IsAdmin]
    serializer_class = CompanySerializer

    def post(self, request, pk, action):
        try:
            company = Company.objects.get(pk=pk)
        except Company.DoesNotExist:
            return Response({'detail': 'Company not found.'}, status=status.HTTP_404_NOT_FOUND)

        if action == 'activate':
            company.status = Company.Status.ACTIVE
        elif action == 'deactivate':
            company.status = Company.Status.INACTIVE
        else:
            return Response({'detail': 'Invalid action.'}, status=status.HTTP_400_BAD_REQUEST)

        company.save(update_fields=['status', 'updated_at'])
        return Response(CompanySerializer(company).data)


class CompanyClientListCreateView(generics.ListCreateAPIView):
    """Admin: list a company's clients, or add one (new login or existing client user)."""

    permission_classes = [IsAdmin]

    def get_queryset(self):
        return ClientProfile.objects.filter(company_id=self.kwargs['company_id'])

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return AddClientToCompanySerializer
        return ClientProfileSerializer

    def get_company(self):
        return generics.get_object_or_404(Company, pk=self.kwargs['company_id'])

    def create(self, request, *args, **kwargs):
        company = self.get_company()
        serializer = self.get_serializer(data=request.data, context={'request': request, 'company': company})
        serializer.is_valid(raise_exception=True)
        profile = serializer.save()
        return Response(
            {
                **ClientProfileSerializer(profile).data,
                'generated_password': serializer.data.get('generated_password'),
            },
            status=status.HTTP_201_CREATED,
        )


class CompanyClientDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Admin: view/update a client's role at the company, or remove them from it."""

    serializer_class = ClientProfileSerializer
    permission_classes = [IsAdmin]

    def get_queryset(self):
        return ClientProfile.objects.filter(company_id=self.kwargs['company_id'])

    def get_serializer_class(self):
        if self.request.method in ('PUT', 'PATCH'):
            return ClientProfileUpdateSerializer
        return ClientProfileSerializer
