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

        tracked = [f for f in serializer.validated_data]
        before = {f: str(getattr(serializer.instance, f)) for f in tracked}
        instance = serializer.save(updated_by=self.request.user)
        after = {f: str(getattr(instance, f)) for f in tracked}
        changed = [f for f in tracked if before[f] != after[f]]
        log_activity(
            module=ActivityLog.Module.SETTINGS, action='Platform settings updated',
            description=', '.join(changed)[:500],
            old_value={f: before[f] for f in changed} or None,
            new_value={f: after[f] for f in changed} or None,
            request=self.request,
        )
