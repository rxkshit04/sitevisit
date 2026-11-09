from rest_framework.permissions import BasePermission

from .models import User


class IsStaffRole(BasePermission):
    """Any signed-in executive or head."""

    def has_permission(self, request, view):
        u = request.user
        return bool(u and u.is_authenticated and u.role in User.Role.values)


class IsHead(BasePermission):
    def has_permission(self, request, view):
        u = request.user
        return bool(u and u.is_authenticated and u.role == User.Role.HEAD)