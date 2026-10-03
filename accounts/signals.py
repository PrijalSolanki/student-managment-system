"""Login / logout audit logging."""

from __future__ import annotations

from django.contrib.auth.signals import (
    user_logged_in,
    user_logged_out,
    user_login_failed,
)
from django.dispatch import receiver

from core.middleware import get_client_ip
from core.models import AuditLog


def _device_info(request) -> str:
    if request is None:
        return ""
    return request.META.get("HTTP_USER_AGENT", "")[:255]


@receiver(user_logged_in)
def handle_login(sender, request, user, **kwargs):
    AuditLog.objects.create(
        user=user,
        username_snapshot=user.username,
        action=AuditLog.Action.LOGIN,
        module="accounts",
        record_type=user.__class__.__name__,
        record_id=str(user.pk),
        record_repr=user.username,
        description=f"{user.username} signed in",
        http_method=getattr(request, "method", "")[:10],
        path=getattr(request, "path", "")[:255],
        ip_address=get_client_ip(request),
        user_agent=_device_info(request),
    )


@receiver(user_logged_out)
def handle_logout(sender, request, user, **kwargs):
    if user is None:
        return
    AuditLog.objects.create(
        user=user if getattr(user, "pk", None) else None,
        username_snapshot=getattr(user, "username", ""),
        action=AuditLog.Action.LOGOUT,
        module="accounts",
        record_type=user.__class__.__name__,
        record_id=str(getattr(user, "pk", "") or ""),
        record_repr=getattr(user, "username", ""),
        description=f"{getattr(user, 'username', '')} signed out",
        http_method=getattr(request, "method", "")[:10],
        path=getattr(request, "path", "")[:255],
        ip_address=get_client_ip(request),
        user_agent=_device_info(request),
    )


@receiver(user_login_failed)
def handle_login_failed(sender, credentials, request=None, **kwargs):
    username = (credentials or {}).get("username", "")
    AuditLog.objects.create(
        user=None,
        username_snapshot=username[:150],
        action=AuditLog.Action.LOGIN_FAILED,
        module="accounts",
        record_repr=username[:255],
        description=f"Failed sign-in attempt for '{username}'",
        http_method=getattr(request, "method", "")[:10],
        path=getattr(request, "path", "")[:255],
        ip_address=get_client_ip(request),
        user_agent=_device_info(request),
    )
