import datetime
from unittest.mock import patch

from django.core import mail
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from apps.platform_settings.models import PlatformSettings
from apps.reports import exporters
from apps.reports.models import Report
from apps.reports.services import email_report, generate
from apps.reports.tasks import generate_monthly_reports
from tests.helpers import EagerCeleryMixin, PlatformFixturesMixin, TempMediaMixin

DOCUMENT = {
    'title': 'Test report', 'subtitle': '1 Sep – 30 Sep',
    'kpis': [{'label': 'Reach', 'value': 1200, 'hint': '+10%'}, {'label': 'Rate', 'value': '4.5%'}],
    'sections': [{'title': 'Top posts', 'columns': ['Topic', 'Reach'], 'rows': [['Diwali ₹ offer', 900], ['Launch', 300]]}],
}


class ExporterTests(TestCase):
    def test_pdf_excel_and_csv_are_valid(self):
        pdf = exporters.to_pdf(DOCUMENT)
        self.assertTrue(pdf.startswith(b'%PDF'))
        xlsx = exporters.to_xlsx(DOCUMENT)
        self.assertTrue(xlsx.startswith(b'PK'))
        csv_bytes = exporters.to_csv(DOCUMENT)
        self.assertTrue(csv_bytes.startswith('﻿'.encode('utf-8')))
        self.assertIn('Diwali ₹ offer', csv_bytes.decode('utf-8'))

    def test_wide_tables_render_in_landscape(self):
        document = {**DOCUMENT, 'sections': [{'title': 'Wide', 'columns': [f'c{i}' for i in range(9)], 'rows': [list(range(9))]}]}
        self.assertTrue(exporters.to_pdf(document).startswith(b'%PDF'))


class ReportGenerationTests(TempMediaMixin, EagerCeleryMixin, PlatformFixturesMixin, APITestCase):
    def setUp(self):
        super().setUp()
        self.today = timezone.localdate()
        self.start = self.today.replace(day=1)

    def list_url(self):
        return reverse('reports:list-create', kwargs={'company_id': self.company.pk})

    def test_admin_generates_monthly_report_with_all_formats(self):
        self.make_item()
        self.login(self.admin)
        response = self.client.post(self.list_url(), {
            'report_type': 'monthly', 'period_start': self.start.isoformat(), 'period_end': self.today.isoformat(),
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED, response.data)
        report = Report.objects.get(pk=response.data['id'])
        self.assertEqual(report.status, Report.Status.READY, report.error)
        self.assertTrue(report.pdf_file and report.xlsx_file and report.csv_file)
        self.assertIn('kpis', report.data)

        download = self.client.get(
            reverse('reports:download', kwargs={'company_id': self.company.pk, 'pk': report.pk}), {'file_format': 'xlsx'},
        )
        self.assertEqual(download.status_code, 200)
        self.assertIn('spreadsheetml', download['Content-Type'])

    def test_client_can_download_but_not_generate(self):
        report = Report.objects.create(company=self.company, report_type='content', period_start=self.start, period_end=self.today)
        generate(report)
        self.login(self.client_user)
        self.assertEqual(self.client.get(self.list_url()).data['count'], 1)
        pdf = self.client.get(reverse('reports:download', kwargs={'company_id': self.company.pk, 'pk': report.pk}))
        self.assertEqual(pdf.status_code, 200)
        self.assertEqual(pdf['Content-Type'], 'application/pdf')
        create = self.client.post(self.list_url(), {
            'report_type': 'monthly', 'period_start': self.start.isoformat(), 'period_end': self.today.isoformat(),
        }, format='json')
        self.assertEqual(create.status_code, status.HTTP_403_FORBIDDEN)

    def test_client_cannot_see_another_companys_reports(self):
        self.login(self.client_user)
        url = reverse('reports:list-create', kwargs={'company_id': self.other_company.pk})
        self.assertEqual(self.client.get(url).status_code, status.HTTP_404_NOT_FOUND)

    def test_admin_platform_reports(self):
        self.login(self.admin)
        for report_type in ('company_overview', 'client_overview', 'ai_usage', 'approval', 'publishing_overview', 'subscription'):
            response = self.client.post(reverse('reports_admin:list-create'), {
                'report_type': report_type, 'period_start': self.start.isoformat(), 'period_end': self.today.isoformat(),
            }, format='json')
            self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED, response.data)
            report = Report.objects.get(pk=response.data['id'])
            self.assertEqual(report.status, Report.Status.READY, f'{report_type}: {report.error}')

    def test_company_endpoint_rejects_admin_report_types(self):
        self.login(self.admin)
        response = self.client.post(self.list_url(), {
            'report_type': 'ai_usage', 'period_start': self.start.isoformat(), 'period_end': self.today.isoformat(),
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_email_report_attaches_pdf(self):
        report = Report.objects.create(company=self.company, report_type='monthly', period_start=self.start, period_end=self.today)
        generate(report)
        sent = email_report(report)
        self.assertEqual(sent, 1)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].attachments[0][2], 'application/pdf')


class MonthlyAutomationTests(TempMediaMixin, PlatformFixturesMixin, TestCase):
    def test_generates_last_months_reports_once_on_the_configured_day(self):
        settings_obj = PlatformSettings.load()
        settings_obj.report_day_of_month = 1
        settings_obj.save()
        first_of_month = datetime.date(2026, 10, 1)
        with patch('apps.reports.tasks.timezone.localdate', return_value=first_of_month), \
                patch('apps.reports.tasks.generate_report.delay') as mock_delay:
            self.assertEqual(generate_monthly_reports(), 2)
            self.assertEqual(generate_monthly_reports(), 0)
        report = Report.objects.filter(company=self.company).get()
        self.assertEqual((report.period_start, report.period_end), (datetime.date(2026, 9, 1), datetime.date(2026, 9, 30)))
        self.assertTrue(report.is_automated)
        self.assertEqual(mock_delay.call_count, 2)

    def test_does_nothing_on_other_days(self):
        with patch('apps.reports.tasks.timezone.localdate', return_value=datetime.date(2026, 10, 9)):
            self.assertEqual(generate_monthly_reports(), 0)
