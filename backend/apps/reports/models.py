from django.conf import settings
from django.db import models

from apps.companies.models import Company
from common.models import TimeStampedModel


def report_upload_path(instance, filename):
    scope = instance.company_id or 'platform'
    return f'reports/{scope}/{instance.id}/{filename}'


class Report(TimeStampedModel):
    """A generated report with its PDF / Excel / CSV exports (Epic 16: Reports).

    Client reports belong to a company (and are visible to its clients with the Reports
    page permission); admin reports are platform-wide (company is null). `data` holds the
    computed report as a format-neutral document - KPIs plus tabular sections - which
    every exporter renders, so all three formats always agree.
    """

    class ReportType(models.TextChoices):
        MONTHLY = 'monthly', 'Monthly report'
        CONTENT = 'content', 'Content report'
        PUBLISHING = 'publishing', 'Publishing report'
        ENGAGEMENT = 'engagement', 'Engagement report'
        GROWTH = 'growth', 'Growth report'
        COMPANY_OVERVIEW = 'company_overview', 'Company report'
        CLIENT_OVERVIEW = 'client_overview', 'Client report'
        AI_USAGE = 'ai_usage', 'AI usage report'
        APPROVAL = 'approval', 'Approval report'
        PUBLISHING_OVERVIEW = 'publishing_overview', 'Publishing report (all companies)'
        SUBSCRIPTION = 'subscription', 'Subscription report'

    CLIENT_TYPES = (ReportType.MONTHLY, ReportType.CONTENT, ReportType.PUBLISHING, ReportType.ENGAGEMENT, ReportType.GROWTH)
    ADMIN_TYPES = (
        ReportType.COMPANY_OVERVIEW, ReportType.CLIENT_OVERVIEW, ReportType.AI_USAGE, ReportType.APPROVAL,
        ReportType.PUBLISHING_OVERVIEW, ReportType.SUBSCRIPTION,
    )

    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        GENERATING = 'generating', 'Generating'
        READY = 'ready', 'Ready'
        FAILED = 'failed', 'Failed'

    company = models.ForeignKey(Company, null=True, blank=True, on_delete=models.CASCADE, related_name='reports')
    report_type = models.CharField(max_length=25, choices=ReportType.choices)
    title = models.CharField(max_length=255, blank=True)
    period_start = models.DateField()
    period_end = models.DateField()

    status = models.CharField(max_length=12, choices=Status.choices, default=Status.PENDING)
    error = models.TextField(blank=True)
    data = models.JSONField(default=dict, blank=True)

    pdf_file = models.FileField(upload_to=report_upload_path, blank=True, null=True)
    xlsx_file = models.FileField(upload_to=report_upload_path, blank=True, null=True)
    csv_file = models.FileField(upload_to=report_upload_path, blank=True, null=True)

    is_automated = models.BooleanField(default=False)
    generated_at = models.DateTimeField(null=True, blank=True)
    emailed_at = models.DateTimeField(null=True, blank=True)
    whatsapp_sent_at = models.DateTimeField(null=True, blank=True)
    celery_task_id = models.CharField(max_length=255, blank=True)
    generated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='+',
    )

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['company', 'report_type', 'period_start']),
            models.Index(fields=['status']),
        ]

    def __str__(self):
        return self.title or f'{self.get_report_type_display()} {self.period_start}–{self.period_end}'

    @property
    def is_client_report(self):
        return self.report_type in self.CLIENT_TYPES
