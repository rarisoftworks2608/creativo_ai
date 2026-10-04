import datetime
from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from apps.analytics import fetchers, services
from apps.analytics.models import AccountMetricSnapshot, AnalyticsSyncLog, PostMetrics
from apps.publishing.models import PublishJob
from tests.helpers import PlatformFixturesMixin, TempMediaMixin


def make_published_job(test, platform='instagram', account=None, days_ago=1, external_id='M1', content_type='Reel'):
    item = test.make_item(content_type=content_type, platforms=[platform])
    return PublishJob.objects.create(
        company=test.company, content_calendar_item=item, social_account=account or test.make_account(platform, account_id=f'{platform}-1'),
        platform=platform, post_type='image', scheduled_at=timezone.now() - datetime.timedelta(days=days_ago),
        status=PublishJob.Status.PUBLISHED, published_at=timezone.now() - datetime.timedelta(days=days_ago),
        external_post_id=external_id, external_url=f'https://example.com/{external_id}',
    )


class FetcherTests(PlatformFixturesMixin, TestCase):
    def test_instagram_metrics_are_mapped_with_fallback(self):
        job = make_published_job(self)

        def fake_get(url, params=None, headers=None):
            if url.endswith('/insights'):
                if 'total_interactions' in params['metric']:
                    raise fetchers.FetchError('metric deprecated')
                return {'data': [{'name': 'reach', 'values': [{'value': 500}]}, {'name': 'saved', 'values': [{'value': 7}]},
                                 {'name': 'shares', 'total_value': {'value': 3}}]}
            return {'like_count': 40, 'comments_count': 5}

        with patch('apps.analytics.fetchers._get', side_effect=fake_get):
            metrics, raw = fetchers.fetch_post_metrics(job)
        self.assertEqual(metrics, {'reach': 500, 'saves': 7, 'shares': 3, 'likes': 40, 'comments': 5})

    def test_sync_post_computes_engagement_rate_and_keeps_history(self):
        job = make_published_job(self)
        with patch('apps.analytics.fetchers.fetch_post_metrics',
                   return_value=({'reach': 1000, 'likes': 80, 'comments': 10, 'shares': 5, 'saves': 5}, {})):
            record = services.sync_post(job)
            services.sync_post(job)
        self.assertEqual(record.engagements, 100)
        self.assertEqual(record.engagement_rate, 10.0)
        self.assertEqual(record.snapshots.count(), 2)

    def test_sync_company_records_partial_failure(self):
        good = make_published_job(self, external_id='OK')
        make_published_job(self, platform='facebook', external_id='BAD')

        def fake_fetch(job):
            if job.external_post_id == 'BAD':
                raise fetchers.FetchError('Unsupported post')
            return {'reach': 10, 'likes': 1}, {}

        with patch('apps.analytics.fetchers.fetch_post_metrics', side_effect=fake_fetch), \
                patch('apps.analytics.fetchers.fetch_account_metrics', return_value={'followers': 1200, 'raw': {}}):
            log = services.sync_company(self.company)
        self.assertEqual(log.status, AnalyticsSyncLog.Status.PARTIAL)
        self.assertEqual(log.posts_synced, 1)
        self.assertEqual(log.posts_failed, 1)
        self.assertTrue(PostMetrics.objects.filter(publish_job=good).exists())
        self.assertTrue(AccountMetricSnapshot.objects.filter(company=self.company, followers=1200).exists())


class SummaryTests(TempMediaMixin, PlatformFixturesMixin, TestCase):
    def _metrics(self, job, **values):
        record = PostMetrics(publish_job=job, company=self.company, platform=job.platform, published_at=job.published_at,
                             content_type=job.content_calendar_item.content_type, **values)
        record.recompute()
        record.save()
        return record

    def test_summary_totals_best_platform_and_top_posts(self):
        ig = make_published_job(self, platform='instagram', external_id='A', content_type='Reel')
        fb = make_published_job(self, platform='facebook', external_id='B', content_type='Static Post')
        self._metrics(ig, reach=1000, likes=150, comments=30, shares=10, saves=10)   # 20%
        self._metrics(fb, reach=2000, likes=50, comments=10)                          # 3%

        data = services.summary(self.company)
        self.assertEqual(data['totals']['posts'], 2)
        self.assertEqual(data['totals']['reach'], 3000)
        self.assertEqual(data['totals']['engagements'], 260)
        self.assertEqual(data['best_platform'], 'instagram')
        self.assertEqual(data['best_content_type'], 'Reel')
        self.assertEqual(data['top_posts'][0]['job_id'], ig.id)
        self.assertEqual(len(data['timeline']), 30)

    def test_previous_period_change(self):
        old = make_published_job(self, external_id='OLD', days_ago=40)
        new = make_published_job(self, external_id='NEW', days_ago=2)
        self._metrics(old, reach=100, likes=10)
        self._metrics(new, reach=200, likes=20)
        data = services.summary(self.company)
        self.assertEqual(data['changes']['reach'], 100.0)


class AnalyticsApiTests(PlatformFixturesMixin, APITestCase):
    def test_client_with_analytics_page_can_view_summary(self):
        self.login(self.client_user)
        response = self.client.get(reverse('analytics:summary', kwargs={'company_id': self.company.pk}))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('totals', response.data)

    def test_client_without_page_gets_404_and_cannot_sync(self):
        self.client_profile.page_permissions = ['dashboard']
        self.client_profile.save()
        self.login(self.client_user)
        self.assertEqual(self.client.get(reverse('analytics:summary', kwargs={'company_id': self.company.pk})).status_code, 404)
        self.assertEqual(self.client.post(reverse('analytics:sync', kwargs={'company_id': self.company.pk})).status_code, 403)

    def test_admin_can_trigger_sync(self):
        self.login(self.admin)
        with patch('apps.analytics.tasks.sync_company_analytics.delay') as mock_delay:
            response = self.client.post(reverse('analytics:sync', kwargs={'company_id': self.company.pk}))
        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        mock_delay.assert_called_once()

    def test_admin_overview(self):
        self.login(self.admin)
        response = self.client.get(reverse('analytics_global:overview'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('companies', response.data)
