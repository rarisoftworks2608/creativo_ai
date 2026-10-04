"""WhatsApp notification dispatch (Epic 12 / Epic 13: WhatsApp channel).

Other apps call `dispatch_event(company, event, context)` at workflow moments (content
ready, approved, published, ...). Nothing is sent unless the company's WhatsApp config is
enabled and the event is switched on; every attempted message is logged.
"""

from django.conf import settings

from .models import EVENT_AUDIENCE, Event, WhatsAppConfig, WhatsAppMessage, WhatsAppTemplate
from .providers import normalize_phone


def get_config(company):
    config, _ = WhatsAppConfig.objects.get_or_create(company=company)
    return config


def recipients_for(config, event=None):
    """[{name, phone, type}] for an event, de-duplicated by phone number."""
    audience = EVENT_AUDIENCE.get(event, 'all') if event else 'all'
    people = []
    if audience in ('all', 'clients'):
        people += [{'name': n.get('name', ''), 'phone': n.get('phone', ''), 'type': 'client'} for n in config.client_numbers or []]
        if config.include_client_users:
            for profile in config.company.clients.select_related('user'):
                user = profile.user
                if user.is_active and user.whatsapp_notifications_enabled and user.phone_number:
                    people.append({'name': user.get_full_name(), 'phone': user.phone_number, 'type': 'user'})
    if audience in ('all', 'internal'):
        people += [{'name': n.get('name', ''), 'phone': n.get('phone', ''), 'type': 'internal'} for n in config.internal_numbers or []]

    seen, result = set(), []
    for person in people:
        phone = normalize_phone(person['phone'])
        if phone and phone not in seen:
            seen.add(phone)
            result.append({**person, 'phone': phone})
    return result


def template_for(event, language_code):
    templates = WhatsAppTemplate.objects.filter(event=event, is_active=True)
    base = (language_code or 'en').split('_')[0]
    return (
        templates.filter(language_code=language_code).first()
        or templates.filter(language_code__startswith=base).first()
        or templates.filter(language_code__startswith='en').first()
        or templates.first()
    )


def _absolute_link(url):
    if not url:
        return settings.FRONTEND_URL
    if url.startswith(('http://', 'https://')):
        return url
    return f'{settings.FRONTEND_URL.rstrip("/")}/{url.lstrip("/")}'


def build_parameters(template, company, context):
    values = {**context, 'company_name': company.name, 'link': _absolute_link(context.get('url', ''))}
    return [str(values.get(key, '') or '-') for key in template.variables or []]


def dispatch_event(company, event, context=None, *, actor=None):
    """Queues one message per recipient. Returns the created WhatsAppMessage rows."""
    context = context or {}
    config = WhatsAppConfig.objects.filter(company=company).select_related('company').first()
    if config is None or not config.is_enabled or event not in (config.enabled_events or []):
        return []
    recipients = recipients_for(config, event)
    if not recipients:
        return []

    template = template_for(event, config.language_code)
    messages = []
    for person in recipients:
        message = WhatsAppMessage(
            company=company, event=event, to_number=person['phone'], recipient_name=person['name'][:150],
            recipient_type=person['type'], created_by=actor,
        )
        if template is None:
            message.status = WhatsAppMessage.Status.SKIPPED
            message.error = f'No active WhatsApp template is mapped to "{Event(event).label}".'
            message.save()
            messages.append(message)
            continue
        parameters = build_parameters(template, company, context)
        message.template_name = template.name
        message.language_code = template.language_code
        message.variables = parameters
        message.body = template.render(parameters)
        message.save()
        messages.append(message)

    from .tasks import send_whatsapp_message

    for message in messages:
        if message.status == WhatsAppMessage.Status.QUEUED:
            send_whatsapp_message.delay(message.id)
    return messages


def send_test_message(company, phone, actor=None):
    """Sends Meta's built-in `hello_world` (en_US) template, which exists in every
    WhatsApp Business account - the quickest end-to-end check that credentials work."""
    to = normalize_phone(phone)
    if not to:
        raise ValueError('Enter a valid phone number with country code, e.g. +919876543210.')
    message = WhatsAppMessage.objects.create(
        company=company, event='test', to_number=to, recipient_name='Test', recipient_type='test',
        template_name='hello_world', language_code='en_US', body='Hello World (WhatsApp test template)',
        created_by=actor,
    )
    from .tasks import send_whatsapp_message

    send_whatsapp_message.delay(message.id)
    return message
