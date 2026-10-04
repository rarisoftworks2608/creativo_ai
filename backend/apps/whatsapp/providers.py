"""WhatsApp sending backends (Epic 12: WhatsApp API).

- ConsoleProvider (default, WHATSAPP_PROVIDER=console): logs instead of sending, so the
  whole notification workflow can be developed and tested without a WhatsApp Business
  account - messages still appear in the delivery log as "sent".
- MetaCloudProvider (WHATSAPP_PROVIDER=meta): the official WhatsApp Business Cloud API.
  Business-initiated messages must use a pre-approved template.
"""

import logging
import re
import uuid

import httpx
from django.conf import settings

logger = logging.getLogger(__name__)

PHONE_RE = re.compile(r'^[1-9]\d{7,14}$')
TIMEOUT = 20.0
# Meta error codes worth retrying: rate limits / temporary errors.
TRANSIENT_CODES = {1, 2, 4, 80007, 130429, 131016, 131048, 131056, 133004}


class WhatsAppError(Exception):
    def __init__(self, message, *, retryable=False):
        super().__init__(message)
        self.retryable = retryable


def normalize_phone(raw):
    """'+91 98765-43210' -> '919876543210' (E.164 digits, no '+'). Returns '' if invalid."""
    digits = re.sub(r'\D', '', str(raw or ''))
    if digits.startswith('00'):
        digits = digits[2:]
    return digits if PHONE_RE.match(digits) else ''


def clean_parameter(value):
    """Template parameters can't contain newlines/tabs or 4+ consecutive spaces, and are
    limited in length - Meta rejects the whole message otherwise."""
    text = re.sub(r'[\r\n\t]+', ' ', str(value if value is not None else ''))
    text = re.sub(r' {4,}', '   ', text).strip()
    return (text or '-')[:1000]


class ConsoleProvider:
    name = 'console'

    def is_configured(self):
        return True

    def send_template(self, *, to, template_name, language_code, parameters):
        message_id = f'console-{uuid.uuid4().hex[:16]}'
        logger.info('[WhatsApp console] to=%s template=%s lang=%s params=%s', to, template_name, language_code, parameters)
        return message_id

    def send_text(self, *, to, body):
        message_id = f'console-{uuid.uuid4().hex[:16]}'
        logger.info('[WhatsApp console] to=%s text=%s', to, body)
        return message_id


class MetaCloudProvider:
    name = 'meta'

    def is_configured(self):
        return bool(settings.WHATSAPP_ACCESS_TOKEN and settings.WHATSAPP_PHONE_NUMBER_ID)

    def _url(self):
        return f'https://graph.facebook.com/{settings.WHATSAPP_API_VERSION}/{settings.WHATSAPP_PHONE_NUMBER_ID}/messages'

    def _post(self, payload):
        if not self.is_configured():
            raise WhatsAppError('WhatsApp Cloud API is not configured - set WHATSAPP_ACCESS_TOKEN and WHATSAPP_PHONE_NUMBER_ID.')
        try:
            response = httpx.post(
                self._url(), json=payload, timeout=TIMEOUT,
                headers={'Authorization': f'Bearer {settings.WHATSAPP_ACCESS_TOKEN}'},
            )
        except httpx.HTTPError as exc:
            raise WhatsAppError(f'Could not reach WhatsApp: {exc}', retryable=True) from exc
        if response.status_code >= 400:
            try:
                error = response.json().get('error') or {}
            except ValueError:
                error = {}
            code = error.get('code')
            detail = (error.get('error_data') or {}).get('details') or error.get('message') or response.text[:300]
            retryable = response.status_code >= 500 or response.status_code == 429 or code in TRANSIENT_CODES
            raise WhatsAppError(f'WhatsApp API error {code or response.status_code}: {detail}', retryable=retryable)
        messages = response.json().get('messages') or [{}]
        return messages[0].get('id', '')

    def send_template(self, *, to, template_name, language_code, parameters):
        template = {'name': template_name, 'language': {'code': language_code}}
        if parameters:
            template['components'] = [{
                'type': 'body',
                'parameters': [{'type': 'text', 'text': clean_parameter(p)} for p in parameters],
            }]
        return self._post({
            'messaging_product': 'whatsapp', 'recipient_type': 'individual', 'to': to,
            'type': 'template', 'template': template,
        })

    def send_text(self, *, to, body):
        """Free-form text - only delivered inside the 24h customer service window."""
        return self._post({
            'messaging_product': 'whatsapp', 'recipient_type': 'individual', 'to': to,
            'type': 'text', 'text': {'preview_url': True, 'body': body[:4096]},
        })

    def list_templates(self):
        if not (settings.WHATSAPP_ACCESS_TOKEN and settings.WHATSAPP_BUSINESS_ACCOUNT_ID):
            raise WhatsAppError('Set WHATSAPP_BUSINESS_ACCOUNT_ID and WHATSAPP_ACCESS_TOKEN to sync templates.')
        url = f'https://graph.facebook.com/{settings.WHATSAPP_API_VERSION}/{settings.WHATSAPP_BUSINESS_ACCOUNT_ID}/message_templates'
        templates, params = [], {'fields': 'name,status,language,category', 'limit': 200}
        headers = {'Authorization': f'Bearer {settings.WHATSAPP_ACCESS_TOKEN}'}
        while url:
            try:
                response = httpx.get(url, params=params, headers=headers, timeout=TIMEOUT)
            except httpx.HTTPError as exc:
                raise WhatsAppError(f'Could not reach WhatsApp: {exc}') from exc
            if response.status_code >= 400:
                raise WhatsAppError(f'WhatsApp API error: {response.text[:300]}')
            data = response.json()
            templates.extend(data.get('data', []))
            url = (data.get('paging') or {}).get('next')
            params = None
        return templates


def get_provider():
    if settings.WHATSAPP_PROVIDER == 'meta':
        return MetaCloudProvider()
    return ConsoleProvider()
