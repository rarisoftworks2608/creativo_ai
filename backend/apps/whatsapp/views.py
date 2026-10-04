import hashlib
import hmac
import json
import logging

from django.conf import settings
from django.http import HttpResponse
from django.utils import timezone
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema
from rest_framework import generics, status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.activity_log.models import ActivityLog
from apps.activity_log.services import log_activity
from common.mixins import CompanyScopedMixin
from common.permissions import IsAdmin

from .models import WhatsAppConfig, WhatsAppMessage, WhatsAppTemplate
from .providers import WhatsAppError, get_provider
from .serializers import WhatsAppConfigSerializer, WhatsAppMessageSerializer, WhatsAppTemplateSerializer
from .services import get_config, send_test_message
from .tasks import apply_status_update, send_whatsapp_message

logger = logging.getLogger(__name__)


class WhatsAppConfigView(CompanyScopedMixin, APIView):
    """Admin: a company's WhatsApp configuration + notification group (Epic 12)."""

    permission_classes = [IsAdmin]
    serializer_class = WhatsAppConfigSerializer

    def get(self, request, company_id):
        config = get_config(self.get_company())
        return Response(WhatsAppConfigSerializer(config).data)

    def patch(self, request, company_id):
        company = self.get_company()
        config = get_config(company)
        serializer = WhatsAppConfigSerializer(config, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        config = serializer.save()
        log_activity(module=ActivityLog.Module.WHATSAPP, action='WhatsApp settings updated',
                     description=company.name, company=company, request=request)
        return Response(WhatsAppConfigSerializer(config).data)


class WhatsAppGroupView(CompanyScopedMixin, APIView):
    """Admin: create (activate) or deactivate the company's notification group - the
    client numbers + internal numbers that receive this company's WhatsApp updates."""

    permission_classes = [IsAdmin]
    serializer_class = WhatsAppConfigSerializer

    def post(self, request, company_id):
        company = self.get_company()
        config = get_config(company)
        name = (request.data.get('group_name') or config.group_name or f'{company.name} × Marketing').strip()
        if not (config.client_numbers or config.internal_numbers or config.include_client_users):
            return Response({'detail': 'Add at least one client or internal number before creating the group.'},
                            status=status.HTTP_400_BAD_REQUEST)
        config.group_name = name[:120]
        if 'group_description' in request.data:
            config.group_description = request.data.get('group_description') or ''
        if 'group_invite_link' in request.data:
            config.group_invite_link = request.data.get('group_invite_link') or ''
        config.group_status = WhatsAppConfig.GroupStatus.ACTIVE
        config.group_created_at = config.group_created_at or timezone.now()
        config.is_enabled = True
        config.save()
        log_activity(module=ActivityLog.Module.WHATSAPP, action='WhatsApp group created',
                     description=config.group_name, company=company, request=request)
        return Response(WhatsAppConfigSerializer(config).data)

    def delete(self, request, company_id):
        company = self.get_company()
        config = get_config(company)
        config.group_status = WhatsAppConfig.GroupStatus.INACTIVE
        config.is_enabled = False
        config.save(update_fields=['group_status', 'is_enabled', 'updated_at'])
        log_activity(module=ActivityLog.Module.WHATSAPP, action='WhatsApp group deactivated',
                     description=config.group_name, company=company, request=request)
        return Response(WhatsAppConfigSerializer(config).data)


class WhatsAppMessageListView(CompanyScopedMixin, generics.ListAPIView):
    """Admin: delivery log for one company."""

    serializer_class = WhatsAppMessageSerializer
    permission_classes = [IsAdmin]

    def get_queryset(self):
        queryset = WhatsAppMessage.objects.filter(company=self.get_company())
        if self.request.query_params.get('status'):
            queryset = queryset.filter(status=self.request.query_params['status'])
        if self.request.query_params.get('event'):
            queryset = queryset.filter(event=self.request.query_params['event'])
        return queryset


class WhatsAppResendView(CompanyScopedMixin, APIView):
    permission_classes = [IsAdmin]

    @extend_schema(responses=OpenApiTypes.OBJECT, request=OpenApiTypes.OBJECT)
    def post(self, request, company_id, pk):
        message = generics.get_object_or_404(WhatsAppMessage, pk=pk, company=self.get_company())
        if message.status not in (WhatsAppMessage.Status.FAILED, WhatsAppMessage.Status.SKIPPED):
            return Response({'detail': 'Only failed or skipped messages can be resent.'}, status=status.HTTP_400_BAD_REQUEST)
        if not message.template_name:
            return Response({'detail': 'This message has no template - map one under WhatsApp templates first.'},
                            status=status.HTTP_400_BAD_REQUEST)
        message.status = WhatsAppMessage.Status.QUEUED
        message.attempts = 0
        message.error = ''
        message.save(update_fields=['status', 'attempts', 'error', 'updated_at'])
        send_whatsapp_message.delay(message.id)
        message.refresh_from_db()
        return Response(WhatsAppMessageSerializer(message).data)


class WhatsAppTestMessageView(CompanyScopedMixin, APIView):
    permission_classes = [IsAdmin]

    @extend_schema(responses=OpenApiTypes.OBJECT, request=OpenApiTypes.OBJECT)
    def post(self, request, company_id):
        company = self.get_company()
        try:
            message = send_test_message(company, request.data.get('phone', ''), actor=request.user)
        except ValueError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        message.refresh_from_db()
        return Response(WhatsAppMessageSerializer(message).data, status=status.HTTP_201_CREATED)


# ---------------------------------------------------------------- platform-wide

class WhatsAppStatusView(APIView):
    """Admin: is the WhatsApp Cloud API configured, and what's the webhook URL."""

    permission_classes = [IsAdmin]

    @extend_schema(responses=OpenApiTypes.OBJECT)
    def get(self, request):
        provider = get_provider()
        last_week = timezone.now() - timezone.timedelta(days=7)
        recent = WhatsAppMessage.objects.filter(created_at__gte=last_week)
        return Response({
            'provider': provider.name,
            'configured': provider.is_configured(),
            'is_console': provider.name == 'console',
            'phone_number_id_set': bool(settings.WHATSAPP_PHONE_NUMBER_ID),
            'business_account_id_set': bool(settings.WHATSAPP_BUSINESS_ACCOUNT_ID),
            'access_token_set': bool(settings.WHATSAPP_ACCESS_TOKEN),
            'webhook_verify_token_set': bool(settings.WHATSAPP_WEBHOOK_VERIFY_TOKEN),
            'webhook_url': f'{settings.BACKEND_PUBLIC_URL.rstrip("/")}/api/v1/whatsapp/webhook/',
            'api_version': settings.WHATSAPP_API_VERSION,
            'last_7_days': {
                key: recent.filter(status=key).count() for key in ('sent', 'delivered', 'read', 'failed', 'skipped')
            },
        })


class WhatsAppTemplateListCreateView(generics.ListCreateAPIView):
    serializer_class = WhatsAppTemplateSerializer
    permission_classes = [IsAdmin]
    pagination_class = None
    queryset = WhatsAppTemplate.objects.all()


class WhatsAppTemplateDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = WhatsAppTemplateSerializer
    permission_classes = [IsAdmin]
    queryset = WhatsAppTemplate.objects.all()


class WhatsAppTemplateSyncView(APIView):
    """Admin: pull each mapped template's review status from WhatsApp Manager."""

    permission_classes = [IsAdmin]

    @extend_schema(responses=OpenApiTypes.OBJECT, request=OpenApiTypes.OBJECT)
    def post(self, request):
        provider = get_provider()
        if provider.name != 'meta':
            return Response({'detail': 'Template sync needs WHATSAPP_PROVIDER=meta and the WhatsApp Cloud API credentials.'},
                            status=status.HTTP_400_BAD_REQUEST)
        try:
            remote = provider.list_templates()
        except WhatsAppError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_502_BAD_GATEWAY)
        index = {(t.get('name'), t.get('language')): (t.get('status') or '').lower() for t in remote}
        now = timezone.now()
        for template in WhatsAppTemplate.objects.all():
            remote_status = index.get((template.name, template.language_code))
            template.meta_status = (
                remote_status if remote_status in WhatsAppTemplate.MetaStatus.values else
                WhatsAppTemplate.MetaStatus.MISSING if remote_status is None else WhatsAppTemplate.MetaStatus.UNKNOWN
            )
            template.last_synced_at = now
            template.save(update_fields=['meta_status', 'last_synced_at', 'updated_at'])
        return Response(WhatsAppTemplateSerializer(WhatsAppTemplate.objects.all(), many=True).data)


