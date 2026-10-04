"""Report jobs (Epic 16: Automation - Monthly report generation; Epic 23: Reports jobs)."""

from celery import shared_task
from django.utils import timezone

from .models import Report


@shared_task(bind=True)
def generate_report(self, report_id, deliver=False):
    from .services import email_report, generate, whatsapp_report

    report = Report.objects.select_related('company', 'generated_by').filter(pk=report_id).first()
    if report is None:
        return None
    if self.request.id:
        Report.objects.filter(pk=report_id).update(celery_task_id=self.request.id)
    report = generate(report)
    if deliver and report.status == Report.Status.READY:
        from apps.platform_settings.models import PlatformSettings

        platform_settings = PlatformSettings.load()
        if platform_settings.email_reports_to_clients:
            email_report(report)
        if platform_settings.whatsapp_reports_to_clients:
            whatsapp_report(report)
    return report.status


@shared_task
def generate_monthly_reports():
    """Daily: on Admin Settings > report day of month, creates last month's Monthly
    report for every active company (once - an existing one is never duplicated) and
    delivers it by email/WhatsApp per the settings."""
    from apps.companies.models import Company
    from apps.platform_settings.models import PlatformSettings

    from .services import previous_month

    platform_settings = PlatformSettings.load()
    today = timezone.localdate()
    if not platform_settings.monthly_reports_enabled:
        return 0
    if today.day != max(1, min(platform_settings.report_day_of_month or 1, 28)):
        return 0

    start, end = previous_month(today)
    created = 0
    for company in Company.objects.filter(status=Company.Status.ACTIVE):
        exists = Report.objects.filter(
            company=company, report_type=Report.ReportType.MONTHLY, period_start=start, period_end=end,
        ).exclude(status=Report.Status.FAILED).exists()
        if exists:
            continue
        report = Report.objects.create(
            company=company, report_type=Report.ReportType.MONTHLY, period_start=start, period_end=end,
            is_automated=True,
        )
        from .services import default_title

        report.title = default_title(report)
        report.save(update_fields=['title'])
        generate_report.delay(report.id, deliver=True)
        created += 1
    return created
