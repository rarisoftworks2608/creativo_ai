from django.utils import timezone
from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Notification
from .serializers import MarkAllReadResultSerializer, NotificationSerializer, UnreadCountSerializer
from .services import mark_read


class NotificationListView(generics.ListAPIView):
    """The authenticated user's own notifications (Epic 13: Notification list / history)."""

    serializer_class = NotificationSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = Notification.objects.filter(recipient=self.request.user)
        is_read = self.request.query_params.get('is_read')
        if is_read is not None:
            queryset = queryset.filter(is_read=is_read.lower() in ('1', 'true', 'yes'))
        return queryset


class UnreadCountView(APIView):
    """Unread notification count for the topbar badge (Epic 13: Read/unread)."""

    permission_classes = [IsAuthenticated]
    serializer_class = UnreadCountSerializer

    def get(self, request):
        count = Notification.objects.filter(recipient=request.user, is_read=False).count()
        return Response({'count': count})


class MarkNotificationReadView(APIView):
    """Marks a single notification as read (Epic 13: Mark as read)."""

    permission_classes = [IsAuthenticated]
    serializer_class = NotificationSerializer

    def post(self, request, pk):
        notification = generics.get_object_or_404(Notification, pk=pk, recipient=request.user)
        mark_read(notification)
        return Response(NotificationSerializer(notification).data)


class MarkAllNotificationsReadView(APIView):
    """Marks every unread notification for this user as read in one action."""

    permission_classes = [IsAuthenticated]
    serializer_class = MarkAllReadResultSerializer

    def post(self, request):
        updated = Notification.objects.filter(recipient=request.user, is_read=False).update(
            is_read=True, read_at=timezone.now(),
        )
        return Response({'updated': updated}, status=status.HTTP_200_OK)
