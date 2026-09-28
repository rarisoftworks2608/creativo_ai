from rest_framework import generics

from common.permissions import IsAdmin

from .models import PlatformSettings
from .serializers import PlatformSettingsSerializer


class PlatformSettingsView(generics.RetrieveUpdateAPIView):
    """Admin: view or update the platform-wide settings singleton (Epic 19)."""

    serializer_class = PlatformSettingsSerializer
    permission_classes = [IsAdmin]

    def get_object(self):
        return PlatformSettings.load()

    def perform_update(self, serializer):
        from apps.activity_log.models import ActivityLog
        from apps.activity_log.services import log_activity

        serializer.save(updated_by=self.request.user)
        log_activity(
            module=ActivityLog.Module.SETTINGS, action='Platform settings updated', request=self.request,
        )
