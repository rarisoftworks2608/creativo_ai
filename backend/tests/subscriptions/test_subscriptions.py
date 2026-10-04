import datetime
from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from apps.creative_generation.models import GenerationRequest
from apps.notifications.models import Notification
from apps.platform_settings.models import PlatformSettings
from apps.subscriptions.enforcement import QuotaExceeded, check_quota
from apps.subscriptions.models import BillingRecord, Plan, Subscription
from apps.subscriptions.tasks import check_subscriptions
from apps.subscriptions.usage import compute_usage, invalidate_usage_cache, usage_period
from tests.helpers import PlatformFixturesMixin


def make_plan(**overrides):
    defaults = {'name': 'Growth', 'slug': 'growth', 'price': Decimal('19999'), 'creative_limit': 2, 'video_limit': 1,
                'publishing_limit': 10}
    defaults.update(overrides)
    return Plan.objects.create(**defaults)


class SubscriptionAdminApiTests(PlatformFixturesMixin, APITestCase):
    def test_admin_creates_plan_with_generated_slug(self):
        self.login(self.admin)
        response = self.client.post(reverse('subscriptions:plan-list-create'), {
            'name': 'Starter Plan', 'price': '9999.00', 'creative_limit': 20, 'allowed_platforms': ['instagram'],
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertEqual(response.data['slug'], 'starter-plan')

    def test_new_current_subscription_cancels_the_old_one(self):
        plan = make_plan()
        old = Subscription.objects.create(company=self.company, plan=plan, start_date=datetime.date(2026, 1, 1))
        self.login(self.admin)
        response = self.client.post(reverse('subscriptions:subscription-list-create'), {
            'company': self.company.pk, 'plan': plan.pk, 'start_date': timezone.localdate().isoformat(),
            'end_date': (timezone.localdate() + datetime.timedelta(days=30)).isoformat(),
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        old.refresh_from_db()
        self.assertEqual(old.status, Subscription.Status.CANCELLED)

    def test_end_before_start_is_rejected(self):
        plan = make_plan()
        self.login(self.admin)
        response = self.client.post(reverse('subscriptions:subscription-list-create'), {
            'company': self.company.pk, 'plan': plan.pk, 'start_date': '2026-05-10', 'end_date': '2026-05-01',
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_billing_record_total_and_client_isolation(self):
        self.login(self.admin)
        url = reverse('company_subscription:billing-list-create', kwargs={'company_id': self.company.pk})
        response = self.client.post(url, {
            'invoice_number': 'INV-001', 'invoice_date': '2026-09-01', 'amount': '10000.00', 'tax_amount': '1800.00',
            'payment_status': 'paid', 'payment_method': 'upi', 'payment_reference': 'UTR123', 'amount_paid': '11800.00',
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertEqual(response.data['total_amount'], '11800.00')
        self.assertEqual(response.data['balance_due'], '0.00')

        self.login(self.client_user)
        self.assertEqual(self.client.get(url).status_code, status.HTTP_403_FORBIDDEN)

    def test_client_sees_plan_and_usage_but_not_history(self):
        Subscription.objects.create(company=self.company, plan=make_plan(), start_date=timezone.localdate())
        self.login(self.client_user)
        response = self.client.get(reverse('company_subscription:current', kwargs={'company_id': self.company.pk}))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['plan']['name'], 'Growth')
        self.assertNotIn('history', response.data)

    def test_usage_overview(self):
        self.login(self.admin)
        response = self.client.get(reverse('subscriptions:usage-overview'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['summary']['without_subscription'], 2)


class UsageAndEnforcementTests(PlatformFixturesMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.plan = make_plan()
        self.subscription = Subscription.objects.create(
            company=self.company, plan=self.plan, start_date=timezone.localdate() - datetime.timedelta(days=3),
        )

    def _creative(self, status_value=GenerationRequest.Status.SUCCEEDED):
        GenerationRequest.objects.create(company=self.company, creative_type='post', status=status_value)
        invalidate_usage_cache(self.company.id)

    def test_usage_counts_exclude_failed_generations(self):
        self._creative()
        self._creative(GenerationRequest.Status.FAILED)
        metric = compute_usage(self.company, use_cache=False)['metrics']['creative']
        self.assertEqual(metric['used'], 1)
        self.assertEqual(metric['limit'], 2)
        self.assertEqual(metric['percentage'], 50.0)

    def test_usage_period_is_anchored_on_start_day(self):
        subscription = Subscription(plan=self.plan, start_date=datetime.date(2026, 1, 15))
        start, end = usage_period(subscription, datetime.date(2026, 3, 10))
        self.assertEqual((start, end), (datetime.date(2026, 2, 15), datetime.date(2026, 3, 14)))

    def test_quota_not_enforced_by_default(self):
        self._creative()
        self._creative()
        check_quota(self.company, 'creative')  # no exception

    def test_quota_enforced_when_enabled(self):
        settings_obj = PlatformSettings.load()
        settings_obj.enforce_subscription_limits = True
        settings_obj.save()
        self._creative()
        check_quota(self.company, 'creative')
        self._creative()
        with self.assertRaises(QuotaExceeded):
            check_quota(self.company, 'creative')
        self.assertTrue(Notification.objects.filter(
            recipient=self.admin, notification_type=Notification.NotificationType.USAGE_LIMIT_REACHED,
        ).exists())

    def test_override_limit_beats_plan(self):
        self.subscription.creative_limit_override = 0  # unlimited
        self.subscription.save()
        settings_obj = PlatformSettings.load()
        settings_obj.enforce_subscription_limits = True
        settings_obj.save()
        for _ in range(5):
            self._creative()
        check_quota(self.company, 'creative')

    def test_no_subscription_blocks_when_enforced(self):
        settings_obj = PlatformSettings.load()
        settings_obj.enforce_subscription_limits = True
        settings_obj.save()
        with self.assertRaises(QuotaExceeded):
            check_quota(self.other_company, 'creative')


class GenerationQuotaApiTests(PlatformFixturesMixin, APITestCase):
    def test_creative_generation_is_blocked_when_limit_reached(self):
        Subscription.objects.create(company=self.company, plan=make_plan(creative_limit=1), start_date=timezone.localdate())
        GenerationRequest.objects.create(company=self.company, creative_type='post', status=GenerationRequest.Status.SUCCEEDED)
        settings_obj = PlatformSettings.load()
        settings_obj.enforce_subscription_limits = True
        settings_obj.save()
        self.login(self.admin)
        with patch('apps.creative_generation.views._enqueue') as mock_enqueue:
            response = self.client.post(
                reverse('creative_generation:request-list-create', kwargs={'company_id': self.company.pk}),
                {'creative_type': 'post', 'platform': 'instagram', 'variation_count': 1}, format='json',
            )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn('limit reached', response.data['detail'])
        mock_enqueue.assert_not_called()


class SubscriptionTaskTests(PlatformFixturesMixin, TestCase):
    def test_expires_reminds_and_flags_overdue(self):
        plan = make_plan()
        today = timezone.localdate()
        expired = Subscription.objects.create(company=self.company, plan=plan, start_date=today - datetime.timedelta(days=60),
                                              end_date=today - datetime.timedelta(days=1))
        expiring = Subscription.objects.create(company=self.other_company, plan=plan, start_date=today - datetime.timedelta(days=20),
                                               end_date=today + datetime.timedelta(days=5))
        invoice = BillingRecord.objects.create(company=self.company, invoice_date=today - datetime.timedelta(days=40),
                                               due_date=today - datetime.timedelta(days=10), amount=Decimal('100'))

        result = check_subscriptions()

        expired.refresh_from_db()
        expiring.refresh_from_db()
        invoice.refresh_from_db()
        self.assertEqual(expired.status, Subscription.Status.EXPIRED)
        self.assertEqual(expiring.last_reminder_sent_on, today)
        self.assertEqual(invoice.payment_status, BillingRecord.PaymentStatus.OVERDUE)
        self.assertEqual(result['expired'], 1)
        self.assertTrue(Notification.objects.filter(notification_type=Notification.NotificationType.SUBSCRIPTION_EXPIRING).exists())

        check_subscriptions()  # same day - no duplicate reminder
        self.assertEqual(
            Notification.objects.filter(notification_type=Notification.NotificationType.SUBSCRIPTION_EXPIRING).count(), 1,
        )
