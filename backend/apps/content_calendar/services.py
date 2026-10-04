"""Content review lifecycle helpers (Epic 09: Content Approval Workflow).

The single write path for ContentReviewEvent, plus the hooks the generation tasks
(creative/video) and the publishing app call when a calendar item moves through its
lifecycle - each records history and fans the event out to WhatsApp (Epic 12).
"""

import logging

from .models import ContentCalendarItem, ContentReviewEvent

logger = logging.getLogger(__name__)


def _actor_role(actor):
    if actor is None:
        return ContentReviewEvent.ActorRole.SYSTEM
    return ContentReviewEvent.ActorRole.ADMIN if actor.is_admin else ContentReviewEvent.ActorRole.CLIENT


def record_review_event(item, action, *, actor=None, feedback='', metadata=None):
    return ContentReviewEvent.objects.create(
        item=item,
        company_id=item.company_id,
        action=action,
        actor=actor,
        actor_role=_actor_role(actor),
        feedback=feedback or '',
        metadata=metadata or {},
    )


def _whatsapp(company, event, context):
    """WhatsApp is a mirror of in-app notifications - it must never break the workflow."""
    try:
        from apps.whatsapp.services import dispatch_event

        dispatch_event(company, event, context)
    except Exception:  # noqa: BLE001
        logger.exception('WhatsApp dispatch failed for event %s', event)


def content_link(item):
    return f'/companies/{item.company_id}/approvals?item={item.id}'


def submitted_for_review(item_id, *, is_regeneration=False, kind='creative', request_id=None):
    """Called by the creative/video generation tasks once content is ready for review."""
    item = ContentCalendarItem.objects.select_related('company').filter(pk=item_id).first()
    if item is None:
        return None
    action = ContentReviewEvent.Action.REGENERATED if is_regeneration else ContentReviewEvent.Action.GENERATED
    event = record_review_event(item, action, metadata={'kind': kind, 'request_id': request_id})
    _whatsapp(item.company, 'content_regenerated' if is_regeneration else 'approval_required', {
        'topic': item.topic, 'scheduled_date': item.scheduled_date.isoformat(), 'url': content_link(item),
    })
    return event


def generation_failed(item_id, message, *, kind='creative', request_id=None):
    item = ContentCalendarItem.objects.filter(pk=item_id).first()
    if item is None:
        return None
    return record_review_event(
        item, ContentReviewEvent.Action.GENERATION_FAILED, feedback=message[:2000],
        metadata={'kind': kind, 'request_id': request_id},
    )


def pending_since(item):
    """When the item last entered review - the most recent generated/regenerated event,
    falling back to updated_at for items generated before review history existed."""
    event = item.review_events.filter(
        action__in=[ContentReviewEvent.Action.GENERATED, ContentReviewEvent.Action.REGENERATED],
    ).order_by('-created_at').first()
    return event.created_at if event else item.updated_at
