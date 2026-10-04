import httpx
from django.conf import settings
from django.db import transaction
from django.http import Http404
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema
from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.activity_log.models import ActivityLog
from apps.activity_log.services import log_activity
from apps.companies.models import Company
from common.crypto import decrypt_secret, encrypt_secret
from common.permissions import IsAdmin

from . import oauth
from .models import SocialAccount, SocialOAuthSession
from .serializers import (
    OAuthCompleteSerializer,
    OAuthConnectSerializer,
    SocialAccountConnectSerializer,
    SocialAccountSerializer,
)

REQUEST_TIMEOUT_SECONDS = 15.0


def _graph(path):
    return f'https://graph.facebook.com/{settings.META_GRAPH_API_VERSION}/{path}'


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
    by pasting in a manually-obtained access token (Epic 10: Connect - manual fallback;
    the OAuth flow below is the primary way to connect).
    """

    permission_classes = [IsAdmin]

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return SocialAccountConnectSerializer
        return SocialAccountSerializer

    def get_queryset(self):
        queryset = SocialAccount.objects.filter(company=self.get_company())
        platform = self.request.query_params.get('platform')
        if platform:
            queryset = queryset.filter(platform=platform)
        status_param = self.request.query_params.get('status')
        if status_param:
            queryset = queryset.filter(status=status_param)
        return queryset

    def create(self, request, *args, **kwargs):
        from apps.subscriptions.enforcement import check_social_account_limit

        company = self.get_company()
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        check_social_account_limit(company, serializer.validated_data['platform'])
        account = serializer.save(
            company=company, connected_by=request.user, connection_method=SocialAccount.ConnectionMethod.MANUAL,
        )
        log_activity(
            module=ActivityLog.Module.SOCIAL, action='Social account connected',
            description=f'{account.get_platform_display()} — {account.account_name}'.strip(' —'),
            company=company, request=request,
        )
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
        account.refresh_token = ''
        account.save(update_fields=['status', 'access_token', 'refresh_token', 'updated_at'])

        log_activity(
            module=ActivityLog.Module.SOCIAL, action='Social account disconnected',
            description=f'{account.get_platform_display()} — {account.account_name}'.strip(' —'),
            company=company, request=request,
        )

        return Response(SocialAccountSerializer(account).data)


class SocialAccountTestConnectionView(CompanyScopedMixin, APIView):
    """Admin: validate a connected account's stored token against the real platform
    (Epic 10: Account information / Connection errors). On success, refreshes
    account_name/account_id (and follower count / picture where the platform returns
    them) and marks the account CONNECTED; on an auth failure marks it EXPIRED; any other
    error is reported without changing status.
    """

    permission_classes = [IsAdmin]
    serializer_class = SocialAccountSerializer

    def post(self, request, company_id, pk):
        company = self.get_company()
        account = generics.get_object_or_404(SocialAccount, pk=pk, company=company)

        token = decrypt_secret(account.access_token)
        if not token:
            return Response({'detail': 'No access token is stored for this account.'}, status=status.HTTP_400_BAD_REQUEST)

        metadata = account.metadata or {}
        try:
            if account.platform == SocialAccount.Platform.LINKEDIN:
                if account.account_id and metadata.get('account_type') != 'person':
                    response = httpx.get(
                        f'{oauth.LINKEDIN_API}/rest/organizations/{account.account_id}',
                        headers=oauth.linkedin_headers(token), timeout=REQUEST_TIMEOUT_SECONDS,
                    )
                else:
                    response = httpx.get(
                        f'{oauth.LINKEDIN_API}/v2/userinfo', headers={'Authorization': f'Bearer {token}'},
                        timeout=REQUEST_TIMEOUT_SECONDS,
                    )
            elif account.platform == SocialAccount.Platform.INSTAGRAM and account.account_id:
                response = httpx.get(
                    _graph(account.account_id),
                    params={'fields': 'id,username,name,followers_count,profile_picture_url', 'access_token': token},
                    timeout=REQUEST_TIMEOUT_SECONDS,
                )
            elif account.platform == SocialAccount.Platform.FACEBOOK and account.account_id:
                response = httpx.get(
                    _graph(account.account_id),
                    params={'fields': 'id,name,followers_count,fan_count', 'access_token': token},
                    timeout=REQUEST_TIMEOUT_SECONDS,
                )
            else:
                response = httpx.get(
                    _graph('me'), params={'fields': 'id,name', 'access_token': token}, timeout=REQUEST_TIMEOUT_SECONDS,
                )
        except httpx.HTTPError as exc:
            return Response(
                {'detail': f'Could not reach {account.get_platform_display()}: {exc}'},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        account.last_checked_at = timezone.now()

        if response.status_code in (401, 403):
            account.status = SocialAccount.Status.EXPIRED
            account.last_error = 'Token rejected by the platform (expired or revoked).'
            account.save(update_fields=['status', 'last_error', 'last_checked_at', 'updated_at'])
            return Response({
                'detail': 'This token was rejected by the platform - it has likely expired or been revoked.',
                'account': SocialAccountSerializer(account).data,
            })

        if response.status_code >= 400:
            account.last_error = response.text[:500]
            account.save(update_fields=['last_error', 'last_checked_at', 'updated_at'])
            return Response(
                {'detail': f'{account.get_platform_display()} returned an error: {response.text[:300]}'},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        data = response.json()
        account.account_name = (
            data.get('name') or data.get('localizedName') or data.get('username') or account.account_name
        )
        account.account_id = str(data.get('id') or data.get('sub') or account.account_id)
        followers = data.get('followers_count') or data.get('fan_count')
        if followers is not None:
            metadata['followers_count'] = followers
        if data.get('profile_picture_url'):
            metadata['picture_url'] = data['profile_picture_url']
        if data.get('username'):
            metadata['username'] = data['username']
        account.metadata = metadata
        account.status = SocialAccount.Status.CONNECTED
        account.last_error = ''
        account.save(update_fields=[
            'account_name', 'account_id', 'metadata', 'status', 'last_error', 'last_checked_at', 'updated_at',
        ])

        return Response({'detail': 'Connection is working.', 'account': SocialAccountSerializer(account).data})


class SocialAccountRefreshTokenView(CompanyScopedMixin, APIView):
    """Admin: refresh an OAuth token now (Epic 10: Token refresh). LinkedIn tokens with
    a refresh token are renewed in place; Meta Page tokens don't expire, so a Meta
    account that stops working has to be reconnected through "Connect with Facebook"."""

    permission_classes = [IsAdmin]
    serializer_class = SocialAccountSerializer

    def post(self, request, company_id, pk):
        from .tasks import refresh_account_token

        company = self.get_company()
        account = generics.get_object_or_404(SocialAccount, pk=pk, company=company)
        if account.platform != SocialAccount.Platform.LINKEDIN or not account.refresh_token:
            return Response(
                {'detail': 'This account has no refresh token - reconnect it with the OAuth button to get a fresh token.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            refresh_account_token(account)
        except oauth.OAuthError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_502_BAD_GATEWAY)
        account.refresh_from_db()
        log_activity(
            module=ActivityLog.Module.SOCIAL, action='Social token refreshed',
            description=account.account_name, company=company, request=request,
        )
        return Response({'detail': 'Token refreshed.', 'account': SocialAccountSerializer(account).data})


# ---------------------------------------------------------------- OAuth

class OAuthStatusView(APIView):
    """Admin: which OAuth providers are configured, and the exact redirect URIs that
    must be registered in the Meta / LinkedIn developer apps."""

    permission_classes = [IsAdmin]

    @extend_schema(responses=OpenApiTypes.OBJECT)
    def get(self, request, company_id=None):
        return Response(oauth.provider_status())


class OAuthStartView(CompanyScopedMixin, APIView):
    """Admin: get the provider's authorization URL to redirect the browser to."""

    permission_classes = [IsAdmin]

    @extend_schema(responses=OpenApiTypes.OBJECT)
    def get(self, request, company_id, provider):
        company = self.get_company()
        state = oauth.build_state(company_id=company.id, user_id=request.user.id, provider=provider)
        try:
            if provider == 'meta':
                url = oauth.meta_authorization_url(state)
            elif provider == 'linkedin':
                url = oauth.linkedin_authorization_url(state)
            else:
                return Response({'detail': 'Unknown provider.'}, status=status.HTTP_404_NOT_FOUND)
        except oauth.OAuthError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response({'authorization_url': url, 'redirect_uri': oauth.redirect_uri(provider)})


