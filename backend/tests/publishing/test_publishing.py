import datetime
from unittest.mock import Mock, patch

from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from apps.companies.models import ClientProfile
from apps.content_calendar.models import ContentCalendarItem, ContentReviewEvent
from apps.notifications.models import Notification
from apps.platform_settings.models import PlatformSettings
from apps.publishing import media as media_utils
from apps.publishing.models import PublishJob
from apps.publishing.platforms import (
    FacebookPublisher,
    InstagramPublisher,
    PublishError,
    PublishResult,
    linkedin_commentary,
)
from apps.publishing.tasks import dispatch_due_publish_jobs, publish_job
from apps.social_accounts.models import SocialAccount
from tests.helpers import PlatformFixturesMixin, TempMediaMixin


class PublishingApiTests(TempMediaMixin, PlatformFixturesMixin, APITestCase):
    def setUp(self):
        super().setUp()
        self.item = self.make_item()
        self.creative, self.variations = self.add_creative(self.item)
        self.facebook = self.make_account('facebook')
        self.instagram = self.make_account('instagram', account_id='1789')

    def jobs_url(self, company_id=None):
        return reverse('publishing:job-list-create', kwargs={'company_id': company_id or self.company.pk})

    def test_admin_schedules_approved_content_to_multiple_accounts(self):
        self.login(self.admin)
        when = timezone.now() + datetime.timedelta(days=1)
        response = self.client.post(self.jobs_url(), {
            'content_calendar_item': self.item.pk, 'social_account_ids': [self.facebook.pk, self.instagram.pk],
            'scheduled_at': when.isoformat(),
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertEqual(len(response.data), 2)
        jobs = PublishJob.objects.filter(content_calendar_item=self.item)
        self.assertEqual(jobs.count(), 2)
        job = jobs.get(platform='facebook')
        self.assertEqual(job.status, PublishJob.Status.SCHEDULED)
        self.assertEqual(job.media[0]['source'], 'variation')
        self.assertEqual(job.media[0]['id'], self.variations[0].id)
        self.assertIn('Caption 1', job.caption)
        self.assertIn('#Diwali', job.caption)
        self.assertIn('#Offer', job.caption)
        self.assertTrue(ContentReviewEvent.objects.filter(item=self.item, action=ContentReviewEvent.Action.SCHEDULED).exists())

    def test_unapproved_content_cannot_be_scheduled(self):
        pending = self.make_item(status=ContentCalendarItem.Status.PENDING_APPROVAL)
        self.add_creative(pending)
        self.login(self.admin)
        response = self.client.post(self.jobs_url(), {
            'content_calendar_item': pending.pk, 'social_account_ids': [self.facebook.pk],
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_account_from_another_company_is_rejected(self):
        foreign = self.make_account('facebook', company=self.other_company, account_id='999')
        self.login(self.admin)
        response = self.client.post(self.jobs_url(), {
            'content_calendar_item': self.item.pk, 'social_account_ids': [foreign.pk],
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_disconnected_account_is_rejected(self):
        self.facebook.status = SocialAccount.Status.DISCONNECTED
        self.facebook.save()
        self.login(self.admin)
        response = self.client.post(self.jobs_url(), {
            'content_calendar_item': self.item.pk, 'social_account_ids': [self.facebook.pk],
            'scheduled_at': (timezone.now() + datetime.timedelta(hours=2)).isoformat(),
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_publish_now_enqueues_immediately(self):
        self.login(self.admin)
        with patch('apps.publishing.tasks.publish_job.delay', return_value=Mock(id='task-1')) as mock_delay:
            response = self.client.post(self.jobs_url(), {
                'content_calendar_item': self.item.pk, 'social_account_ids': [self.facebook.pk],
            }, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        mock_delay.assert_called_once()
        self.assertEqual(PublishJob.objects.get().status, PublishJob.Status.QUEUED)

    def test_client_can_view_but_not_schedule(self):
        PublishJob.objects.create(
            company=self.company, content_calendar_item=self.item, social_account=self.facebook, platform='facebook',
            scheduled_at=timezone.now() + datetime.timedelta(days=1),
        )
        self.login(self.client_user)
        self.assertEqual(self.client.get(self.jobs_url()).data['count'], 1)
        response = self.client.post(self.jobs_url(), {
            'content_calendar_item': self.item.pk, 'social_account_ids': [self.facebook.pk],
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_client_without_publishing_page_gets_404(self):
        self.client_profile.page_permissions = [p for p in self.client_profile.page_permissions if p != 'publishing']
        self.client_profile.save()
        self.login(self.client_user)
        self.assertEqual(self.client.get(self.jobs_url()).status_code, status.HTTP_404_NOT_FOUND)

    def test_client_cannot_see_another_companys_queue(self):
        self.login(self.client_user)
        self.assertEqual(self.client.get(self.jobs_url(self.other_company.pk)).status_code, status.HTTP_404_NOT_FOUND)

    def test_cancel_and_retry(self):
        job = PublishJob.objects.create(
            company=self.company, content_calendar_item=self.item, social_account=self.facebook, platform='facebook',
            scheduled_at=timezone.now() + datetime.timedelta(days=1),
        )
        self.login(self.admin)
        cancel = self.client.post(reverse('publishing:job-cancel', kwargs={'company_id': self.company.pk, 'pk': job.pk}))
        self.assertEqual(cancel.status_code, status.HTTP_200_OK)
        job.refresh_from_db()
        self.assertEqual(job.status, PublishJob.Status.CANCELLED)

        with patch('apps.publishing.tasks.publish_job.delay', return_value=Mock(id='task-2')):
            retry = self.client.post(reverse('publishing:job-retry', kwargs={'company_id': self.company.pk, 'pk': job.pk}))
        self.assertEqual(retry.status_code, status.HTTP_200_OK)
        job.refresh_from_db()
        self.assertEqual(job.status, PublishJob.Status.QUEUED)

    @override_settings(PUBLIC_MEDIA_BASE_URL='', BACKEND_PUBLIC_URL='http://localhost:8000')
    def test_preview_lists_accounts_with_warnings(self):
        self.login(self.admin)
        response = self.client.get(reverse('publishing:preview', kwargs={'company_id': self.company.pk, 'item_id': self.item.pk}))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['post_type'], PublishJob.PostType.IMAGE)
        instagram = next(a for a in response.data['accounts'] if a['platform'] == 'instagram')
        self.assertTrue(any('public media URL' in w for w in instagram['warnings']))

    def test_ready_to_publish_excludes_scheduled_items(self):
        self.login(self.admin)
        url = reverse('publishing:ready', kwargs={'company_id': self.company.pk})
        self.assertEqual(self.client.get(url).data['count'], 1)
        PublishJob.objects.create(
            company=self.company, content_calendar_item=self.item, social_account=self.facebook, platform='facebook',
            scheduled_at=timezone.now() + datetime.timedelta(days=1),
        )
        self.assertEqual(self.client.get(url).data['count'], 0)


class PublishTaskTests(TempMediaMixin, PlatformFixturesMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.item = self.make_item()
        self.add_creative(self.item)
        self.account = self.make_account('facebook')
        self.job = PublishJob.objects.create(
            company=self.company, content_calendar_item=self.item, social_account=self.account, platform='facebook',
            scheduled_at=timezone.now() - datetime.timedelta(minutes=1), caption='Hello',
            media=media_utils.resolve_content(self.item)[1],
        )

    def test_dispatch_queues_due_jobs(self):
        with patch('apps.publishing.tasks.publish_job.delay', return_value=Mock(id='t')) as mock_delay:
            self.assertEqual(dispatch_due_publish_jobs(), 1)
        mock_delay.assert_called_once_with(self.job.id)
        self.job.refresh_from_db()
        self.assertEqual(self.job.status, PublishJob.Status.QUEUED)

    def test_dispatch_respects_kill_switch(self):
        settings_obj = PlatformSettings.load()
        settings_obj.publishing_enabled = False
        settings_obj.save()
        with patch('apps.publishing.tasks.publish_job.delay') as mock_delay:
            self.assertEqual(dispatch_due_publish_jobs(), 0)
        mock_delay.assert_not_called()

    def _run(self):
        PublishJob.objects.filter(pk=self.job.pk).update(status=PublishJob.Status.QUEUED)
        publish_job.apply(args=[self.job.pk])
        self.job.refresh_from_db()
        self.item.refresh_from_db()

    def test_successful_publish_marks_item_published_and_notifies(self):
        publisher = Mock()
        publisher.publish.return_value = PublishResult('123_456', 'https://www.facebook.com/123_456')
        with patch('apps.publishing.platforms.get_publisher', return_value=publisher):
            self._run()
        self.assertEqual(self.job.status, PublishJob.Status.PUBLISHED)
        self.assertEqual(self.job.external_post_id, '123_456')
        self.assertEqual(self.item.status, ContentCalendarItem.Status.PUBLISHED)
        self.assertTrue(Notification.objects.filter(
            recipient=self.client_user, notification_type=Notification.NotificationType.CONTENT_PUBLISHED,
        ).exists())
        self.assertTrue(self.item.review_events.filter(action=ContentReviewEvent.Action.PUBLISHED).exists())

    def test_retryable_failure_is_rescheduled_with_backoff(self):
        publisher = Mock()
        publisher.publish.side_effect = PublishError('rate limited', retryable=True)
        with patch('apps.publishing.platforms.get_publisher', return_value=publisher):
            self._run()
        self.assertEqual(self.job.status, PublishJob.Status.SCHEDULED)
        self.assertEqual(self.job.attempts, 1)
        self.assertGreater(self.job.scheduled_at, timezone.now())
        self.assertEqual(len(self.job.error_log), 1)

    def test_auth_failure_fails_job_and_expires_account(self):
        publisher = Mock()
        publisher.publish.side_effect = PublishError('token expired', retryable=False, auth_error=True)
        with patch('apps.publishing.platforms.get_publisher', return_value=publisher):
            self._run()
        self.assertEqual(self.job.status, PublishJob.Status.FAILED)
        self.account.refresh_from_db()
        self.assertEqual(self.account.status, SocialAccount.Status.EXPIRED)
        self.assertTrue(Notification.objects.filter(
            recipient=self.admin, notification_type=Notification.NotificationType.PUBLISHING_FAILED,
        ).exists())
        self.assertEqual(self.item.status, ContentCalendarItem.Status.APPROVED)

    def test_job_is_never_published_twice(self):
        publisher = Mock()
        publisher.publish.return_value = PublishResult('1', '')
        with patch('apps.publishing.platforms.get_publisher', return_value=publisher):
            self._run()
            publish_job.apply(args=[self.job.pk])  # already PUBLISHED - claim fails
        self.assertEqual(publisher.publish.call_count, 1)


class AutoScheduleOnApprovalTests(TempMediaMixin, PlatformFixturesMixin, APITestCase):
    def test_approval_schedules_connected_accounts_when_enabled(self):
        settings_obj = PlatformSettings.load()
        settings_obj.auto_schedule_on_approval = True
        settings_obj.save()
        item = self.make_item(status=ContentCalendarItem.Status.PENDING_APPROVAL, platforms=['facebook'])
        self.add_creative(item)
        self.make_account('facebook')
        self.make_account('linkedin', account_id='777')  # not one of the item's platforms

        self.login(self.client_user)
        response = self.client.post(reverse('content_calendar:item-approve', kwargs={'company_id': self.company.pk, 'pk': item.pk}))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        jobs = PublishJob.objects.filter(content_calendar_item=item)
        self.assertEqual(jobs.count(), 1)
        self.assertEqual(jobs.get().platform, 'facebook')

    def test_no_jobs_when_disabled(self):
        item = self.make_item(status=ContentCalendarItem.Status.PENDING_APPROVAL, platforms=['facebook'])
        self.add_creative(item)
        self.make_account('facebook')
        self.login(self.client_user)
        self.client.post(reverse('content_calendar:item-approve', kwargs={'company_id': self.company.pk, 'pk': item.pk}))
        self.assertFalse(PublishJob.objects.exists())


class PlatformPublisherTests(TempMediaMixin, PlatformFixturesMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.item = self.make_item()
        self.add_creative(self.item)
        _, self.media, _ = media_utils.resolve_content(self.item)

    def _response(self, payload, status_code=200, headers=None):
        response = Mock(status_code=status_code, headers=headers or {})
        response.json.return_value = payload
        response.text = str(payload)
        return response

    def test_facebook_image_post_uploads_the_file(self):
        account = self.make_account('facebook', account_id='PAGE1')
        job = PublishJob(platform='facebook', post_type='image', caption='Hi', media=self.media)
        with patch('apps.publishing.platforms.httpx.request', return_value=self._response({'id': 'P', 'post_id': 'PAGE1_9'})) as mock_request:
            result = FacebookPublisher(account).publish(job)
        self.assertEqual(result.external_id, 'PAGE1_9')
        args, kwargs = mock_request.call_args
        self.assertTrue(args[1].endswith('/PAGE1/photos'))
        self.assertIn('source', kwargs['files'])
        self.assertEqual(kwargs['data']['caption'], 'Hi')

    @override_settings(PUBLIC_MEDIA_BASE_URL='https://cdn.example.com/media')
    def test_instagram_container_flow(self):
        account = self.make_account('instagram', account_id='IG1')
        job = PublishJob(platform='instagram', post_type='image', caption='Hi', media=self.media)
        responses = [
            self._response({'id': 'C1'}),                       # create container
            self._response({'status_code': 'FINISHED'}),        # poll
            self._response({'id': 'M1'}),                       # media_publish
            self._response({'permalink': 'https://instagram.com/p/x'}),
        ]
        with patch('apps.publishing.platforms.httpx.request', side_effect=responses) as mock_request:
            result = InstagramPublisher(account).publish(job)
        self.assertEqual(result.external_id, 'M1')
        self.assertEqual(result.url, 'https://instagram.com/p/x')
        create_kwargs = mock_request.call_args_list[0].kwargs
        self.assertTrue(create_kwargs['data']['image_url'].startswith('https://cdn.example.com/media/'))

    @override_settings(PUBLIC_MEDIA_BASE_URL='', BACKEND_PUBLIC_URL='http://localhost:8000')
    def test_instagram_rejects_non_public_media_urls(self):
        account = self.make_account('instagram', account_id='IG1')
        job = PublishJob(platform='instagram', post_type='image', caption='Hi', media=self.media)
        with self.assertRaises(PublishError) as ctx:
            InstagramPublisher(account).publish(job)
        self.assertFalse(ctx.exception.retryable)

    def test_meta_rate_limit_is_retryable_and_token_error_is_auth(self):
        account = self.make_account('facebook', account_id='PAGE1')
        job = PublishJob(platform='facebook', post_type='text', caption='Hi', media=[])
        with patch('apps.publishing.platforms.httpx.request',
                   return_value=self._response({'error': {'code': 4, 'message': 'limit'}}, status_code=400)):
            with self.assertRaises(PublishError) as ctx:
                FacebookPublisher(account).publish(job)
        self.assertTrue(ctx.exception.retryable)
        with patch('apps.publishing.platforms.httpx.request',
                   return_value=self._response({'error': {'code': 190, 'message': 'expired'}}, status_code=400)):
            with self.assertRaises(PublishError) as ctx:
                FacebookPublisher(account).publish(job)
        self.assertTrue(ctx.exception.auth_error)
        self.assertFalse(ctx.exception.retryable)


class CaptionAndFormattingTests(TestCase):
    def test_linkedin_commentary_escapes_reserved_characters_and_links_hashtags(self):
        text = linkedin_commentary('Big sale (50% off) #Diwali')
        self.assertIn('\\(50% off\\)', text)
        self.assertIn('{hashtag|\\#|Diwali}', text)

    def test_public_url_detection(self):
        self.assertFalse(media_utils.is_publicly_reachable('http://localhost:8000/media/a.png'))
        self.assertFalse(media_utils.is_publicly_reachable('http://192.168.1.4/media/a.png'))
        self.assertTrue(media_utils.is_publicly_reachable('https://abc.trycloudflare.com/media/a.png'))


class ClientPagePermissionDefaultsTests(TestCase):
    def test_new_pages_are_granted_by_default(self):
        for page in ('publishing', 'analytics', 'reports', 'subscription'):
            self.assertIn(page, ClientProfile.Page.values)


class InstagramImagePreparationTests(TempMediaMixin, PlatformFixturesMixin, TestCase):
    @override_settings(PUBLIC_MEDIA_BASE_URL='https://cdn.example.com/media')
    def test_png_portrait_is_converted_to_a_4x5_jpeg(self):
        import io

        from django.core.files.base import ContentFile
        from django.core.files.storage import default_storage
        from PIL import Image

        from tests.helpers import png_bytes

        item = self.make_item()
        _, variations = self.add_creative(item)
        variation = variations[0]
        variation.image.save('tall.png', ContentFile(png_bytes(size=(200, 300))), save=True)

        url = media_utils.instagram_image_url({'kind': 'image', 'source': 'variation', 'id': variation.id})

        self.assertTrue(url.startswith('https://cdn.example.com/media/publishing/instagram/'))
        name = url.split('/media/', 1)[1]
        with default_storage.open(name, 'rb') as handle:
            prepared = Image.open(io.BytesIO(handle.read()))
            self.assertEqual(prepared.format, 'JPEG')
            self.assertAlmostEqual(prepared.width / prepared.height, 0.8, places=2)
