from rest_framework import generics

from common.permissions import IsAdmin

from .models import ActivityLog
from .serializers import ActivityLogSerializer


class ActivityLogListView(generics.ListAPIView):
    """Admin: the platform-wide audit trail (Epic 18), newest first.

    Filterable by `company`, `module`, `user` and free-text `search` (matches
    action/description) so an admin can narrow a company's history or trace
    one person's actions without paging through everything.
    """

    serializer_class = ActivityLogSerializer
    permission_classes = [IsAdmin]

    def get_queryset(self):
        queryset = ActivityLog.objects.select_related('user', 'company')

        company_id = self.request.query_params.get('company')
        if company_id:
            queryset = queryset.filter(company_id=company_id)

        module = self.request.query_params.get('module')
        if module:
            queryset = queryset.filter(module=module)

        user_id = self.request.query_params.get('user')
        if user_id:
            queryset = queryset.filter(user_id=user_id)

        search = self.request.query_params.get('search', '').strip()
        if search:
            from django.db.models import Q

            queryset = queryset.filter(Q(action__icontains=search) | Q(description__icontains=search))

        return queryset
