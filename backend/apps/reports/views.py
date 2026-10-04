from django.http import FileResponse
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema
from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.activity_log.models import ActivityLog
from apps.activity_log.services import log_activity
from apps.companies.models import ClientProfile
from common.mixins import AdminWriteMixin, CompanyScopedMixin
from common.permissions import IsAdmin

from .models import Report
from .serializers import ReportCreateSerializer, ReportDetailSerializer, ReportSerializer
from .services import default_title, email_report, whatsapp_report
from .tasks import generate_report

# `?file_format=pdf|xlsx|csv` - not `?format=`, which DRF reserves for renderer negotiation.
CONTENT_TYPES = {
    'pdf': 'application/pdf',
    'xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    'csv': 'text/csv',
}


def _queue(report):
    result = generate_report.delay(report.id)
    Report.objects.filter(pk=report.pk, status=Report.Status.PENDING).update(celery_task_id=result.id or '')
    report.refresh_from_db()
    return report


def _download(report, fmt):
    field = {'pdf': report.pdf_file, 'xlsx': report.xlsx_file, 'csv': report.csv_file}.get(fmt)
    if report.status != Report.Status.READY or not field:
        return Response({'detail': 'This export is not available yet.'}, status=status.HTTP_404_NOT_FOUND)
    filename = field.name.rsplit('/', 1)[-1]
    return FileResponse(field.open('rb'), as_attachment=True, filename=filename, content_type=CONTENT_TYPES[fmt])


class CompanyReportListCreateView(CompanyScopedMixin, AdminWriteMixin, generics.ListCreateAPIView):
    """A company's reports (Epic 16: Client reports) - clients with the Reports page can
    view/download; admins generate them."""

    permission_classes = [IsAuthenticated]
    required_page = ClientProfile.Page.REPORTS
    admin_write_message = 'Only admins can generate reports.'

    def get_serializer_class(self):
        return ReportCreateSerializer if self.request.method == 'POST' else ReportSerializer

    def get_queryset(self):
        queryset = Report.objects.filter(company=self.get_company()).select_related('company', 'generated_by')
        if not self.request.user.is_admin:
            queryset = queryset.filter(status=Report.Status.READY)
        if self.request.query_params.get('report_type'):
            queryset = queryset.filter(report_type=self.request.query_params['report_type'])
        return queryset

    def create(self, request, *args, **kwargs):
        company = self.get_company()
        serializer = ReportCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        if data['report_type'] not in Report.CLIENT_TYPES:
            return Response({'detail': 'That is a platform-wide report - generate it from Reports > Admin reports.'},
                            status=status.HTTP_400_BAD_REQUEST)
        report = Report.objects.create(
            company=company, report_type=data['report_type'], period_start=data['period_start'],
            period_end=data['period_end'], title=data.get('title', ''), generated_by=request.user,
        )
        if not report.title:
            report.title = default_title(report)
            report.save(update_fields=['title'])
        log_activity(module=ActivityLog.Module.REPORTS, action='Report requested', description=report.title,
                     company=company, request=request)
        return Response(ReportSerializer(_queue(report)).data, status=status.HTTP_202_ACCEPTED)


class CompanyReportDetailView(CompanyScopedMixin, AdminWriteMixin, generics.RetrieveDestroyAPIView):
    permission_classes = [IsAuthenticated]
    required_page = ClientProfile.Page.REPORTS
    serializer_class = ReportDetailSerializer

    def get_queryset(self):
        queryset = Report.objects.filter(company=self.get_company())
        return queryset if self.request.user.is_admin else queryset.filter(status=Report.Status.READY)

    def perform_destroy(self, instance):
        for field in (instance.pdf_file, instance.xlsx_file, instance.csv_file):
            if field:
                field.delete(save=False)
        instance.delete()


class CompanyReportDownloadView(CompanyScopedMixin, APIView):
    permission_classes = [IsAuthenticated]
    required_page = ClientProfile.Page.REPORTS

    @extend_schema(responses=OpenApiTypes.BINARY)
    def get(self, request, company_id, pk):
        report = generics.get_object_or_404(Report, pk=pk, company=self.get_company())
        return _download(report, request.query_params.get('file_format', 'pdf'))


