"""View mixins shared by the company-scoped apps added after the original epics
(publishing, analytics, reports, whatsapp, subscriptions).

The older apps each carry their own copy of CompanyScopedMixin (identical
behavior); new apps import this one instead of adding another copy.
"""

from django.http import Http404
from rest_framework import generics

from apps.companies.models import Company


class CompanyScopedMixin:
    """Resolves the company from the URL, 404ing if a client tries to reach a company
    that isn't theirs, or (if `required_page` is set on the view) one they haven't been
    granted access to (Epic 01: Role & Access - Access Control page; Epic 25: tenant
    isolation).
    """

    required_page = None

    def get_company(self):
        if hasattr(self, '_company_cache'):
            return self._company_cache
        company = generics.get_object_or_404(Company, pk=self.kwargs['company_id'])
        user = self.request.user
        if not user.is_admin:
            profile = getattr(user, 'client_profile', None)
            if not profile or profile.company_id != company.id:
                raise Http404
            if self.required_page and not profile.can_access(self.required_page):
                raise Http404
        self._company_cache = company
        return company


class AdminWriteMixin:
    """Lets clients read (GET/HEAD/OPTIONS) but restricts every write to admins - the
    same rule the content calendar / generation views enforce inline."""

    admin_write_message = 'Only admins can make changes here.'

    def check_permissions(self, request):
        super().check_permissions(request)
        if request.method not in ('GET', 'HEAD', 'OPTIONS') and not (
            request.user.is_authenticated and request.user.is_admin
        ):
            self.permission_denied(request, message=self.admin_write_message)