class WhatsAppWebhookView(APIView):
    """Public webhook for WhatsApp delivery receipts (sent/delivered/read/failed).

    GET  - Meta's one-time verification handshake (hub.verify_token must match
           WHATSAPP_WEBHOOK_VERIFY_TOKEN).
    POST - status updates, authenticated by the X-Hub-Signature-256 HMAC of the body
           with the app secret.
    """

    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = []

    @extend_schema(responses=OpenApiTypes.OBJECT)
    def get(self, request):
        mode = request.query_params.get('hub.mode')
        token = request.query_params.get('hub.verify_token')
        challenge = request.query_params.get('hub.challenge', '')
        expected = settings.WHATSAPP_WEBHOOK_VERIFY_TOKEN
        if mode == 'subscribe' and expected and hmac.compare_digest(token or '', expected):
            return HttpResponse(challenge, content_type='text/plain')
        return HttpResponse('Verification failed', status=403)

    @extend_schema(responses=OpenApiTypes.OBJECT, request=OpenApiTypes.OBJECT)
    def post(self, request):
        secret = settings.WHATSAPP_APP_SECRET
        if secret:
            signature = request.headers.get('X-Hub-Signature-256', '')
            digest = 'sha256=' + hmac.new(secret.encode(), request.body, hashlib.sha256).hexdigest()
            if not hmac.compare_digest(signature, digest):
                return HttpResponse('Invalid signature', status=403)
        try:
            payload = json.loads(request.body or b'{}')
        except json.JSONDecodeError:
            return HttpResponse('Bad payload', status=400)

        updated = 0
        for entry in payload.get('entry', []):
            for change in entry.get('changes', []):
                for status_payload in (change.get('value') or {}).get('statuses', []):
                    updated += apply_status_update(status_payload)
        return Response({'updated': updated})