class CompanyReportActionView(CompanyScopedMixin, APIView):
    """Admin: regenerate / send (email + WhatsApp) a company report."""

    permission_classes = [IsAdmin]
    action = None

    @extend_schema(responses=OpenApiTypes.OBJECT, request=OpenApiTypes.OBJECT)
    def post(self, request, company_id, pk):
        report = generics.get_object_or_404(Report, pk=pk, company=self.get_company())
        if self.action == 'regenerate':
            report.status = Report.Status.PENDING
            report.save(update_fields=['status', 'updated_at'])
            return Response(ReportSerializer(_queue(report)).data, status=status.HTTP_202_ACCEPTED)
        if report.status != Report.Status.READY:
            return Response({'detail': 'The report is not ready yet.'}, status=status.HTTP_400_BAD_REQUEST)
        emailed = email_report(report) if request.data.get('email', True) else 0
        whatsapped = whatsapp_report(report) if request.data.get('whatsapp', True) else 0
        log_activity(module=ActivityLog.Module.REPORTS, action='Report sent',
                     description=f'{report.title} — {emailed} email(s), {whatsapped} WhatsApp message(s)',
                     company=report.company, request=request)
        return Response({'detail': f'Sent to {emailed} email recipient(s) and {whatsapped} WhatsApp number(s).',
                         'report': ReportSerializer(report).data})


class AdminReportListCreateView(generics.ListCreateAPIView):
    """Admin: platform-wide reports (Epic 16: Admin reports)."""

    permission_classes = [IsAdmin]

    def get_serializer_class(self):
        return ReportCreateSerializer if self.request.method == 'POST' else ReportSerializer

    def get_queryset(self):
        queryset = Report.objects.select_related('company', 'generated_by')
        scope = self.request.query_params.get('scope', 'platform')
        if scope == 'platform':
            queryset = queryset.filter(company__isnull=True)
        elif scope == 'company':
            queryset = queryset.filter(company__isnull=False)
        if self.request.query_params.get('report_type'):
            queryset = queryset.filter(report_type=self.request.query_params['report_type'])
        return queryset

    def create(self, request, *args, **kwargs):
        serializer = ReportCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        if data['report_type'] not in Report.ADMIN_TYPES:
            return Response({'detail': 'Company reports are generated from the company\'s Reports page.'},
                            status=status.HTTP_400_BAD_REQUEST)
        report = Report.objects.create(
            report_type=data['report_type'], period_start=data['period_start'], period_end=data['period_end'],
            title=data.get('title', ''), generated_by=request.user,
        )
        if not report.title:
            report.title = default_title(report)
            report.save(update_fields=['title'])
        log_activity(module=ActivityLog.Module.REPORTS, action='Report requested', description=report.title, request=request)
        return Response(ReportSerializer(_queue(report)).data, status=status.HTTP_202_ACCEPTED)


class AdminReportDetailView(generics.RetrieveDestroyAPIView):
    permission_classes = [IsAdmin]
    serializer_class = ReportDetailSerializer
    queryset = Report.objects.all()

    def perform_destroy(self, instance):
        for field in (instance.pdf_file, instance.xlsx_file, instance.csv_file):
            if field:
                field.delete(save=False)
        instance.delete()


class AdminReportDownloadView(APIView):
    permission_classes = [IsAdmin]

    @extend_schema(responses=OpenApiTypes.BINARY)
    def get(self, request, pk):
        report = generics.get_object_or_404(Report, pk=pk)
        return _download(report, request.query_params.get('file_format', 'pdf'))


class AdminReportRegenerateView(APIView):
    permission_classes = [IsAdmin]

    @extend_schema(responses=OpenApiTypes.OBJECT, request=OpenApiTypes.OBJECT)
    def post(self, request, pk):
        report = generics.get_object_or_404(Report, pk=pk)
        report.status = Report.Status.PENDING
        report.save(update_fields=['status', 'updated_at'])
        return Response(ReportSerializer(_queue(report)).data, status=status.HTTP_202_ACCEPTED)
