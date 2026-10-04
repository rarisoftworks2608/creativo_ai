"""Health checks (Epic 26: Monitoring - server, Celery, database monitoring).

GET /api/v1/health/          public liveness/readiness probe (Docker, load balancer, uptime monitor)
GET /api/v1/health/details/  admin-only: every dependency + integration configuration
"""

import time

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.db import connection
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from common.permissions import IsAdmin


def _check_database():
    started = time.monotonic()
    try:
        with connection.cursor() as cursor:
            cursor.execute('SELECT 1')
            cursor.fetchone()
    except Exception as exc:  # noqa: BLE001
        return {'ok': False, 'error': str(exc)[:200]}
    return {'ok': True, 'vendor': connection.vendor, 'latency_ms': round((time.monotonic() - started) * 1000, 1)}


def _check_redis():
    try:
        import redis

        client = redis.Redis.from_url(settings.CELERY_BROKER_URL, socket_connect_timeout=2, socket_timeout=2)
        started = time.monotonic()
        client.ping()
        return {'ok': True, 'latency_ms': round((time.monotonic() - started) * 1000, 1)}
    except Exception as exc:  # noqa: BLE001
        return {'ok': False, 'error': str(exc)[:200]}


def _check_celery():
    try:
        from config.celery import app

        replies = app.control.inspect(timeout=1.5).ping() or {}
    except Exception as exc:  # noqa: BLE001
        return {'ok': False, 'workers': [], 'error': str(exc)[:200]}
    return {'ok': bool(replies), 'workers': sorted(replies.keys())}


def _check_storage():
    name = f'healthcheck/{int(time.time())}.txt'
    try:
        saved = default_storage.save(name, ContentFile(b'ok'))
        default_storage.delete(saved)
        return {'ok': True, 'backend': default_storage.__class__.__name__}
    except Exception as exc:  # noqa: BLE001
        return {'ok': False, 'backend': default_storage.__class__.__name__, 'error': str(exc)[:200]}


def _check_ffmpeg():
    from apps.video_generation.rendering import find_ffmpeg

    path = find_ffmpeg()
    return {'ok': bool(path), 'path': path or '', 'note': '' if path else 'Video rendering needs FFmpeg (see README).'}


class HealthView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = []

    @extend_schema(responses=OpenApiTypes.OBJECT)
    def get(self, request):
        database = _check_database()
        payload = {'status': 'ok' if database['ok'] else 'error', 'database': database['ok']}
        return Response(payload, status=200 if database['ok'] else 503)


class HealthDetailsView(APIView):
    permission_classes = [IsAdmin]

    @extend_schema(responses=OpenApiTypes.OBJECT)
    def get(self, request):
        from apps.social_accounts.oauth import provider_status
        from apps.whatsapp.providers import get_provider as get_whatsapp_provider
        from common.ai_config import credentials_status, get_model_name, get_provider_name

        checks = {
            'database': _check_database(),
            'redis': _check_redis(),
            'celery': _check_celery(),
            'storage': _check_storage(),
            'ffmpeg': _check_ffmpeg(),
        }
        whatsapp = get_whatsapp_provider()
        return Response({
            'status': 'ok' if all(c['ok'] for c in checks.values()) else 'degraded',
            'checks': checks,
            'ai': {
                kind: {'provider': get_provider_name(kind), 'model': get_model_name(kind)}
                for kind in ('text', 'image', 'video')
            },
            'ai_credentials': credentials_status(),
            'social_oauth': provider_status(),
            'whatsapp': {'provider': whatsapp.name, 'configured': whatsapp.is_configured()},
            'public_media_base_url': settings.PUBLIC_MEDIA_BASE_URL or f'{settings.BACKEND_PUBLIC_URL}{settings.MEDIA_URL}',
            'debug': settings.DEBUG,
        })
