"""WhatsApp sending queue (Epic 12; Epic 23: Notifications jobs)."""

import datetime
import logging

from celery import shared_task
from django.utils import timezone

from .models import WhatsAppMessage
from .providers import WhatsAppError, get_provider

logger = logging.getLogger(__name__)

MAX_ATTEMPTS = 3


@shared_task(bind=True, max_retries=MAX_ATTEMPTS - 1)
def send_whatsapp_message(self, message_id):
    message = WhatsAppMessage.objects.filter(pk=message_id).first()
    if message is None or message.status not in (WhatsAppMessage.Status.QUEUED, WhatsAppMessage.Status.FAILED):
        return None

    provider = get_provider()
    message.attempts += 1
    message.provider = provider.name
    try:
        provider_id = provider.send_template(
            to=message.to_number, template_name=message.template_name,
            language_code=message.language_code or 'en', parameters=message.variables or [],
        )
    except WhatsAppError as exc:
        message.error = str(exc)[:2000]
        if exc.retryable and message.attempts < MAX_ATTEMPTS:
            message.status = WhatsAppMessage.Status.QUEUED
            message.save(update_fields=['attempts', 'provider', 'error', 'status', 'updated_at'])
            raise self.retry(countdown=30 * message.attempts, exc=exc) from exc
        message.status = WhatsAppMessage.Status.FAILED
        message.save(update_fields=['attempts', 'provider', 'error', 'status', 'updated_at'])
        logger.warning('WhatsApp message %s failed: %s', message.id, exc)
        return None

    message.provider_message_id = provider_id or ''
    message.status = WhatsAppMessage.Status.SENT
    message.sent_at = timezone.now()
    message.error = ''
    message.save(update_fields=['attempts', 'provider', 'provider_message_id', 'status', 'sent_at', 'error', 'updated_at'])
    return provider_id


STATUS_ORDER = {'queued': 0, 'sent': 1, 'delivered': 2, 'read': 3}


def apply_status_update(status_payload):
    """Applies one `statuses[]` entry from a WhatsApp webhook (sent/delivered/read/failed)."""
    provider_id = status_payload.get('id')
    new_status = status_payload.get('status')
    if not provider_id or not new_status:
        return False
    message = WhatsAppMessage.objects.filter(provider_message_id=provider_id).first()
    if message is None:
        return False

    timestamp = status_payload.get('timestamp')
    when = timezone.now()
    if timestamp:
        try:
            when = datetime.datetime.fromtimestamp(int(timestamp), tz=datetime.timezone.utc)
        except (TypeError, ValueError):
            pass

    fields = ['updated_at']
    if new_status == 'failed':
        errors = status_payload.get('errors') or [{}]
        message.status = WhatsAppMessage.Status.FAILED
        message.error = (errors[0].get('error_data') or {}).get('details') or errors[0].get('title') or 'Delivery failed'
        fields += ['status', 'error']
    elif STATUS_ORDER.get(new_status, -1) > STATUS_ORDER.get(message.status, -1):
        message.status = new_status
        fields.append('status')
        if new_status == 'delivered':
            message.delivered_at = when
            fields.append('delivered_at')
        elif new_status == 'read':
            message.read_at = when
            fields.append('read_at')
            if not message.delivered_at:
                message.delivered_at = when
                fields.append('delivered_at')
    message.save(update_fields=fields)
    return True
