"""Role based access control helpers, permission classes and view mixins."""

from __future__ import annotations

from functools import wraps

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect
from django.urls import reverse

from core.middleware import get_client_ip
from core.models import AuditLog


def log_action(
    request,
    action: str,
    module: str = "",
    obj=None,
    description: str = "",
    record_type: str = "",
    record_id: str = "",
    changes: dict | None = None,
    status_code: int | None = None,
) -> AuditLog:
    """Create an :class:`~core.models.AuditLog` entry for ``request``."""
    user = getattr(request, "user", None)
    if user is not None and not getattr(user, "is_authenticated", False):
        user = None
    record_repr = ""
    if obj is not None:
        record_repr = str(obj)[:255]
        record_type = record_type or obj.__class__.__name__
        record_id = record_id or str(getattr(obj, "pk", "") or "")
    return AuditLog.objects.create(
        user=user,
        username_snapshot=getattr(user, "username", "") or "anonymous",
        action=action,
        module=module or (obj.__class__.__name__.lower() if obj else ""),
        record_type=record_type,
        record_id=str(record_id or ""),
        record_repr=record_repr,
        description=description,
        changes=changes or None,
        http_method=request.META.get("REQUEST_METHOD", "")[:10],
        path=request.path[:255],
        ip_address=get_client_ip(request),
        user_agent=request.META.get("HTTP_USER_AGENT", "")[:255],
        status_code=status_code,
    )


def staff_required(view_func):
    """Allow any authenticated internal user (Admin or Staff)."""

    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect(f"{reverse('accounts:login')}?next={request.path}")
        if not request.user.is_internal_user:
            raise PermissionDenied("Your account cannot access the admin panel.")
        return view_func(request, *args, **kwargs)

    return _wrapped


def admin_required(view_func):
    """Restrict a view to Administrators (superusers included)."""

    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect(f"{reverse('accounts:login')}?next={request.path}")
        if not request.user.is_admin:
            messages.error(request, "Administrator privileges are required for this page.")
            raise PermissionDenied("Administrator privileges are required.")
        return view_func(request, *args, **kwargs)

    return _wrapped


class StaffRequiredMixin(LoginRequiredMixin):
    """Requires an authenticated Admin/Staff user."""

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        if not request.user.is_internal_user:
            raise PermissionDenied("Your account cannot access the admin panel.")
        return super().dispatch(request, *args, **kwargs)


class AdminRequiredMixin(StaffRequiredMixin):
    """Requires the Administrator role."""

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        if not request.user.is_admin:
            messages.error(
                request, "Administrator privileges are required for this action."
            )
            raise PermissionDenied("Administrator privileges are required.")
        return super().dispatch(request, *args, **kwargs)


class PermissionRequiredMixin(StaffRequiredMixin):
    """Django-model-permission aware mixin (``permission_required``)."""

    permission_required: str | list[str] = ""

    def get_required_permissions(self, request):
        if isinstance(self.permission_required, str):
            return [self.permission_required]
        return list(self.permission_required)

    def has_permission(self):
        user = self.request.user
        if user.is_admin:
            return True
        return user.has_perms(self.get_required_permissions(self.request))

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        if not request.user.is_internal_user:
            raise PermissionDenied
        if not self.has_permission():
            raise PermissionDenied("You do not have permission to perform this action.")
        return super().dispatch(request, *args, **kwargs)


class AuditMixin:
    """Write an audit entry when a tracked view is rendered."""

    audit_action = AuditLog.Action.VIEW
    audit_module = ""

    def get_audit_module(self):
        return self.audit_module or self.__class__.__module__.split(".")[0]

    def get_audit_object(self):
        return None

    def get_audit_description(self):
        return ""

    def after_audit(self):
        return None

    def dispatch(self, request, *args, **kwargs):
        response = super().dispatch(request, *args, **kwargs)
        if 200 <= getattr(response, "status_code", 500) < 400:
            try:
                log_action(
                    request,
                    self.audit_action,
                    module=self.get_audit_module(),
                    obj=self.get_audit_object(),
                    description=self.get_audit_description(),
                    status_code=response.status_code,
                )
            except Exception:  # pragma: no cover - auditing must never break a page
                pass
            self.after_audit()
        return response
