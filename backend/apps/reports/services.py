"""Report generation + delivery (Epic 16: Monthly report generation, Email report,
WhatsApp report, Download report)."""

import calendar
import datetime
import logging

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.mail import EmailMessage
from django.utils import timezone
from django.utils.text import slugify

from apps.activity_log.models import ActivityLog
from apps.activity_log.services import log_activity
from apps.notifications.models import Notification
from apps.notifications.services import notify, notify_admins

from . import builders, exporters
from .models import Report

logger = logging.getLogger(__name__)


def previous_month(today=None):
    today = today or timezone.localdate()
    last_day_prev = today.replace(day=1) - datetime.timedelta(days=1)
    return last_day_prev.replace(day=1), last_day_prev


def month_bounds(year, month):
    return datetime.date(year, month, 1), datetime.date(year, month, calendar.monthrange(year, month)[1])


def default_title(report):
    label = report.get_report_type_display()
    if report.report_type == Report.ReportType.MONTHLY:
        period = report.period_start.strftime('%B %Y')
    else:
        period = f'{report.period_start:%d %b %Y} – {report.period_end:%d %b %Y}'
    owner = report.company.name if report.company else 'All companies'
    return f'{label} · {owner} · {period}'


def generate(report):
    """Builds the document and all three exports. Marks the report READY or FAILED."""
    report.status = Report.Status.GENERATING
    report.error = ''
    report.save(update_fields=['status', 'error', 'updated_at'])
    try:
        document = builders.build(report)
        pdf_bytes = exporters.to_pdf(document)
        xlsx_bytes = exporters.to_xlsx(document)
        csv_bytes = exporters.to_csv(document)
    except Exception as exc:  # noqa: BLE001 - surfaced on the report, never left "generating"
        logger.exception('Report %s failed', report.id)
        report.status = Report.Status.FAILED
        report.error = str(exc)[:2000]
        report.save(update_fields=['status', 'error', 'updated_at'])
        return report

    base = slugify(f'{report.get_report_type_display()}-{report.period_start}-{report.period_end}')[:80] or 'report'
    for field, content in (('pdf_file', pdf_bytes), ('xlsx_file', xlsx_bytes), ('csv_file', csv_bytes)):
        existing = getattr(report, field)
        if existing:
            existing.delete(save=False)
    report.pdf_file.save(f'{base}.pdf', ContentFile(pdf_bytes), save=False)
    report.xlsx_file.save(f'{base}.xlsx', ContentFile(xlsx_bytes), save=False)
    report.csv_file.save(f'{base}.csv', ContentFile(csv_bytes), save=False)
    report.data = document
    report.title = report.title or document.get('title', '')[:255]
    report.status = Report.Status.READY
    report.generated_at = timezone.now()
    report.save()

    log_activity(module=ActivityLog.Module.REPORTS, action='Report generated', description=report.title or str(report),
                 company=report.company, user=report.generated_by)
    _notify_ready(report)
    return report


def _client_users(company):
    from apps.companies.models import ClientProfile

    return [
        profile.user for profile in company.clients.select_related('user')
        if profile.user.is_active and profile.can_access(ClientProfile.Page.REPORTS)
    ]


def _notify_ready(report):
    url = f'/companies/{report.company_id}/reports' if report.company_id else '/reports'
    title = f'{report.get_report_type_display()} is ready'
    message = report.title or ''
    if report.generated_by is not None:
        notify(report.generated_by, Notification.NotificationType.REPORT_READY, title, message=message, url=url,
               company=report.company)
    elif report.company is None:
        notify_admins(actor=None, notification_type=Notification.NotificationType.REPORT_READY, title=title,
                      message=message, url=url)
    if report.is_automated and report.company is not None:
        for user in _client_users(report.company):
            notify(user, Notification.NotificationType.REPORT_READY, title, message=message, url=url, company=report.company)


def email_report(report, recipients=None):
    """Emails the PDF to the company's clients (or the given users). Returns how many sent."""
    if report.status != Report.Status.READY or not report.pdf_file or report.company is None:
        return 0
    users = recipients if recipients is not None else [u for u in _client_users(report.company) if u.email_notifications_enabled]
    emails = [u.email for u in users if u.email]
    if not emails:
        return 0
    with report.pdf_file.open('rb') as handle:
        pdf = handle.read()
    link = f'{settings.FRONTEND_URL.rstrip("/")}/companies/{report.company_id}/reports'
    message = EmailMessage(
        subject=report.title or report.get_report_type_display(),
        body=(
            f'Hello,\n\nYour {report.get_report_type_display().lower()} for {report.company.name} '
            f'({report.period_start:%d %b %Y} – {report.period_end:%d %b %Y}) is attached.\n\n'
            f'You can also view and download it (PDF, Excel, CSV) here: {link}\n'
        ),
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=emails,
    )
    message.attach(report.pdf_file.name.rsplit('/', 1)[-1], pdf, 'application/pdf')
    try:
        message.send(fail_silently=False)
    except Exception:  # noqa: BLE001 - delivery failure is logged, the report itself is fine
        logger.exception('Emailing report %s failed', report.id)
        return 0
    report.emailed_at = timezone.now()
    report.save(update_fields=['emailed_at', 'updated_at'])
    return len(emails)


def whatsapp_report(report):
    if report.status != Report.Status.READY or report.company is None:
        return 0
    from apps.whatsapp.services import dispatch_event

    messages = dispatch_event(report.company, 'monthly_report', {
        'period': report.period_start.strftime('%B %Y') if report.report_type == Report.ReportType.MONTHLY
        else f'{report.period_start:%d %b} – {report.period_end:%d %b %Y}',
        'url': f'/companies/{report.company_id}/reports',
    })
    if messages:
        report.whatsapp_sent_at = timezone.now()
        report.save(update_fields=['whatsapp_sent_at', 'updated_at'])
    return len(messages)
