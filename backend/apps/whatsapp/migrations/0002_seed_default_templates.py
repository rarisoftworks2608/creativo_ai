from django.db import migrations

# One template per workflow event. Create templates with exactly these names, language
# "English" (code `en`), category Utility and these bodies in WhatsApp Manager (see
# docs/meta-setup-guide.md, part C) - Meta must approve them before they can be sent.
DEFAULT_TEMPLATES = [
    {
        'event': 'approval_required', 'name': 'content_approval_required',
        'body': 'Hello! New content for {{1}} is ready for your review: "{{2}}" (planned for {{3}}). '
                'Please review and approve it here: {{4}}',
        'variables': ['company_name', 'topic', 'scheduled_date', 'link'],
    },
    {
        'event': 'content_regenerated', 'name': 'content_regenerated',
        'body': 'Updated content for {{1}} is ready: "{{2}}" has been regenerated using your feedback. '
                'Please review it here: {{3}}',
        'variables': ['company_name', 'topic', 'link'],
    },
    {
        'event': 'content_approved', 'name': 'content_approved',
        'body': '"{{1}}" for {{2}} was approved by {{3}}. It will be published as scheduled.',
        'variables': ['topic', 'company_name', 'approved_by'],
    },
    {
        'event': 'content_rejected', 'name': 'content_changes_requested',
        'body': 'Changes requested on "{{1}}" for {{2}}. Feedback: {{3}}. Review: {{4}}',
        'variables': ['topic', 'company_name', 'feedback', 'link'],
    },
    {
        'event': 'content_published', 'name': 'content_published',
        'body': '"{{1}}" is now live on {{2}} for {{3}}. View it here: {{4}}',
        'variables': ['topic', 'platform', 'company_name', 'link'],
    },
    {
        'event': 'publishing_failed', 'name': 'publishing_failed',
        'body': 'Publishing "{{1}}" to {{2}} failed for {{3}}. Reason: {{4}}. Please check the publishing queue.',
        'variables': ['topic', 'platform', 'company_name', 'error'],
    },
    {
        'event': 'approval_reminder', 'name': 'approval_reminder',
        'body': 'Reminder: "{{1}}" for {{2}} has been waiting {{3}} hours for your approval. Review it here: {{4}}',
        'variables': ['topic', 'company_name', 'hours_waiting', 'link'],
    },
    {
        'event': 'monthly_report', 'name': 'monthly_report_ready',
        'body': 'Your {{1}} marketing report for {{2}} is ready. View and download it here: {{3}}',
        'variables': ['period', 'company_name', 'link'],
    },
]


def seed(apps, schema_editor):
    WhatsAppTemplate = apps.get_model('whatsapp', 'WhatsAppTemplate')
    for template in DEFAULT_TEMPLATES:
        WhatsAppTemplate.objects.get_or_create(
            event=template['event'], language_code='en',
            defaults={'name': template['name'], 'body': template['body'], 'variables': template['variables'],
                      'category': 'utility', 'is_active': True},
        )


def unseed(apps, schema_editor):
    WhatsAppTemplate = apps.get_model('whatsapp', 'WhatsAppTemplate')
    WhatsAppTemplate.objects.filter(name__in=[t['name'] for t in DEFAULT_TEMPLATES], language_code='en').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('whatsapp', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(seed, unseed),
    ]
