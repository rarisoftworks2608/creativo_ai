"""Starting a background generation safely.

A generation request is saved (and, for an ad-hoc one, given a calendar item) before its Celery task is queued. If
the broker can't be reached at that moment, the request must not be left behind: a request that was never queued
stays "pending" forever, and its DRAFT calendar item would later be picked up by the calendar's auto-generation
sweep - generating a creative nobody asked for. So a failed enqueue undoes both and tells the person plainly.
"""

import logging

from rest_framework import status
from rest_framework.response import Response

logger = logging.getLogger(__name__)

QUEUE_UNAVAILABLE = (
    'The background worker could not be reached, so nothing was generated and no AI credit was used. '
    'Please try again in a moment.'
)


def enqueue_or_undo(enqueue, generation_request, *, created_calendar_item_id=None):
    """(queued_request, None) on success, or (None, a 503 Response) after deleting the request and the calendar
    item that was created only for it."""
    try:
        return enqueue(generation_request), None
    except Exception:  # noqa: BLE001 - any broker/transport failure
        logger.exception('Could not queue %s %s; undoing it.', type(generation_request).__name__, generation_request.pk)
        generation_request.delete()
        if created_calendar_item_id:
            from apps.content_calendar.models import ContentCalendarItem

            ContentCalendarItem.objects.filter(pk=created_calendar_item_id).delete()
        return None, Response({'detail': QUEUE_UNAVAILABLE}, status=status.HTTP_503_SERVICE_UNAVAILABLE)


def queue_failure_response():
    return Response({'detail': QUEUE_UNAVAILABLE}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
