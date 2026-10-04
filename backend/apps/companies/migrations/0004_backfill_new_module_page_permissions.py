from django.db import migrations

NEW_PAGES = ['publishing', 'analytics', 'reports', 'subscription']


def add_new_pages(apps, schema_editor):
    """Publishing, Analytics, Reports and Subscription are newly-added client pages -
    nobody could have restricted them before, so existing clients get them by default
    (an admin can uncheck them on Access Control), the same rule as the AI Strategy
    backfill in 0003."""
    ClientProfile = apps.get_model('companies', 'ClientProfile')
    for profile in ClientProfile.objects.all():
        pages = list(profile.page_permissions or [])
        missing = [page for page in NEW_PAGES if page not in pages]
        if missing:
            profile.page_permissions = [*pages, *missing]
            profile.save(update_fields=['page_permissions'])


def remove_new_pages(apps, schema_editor):
    ClientProfile = apps.get_model('companies', 'ClientProfile')
    for profile in ClientProfile.objects.all():
        pages = [page for page in (profile.page_permissions or []) if page not in NEW_PAGES]
        if pages != (profile.page_permissions or []):
            profile.page_permissions = pages
            profile.save(update_fields=['page_permissions'])


class Migration(migrations.Migration):

    dependencies = [
        ('companies', '0003_backfill_ai_strategy_page_permission'),
    ]

    operations = [
        migrations.RunPython(add_new_pages, remove_new_pages),
    ]
