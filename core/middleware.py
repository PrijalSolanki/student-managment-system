"""Request scoped middleware.

Stores the active user/request in a thread local so that model level signal
receivers (see :mod:`core.signals`) can attribute changes to a user without
having to thread the request through every service call.
"""

from __future__ import annotations

import threading

_local = threading.local()


class RequestAuditMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        _local.request = request
        user = getattr(request, "user", None)
        _local.user = user if getattr(user, "is_authenticated", False) else None
        try:
            return self.get_response(request)
        finally:
            _local.request = None
            _local.user = None


def get_current_request():
    return getattr(_local, "request", None)


def get_current_user():
    return getattr(_local, "user", None)


def set_current_user(user):
    _local.user = user if getattr(user, "is_authenticated", False) else None


def get_client_ip(request):
    """Best effort client IP, honouring a single reverse-proxy header."""
    if request is None:
        return None
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if forwarded:
        return forwarded.split(",")[0].strip() or None
    return request.META.get("REMOTE_ADDR") or None
