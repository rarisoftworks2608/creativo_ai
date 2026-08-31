import httpx
from django.http import Http404
from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.companies.models import Company
from common.crypto import decrypt_secret
from common.permissions import IsAdmin

from .models import SocialAccount
from .serializers import SocialAccountConnectSerializer, SocialAccountSerializer

# One lightweight "who am I" call per platform, used only to validate a stored
# token actually still works (Epic 10: Account information / Connection errors) -
# not a publishing call, so it needs no extra scopes beyond what a basic token grants.
PLATFORM_TEST_ENDPOINTS = {
    SocialAccount.Platform.INSTAGRAM: 'https://graph.facebook.com/v19.0/me',
    SocialAccount.Platform.FACEBOOK: 'https://graph.facebook.com/v19.0/me',
    SocialAccount.Platform.LINKEDIN: 'https://api.linkedin.com/v2/userinfo',
}
REQUEST_TIMEOUT_SECONDS = 15.0


class CompanyScopedMixin:
    """Resolves the company from the URL. Social account management is admin-only
    (Epic 10), but this still 404s a stray client the same way every other app's
    CompanyScopedMixin does, for consistent behavior across the API.
    """

    def get_company(self):
        company = generics.get_object_or_404(Company, pk=self.kwargs['company_id'])
        user = self.request.user
        if not user.is_admin:
            profile = getattr(user, 'client_profile', None)
            if not profile or profile.company_id != company.id:
                raise Http404
        return company


class SocialAccountListCreateView(CompanyScopedMixin, generics.ListCreateAPIView):
    """Admin: list a company's connected social accounts, or connect a new one
    by pasting in a manually-obtained access token (Epic 10: Connect).
    """

    permission_classes = [IsAdmin]

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return SocialAccountConnectSerializer
        return SocialAccountSerializer

    def get_queryset(self):
        return SocialAccount.objects.filter(company=self.get_company())

    def create(self, request, *args, **kwargs):
        company = self.get_company()
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        account = serializer.save(company=company, connected_by=request.user)
        return Response(SocialAccountSerializer(account).data, status=status.HTTP_201_CREATED)


class SocialAccountDetailView(CompanyScopedMixin, generics.RetrieveUpdateAPIView):
    """Admin: view or update (rename, relabel, paste a refreshed token) a connected
    social account (Epic 10: Token management).
    """

    permission_classes = [IsAdmin]

    def get_serializer_class(self):
        if self.request.method in ('PUT', 'PATCH'):
            return SocialAccountConnectSerializer
        return SocialAccountSerializer

    def get_queryset(self):
        return SocialAccount.objects.filter(company=self.get_company())

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=kwargs.get('partial', False))
        serializer.is_valid(raise_exception=True)
        account = serializer.save()
        return Response(SocialAccountSerializer(account).data)


class SocialAccountDisconnectView(CompanyScopedMixin, APIView):
    """Admin: disconnect a social account (Epic 10: Disconnect). The row is kept
    for history, with its token wiped, rather than hard-deleted.
    """

    permission_classes = [IsAdmin]
    serializer_class = SocialAccountSerializer

    def post(self, request, company_id, pk):
        company = self.get_company()
        account = generics.get_object_or_404(SocialAccount, pk=pk, company=company)

        account.status = SocialAccount.Status.DISCONNECTED
        account.access_token = ''
        account.save(update_fields=['status', 'access_token', 'updated_at'])

        return Response(SocialAccountSerializer(account).data)


class SocialAccountTestConnectionView(CompanyScopedMixin, APIView):
    """Admin: validate a connected account's stored token against the real platform
    (Epic 10: Account information / Connection errors). On success, refreshes
    account_name/account_id from the platform's own response and marks the account
    CONNECTED; on an auth failure marks it EXPIRED; any other error is reported
    without changing status.
    """

    permission_classes = [IsAdmin]
    serializer_class = SocialAccountSerializer

    def post(self, request, company_id, pk):
        company = self.get_company()
        account = generics.get_object_or_404(SocialAccount, pk=pk, company=company)

        token = decrypt_secret(account.access_token)
        if not token:
            return Response({'detail': 'No access token is stored for this account.'}, status=status.HTTP_400_BAD_REQUEST)

        endpoint = PLATFORM_TEST_ENDPOINTS[account.platform]
        try:
            if account.platform == SocialAccount.Platform.LINKEDIN:
                response = httpx.get(
                    endpoint, headers={'Authorization': f'Bearer {token}'}, timeout=REQUEST_TIMEOUT_SECONDS,
                )
            else:
                response = httpx.get(
                    endpoint, params={'fields': 'id,name', 'access_token': token}, timeout=REQUEST_TIMEOUT_SECONDS,
                )
        except httpx.HTTPError as exc:
            return Response(
                {'detail': f'Could not reach {account.get_platform_display()}: {exc}'},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        if response.status_code in (401, 403):
            account.status = SocialAccount.Status.EXPIRED
            account.save(update_fields=['status', 'updated_at'])
            return Response({
                'detail': 'This token was rejected by the platform - it has likely expired or been revoked.',
                'account': SocialAccountSerializer(account).data,
            })

        if response.status_code >= 400:
            return Response(
                {'detail': f'{account.get_platform_display()} returned an error: {response.text[:300]}'},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        data = response.json()
        account.account_name = data.get('name') or account.account_name
        account.account_id = str(data.get('id') or data.get('sub') or account.account_id)
        account.status = SocialAccount.Status.CONNECTED
        account.save(update_fields=['account_name', 'account_id', 'status', 'updated_at'])

        return Response({'detail': 'Connection is working.', 'account': SocialAccountSerializer(account).data})