class OAuthCompleteView(CompanyScopedMixin, APIView):
    """Admin: exchange the code the provider redirected back with for tokens, and list
    every account the login can manage so the admin can pick which to connect."""

    permission_classes = [IsAdmin]
    serializer_class = OAuthCompleteSerializer

    def post(self, request, company_id, provider):
        company = self.get_company()
        serializer = OAuthCompleteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        code, state = serializer.validated_data['code'], serializer.validated_data['state']

        try:
            oauth.parse_state(state, provider=provider, company_id=company.id, user_id=request.user.id)
            if provider == 'meta':
                user_token, user_token_expires_at = oauth.meta_exchange_code(code)
                candidates, warnings = oauth.meta_discover_accounts(user_token, user_token_expires_at)
                scopes = oauth.meta_granted_scopes(user_token)
                for candidate in candidates:
                    candidate['scopes'] = scopes
                missing = [s for s in ('pages_manage_posts', 'instagram_content_publish') if scopes and s not in scopes]
                if missing:
                    warnings.append(f'These permissions were not granted, so publishing will fail: {", ".join(missing)}.')
            elif provider == 'linkedin':
                tokens = oauth.linkedin_exchange_code(code)
                candidates, warnings = oauth.linkedin_discover_accounts(tokens)
            else:
                return Response({'detail': 'Unknown provider.'}, status=status.HTTP_404_NOT_FOUND)
        except oauth.OAuthError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        session = SocialOAuthSession.objects.create(
            company=company, provider=provider, payload=oauth.encrypt_payload(candidates),
            created_by=request.user, expires_at=timezone.now() + oauth.SESSION_LIFETIME,
        )
        existing = set(
            SocialAccount.objects.filter(company=company).exclude(status=SocialAccount.Status.DISCONNECTED)
            .values_list('platform', 'account_id')
        )
        public = oauth.public_candidates(candidates)
        for candidate in public:
            candidate['already_connected'] = (candidate['platform'], candidate['account_id']) in existing

        return Response({'session_id': str(session.id), 'provider': provider, 'candidates': public, 'warnings': warnings})


