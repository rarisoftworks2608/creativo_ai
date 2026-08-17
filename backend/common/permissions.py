"""Role-based permission classes shared across all apps."""

from rest_framework.permissions import BasePermission

from apps.authentication.models import User


class IsAdmin(BasePermission):
    """Allows access only to platform Admin users."""

    message = 'This action is restricted to admin users.'

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.role == User.Role.ADMIN
        )


class IsClient(BasePermission):
    """Allows access only to Client users."""

    message = 'This action is restricted to client users.'

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.role == User.Role.CLIENT
        )


class IsSelfOrAdmin(BasePermission):
    """Allows a user to act on their own record, or an admin to act on anyone's."""

    def has_object_permission(self, request, view, obj):
        if request.user.role == User.Role.ADMIN:
            return True
        return obj == request.user
