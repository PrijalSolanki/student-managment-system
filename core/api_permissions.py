"""Shared REST framework building blocks."""

from __future__ import annotations

from rest_framework import permissions


class IsAdminOrStaff(permissions.BasePermission):
    """Allow authenticated internal users (Admin or Staff)."""

    message = "Internal staff access is required."

    def has_permission(self, request, view):
        user = request.user
        return bool(
            user
            and user.is_authenticated
            and getattr(user, "is_internal_user", False)
        )


class IsAdminUser(permissions.BasePermission):
    """Allow administrators only."""

    message = "Administrator access is required."

    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and getattr(user, "is_admin", False))


class ReadOnlyForStaff(permissions.BasePermission):
    """Staff get read-only access; admins may write."""

    def has_permission(self, request, view):
        user = request.user
        if not (user and user.is_authenticated):
            return False
        if getattr(user, "is_admin", False):
            return True
        return request.method in permissions.SAFE_METHODS


class IsOwnerOrReadOnly(permissions.BasePermission):
    """Object level permission used by document/notification endpoints."""

    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True
        user = request.user
        if getattr(user, "is_admin", False):
            return True
        owner = getattr(obj, "uploaded_by", None) or getattr(obj, "created_by", None)
        return owner_id_is_user(owner, user)


def owner_id_is_user(owner, user) -> bool:
    if owner is None:
        return True
    owner_id = getattr(owner, "pk", None) or getattr(owner, "id", None)
    return owner_id == getattr(user, "pk", None)