class OAuthConnectView(CompanyScopedMixin, APIView):
    """Admin: connect the picked accounts from a completed OAuth session."""

    permission_classes = [IsAdmin]
    serializer_class = OAuthConnectSerializer

    def post(self, request, company_id, session_id):
        from apps.subscriptions.enforcement import check_social_account_limit

        company = self.get_company()
        session = generics.get_object_or_404(SocialOAuthSession, pk=session_id, company=company)
        if session.consumed_at or session.expires_at < timezone.now():
            return Response({'detail': 'This connection session has expired - please log in again.'}, status=status.HTTP_400_BAD_REQUEST)

        serializer = OAuthConnectSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        wanted = set(serializer.validated_data['keys'])
        candidates = [c for c in oauth.decrypt_payload(session.payload) if c['key'] in wanted]
        if not candidates:
            return Response({'detail': 'Select at least one account to connect.'}, status=status.HTTP_400_BAD_REQUEST)

        connected = []
        with transaction.atomic():
            for candidate in candidates:
                account = SocialAccount.objects.filter(
                    company=company, platform=candidate['platform'], account_id=candidate['account_id'],
                ).first()
                if account is None:
                    check_social_account_limit(company, candidate['platform'])
                    account = SocialAccount(company=company, platform=candidate['platform'], account_id=candidate['account_id'])
                account.account_name = candidate.get('name') or account.account_name or candidate['account_id']
                account.access_token = encrypt_secret(candidate.get('token', ''))
                account.refresh_token = encrypt_secret(candidate.get('refresh_token', '')) if candidate.get('refresh_token') else ''
                account.token_expires_at = parse_datetime(candidate['token_expires_at']) if candidate.get('token_expires_at') else None
                account.refresh_token_expires_at = (
                    parse_datetime(candidate['refresh_token_expires_at']) if candidate.get('refresh_token_expires_at') else None
                )
                account.scopes = candidate.get('scopes', [])
                account.metadata = {**(account.metadata or {}), **(candidate.get('metadata') or {})}
                account.status = SocialAccount.Status.CONNECTED
                account.connection_method = SocialAccount.ConnectionMethod.OAUTH
                account.last_error = ''
                account.last_checked_at = timezone.now()
                account.connected_by = request.user
                account.save()
                connected.append(account)

            session.consumed_at = timezone.now()
            session.payload = ''
            session.save(update_fields=['consumed_at', 'payload'])

        for account in connected:
            log_activity(
                module=ActivityLog.Module.SOCIAL, action='Social account connected (OAuth)',
                description=f'{account.get_platform_display()} — {account.account_name}', company=company, request=request,
            )
        return Response({'connected': SocialAccountSerializer(connected, many=True).data}, status=status.HTTP_201_CREATED)
