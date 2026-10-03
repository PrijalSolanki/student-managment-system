"""Automatic audit-trail signal receivers.

Every create / update / delete on the tracked models is recorded in
``core.AuditLog`` with the acting user, module, record and a diff of the
changed fields.
"""

from __future__ import annotations

import logging

from django.db.models.signals import post_delete, post_save, pre_save
from django.dispatch import receiver
from django.utils import timezone

from core.middleware import get_client_ip, get_current_request, get_current_user
from core.models import AuditLog

logger = logging.getLogger("sms.audit")

TRACKED_MODELS = {}
_MAX_DIFF_FIELDS = 25
_HIDDEN_FIELDS = {"password", "last_login"}


def register(model, module: str, label: str = ""):
    TRACKED_MODELS[model] = {"module": module, "label": label or model.__name__}


def _describe(instance) -> str:
    for attr in ("student_id", "employee_id", "code", "name", "title", "username",
                 "first_name", "__str__"):
        value = getattr(instance, attr, None)
        if callable(value):
            try:
                return str(value())[:255]
            except Exception:  # pragma: no cover
                continue
        if value:
            return f"{value}"[:255]
    return f"{instance.__class__.__name__} #{instance.pk}"


def _snapshot(instance):
    """Capture changed field values before the row is written."""
    model = instance.__class__
    if instance._state.adding or not instance.pk:
        return None
    try:
        old = model.objects.filter(pk=instance.pk).first()
    except Exception:  # pragma: no cover - table may not exist yet
        return None
    if old is None:
        return None
    diff = {}
    for field in model._meta.concrete_fields:
        if field.name in _HIDDEN_FIELDS:
            continue
        try:
            new_value = getattr(instance, field.attname)
            old_value = getattr(old, field.attname)
        except Exception:  # pragma: no cover
            continue
        if new_value != old_value:
            if len(diff) >= _MAX_DIFF_FIELDS:
                diff["..."] = "truncated"
                break
            diff[field.name] = {"from": _clean(old_value), "to": _clean(new_value)}
    return diff or None


def _clean(value):
    if value in (None, ""):
        return ""
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)[:120]


def _record(action, instance, changes=None, description=""):
    request = get_current_request()
    user = get_current_user()
    meta = TRACKED_MODELS.get(instance.__class__, {})
    module = meta.get("module", instance.__class__.__module__.split(".")[0])
    try:
        return AuditLog.objects.create(
            user=user,
            username_snapshot=getattr(user, "username", "") or "system",
            action=action,
            module=module,
            record_type=instance.__class__.__name__,
            record_id=str(instance.pk or ""),
            record_repr=_describe(instance),
            description=description or f"{instance.__class__.__name__} {action.lower()}d",
            changes=changes,
            http_method=getattr(request, "method", "") or "",
            path=getattr(request, "path", "")[:255] or "",
            ip_address=get_client_ip(request),
            user_agent=(getattr(request, "META", {}) or {}).get("HTTP_USER_AGENT", "")[:255],
            created_at=timezone.now(),
        )
    except Exception as exc:  # pragma: no cover - never break the request
        logger.warning("Audit log write failed: %s", exc)
        return None


@receiver(pre_save)
def audit_pre_save(sender, instance, **kwargs):
    if sender not in TRACKED_MODELS:
        return
    try:
        instance.__audit_changes__ = _snapshot(instance)
    except Exception as exc:  # pragma: no cover
        logger.warning("Audit snapshot failed for %s: %s", sender, exc)
        instance.__audit_changes__ = None


@receiver(post_save)
def audit_post_save(sender, instance, created, **kwargs):
    if sender not in TRACKED_MODELS:
        return
    action = AuditLog.Action.CREATE if created else AuditLog.Action.UPDATE
    changes = None if created else getattr(instance, "__audit_changes__", None)
    description = (
        f"Created {sender._meta.verbose_name} {_describe(instance)}"
        if created
        else f"Updated {sender._meta.verbose_name} {_describe(instance)}"
    )
    _record(action, instance, changes=changes, description=description)


@receiver(post_delete)
def audit_post_delete(sender, instance, **kwargs):
    if sender not in TRACKED_MODELS:
        return
    _record(
        AuditLog.Action.DELETE,
        instance,
        description=f"Deleted {sender._meta.verbose_name} {_describe(instance)}",
    )


def register_all():
    """Wire up every tracked model (called from ``CoreConfig.ready``)."""
    from django.apps import apps

    mapping = {
        "accounts": ["User"],
        "academics": ["Department", "Course", "Subject", "Semester", "Batch"],
        "teachers": ["Teacher", "SubjectAssignment"],
        "students": ["Student", "StudentPromotion", "StudentDocument"],
        "attendance": ["Attendance"],
        "exams": ["Exam", "MarkEntry", "Result"],
        "fees": ["FeeType", "FeeRecord", "Payment"],
        "notifications": ["Notification"],
    }
    for app_label, model_names in mapping.items():
        try:
            app_config = apps.get_app_config(app_label)
        except LookupError:  # pragma: no cover
            continue
        for model_name in model_names:
            try:
                model = app_config.get_model(model_name)
            except LookupError:  # pragma: no cover
                continue
            register(model, app_label, model_name)
