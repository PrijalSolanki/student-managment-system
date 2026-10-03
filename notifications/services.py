"""Notification delivery helpers (in-app + optional email)."""

from __future__ import annotations

import datetime as dt

from django.conf import settings
from django.core.mail import send_mail
from django.db.models import Q
from django.utils import timezone

from notifications.models import Notification, NotificationRead, StudentAnnouncement


def notifications_for_student(student) -> list:
    """Active notices relevant to a single student (they have no login)."""
    queryset = Notification.objects.filter(
        is_active=True
    ).filter(Q(expires_at__isnull=True) | Q(expires_at__gte=timezone.now()))
    queryset = queryset.filter(
        Q(audience=Notification.Audience.ALL)
        | Q(audience=Notification.Audience.STUDENT)
        | Q(audience=Notification.Audience.COURSE, course_id=student.course_id)
        | Q(audience=Notification.Audience.DEPARTMENT, department_id=student.department_id)
        | Q(audience=Notification.Audience.BATCH, batch_id=student.batch_id)
    ).filter(
        Q(course__isnull=True) | Q(course_id=student.course_id),
        Q(department__isnull=True) | Q(department_id=student.department_id),
        Q(batch__isnull=True) | Q(batch_id=student.batch_id),
    )
    return list(queryset.distinct().order_by("-is_pinned", "-created_at")[:25])


def notify_student(student, title: str, message: str, created_by=None, send_email: bool = False) -> StudentAnnouncement:
    """Pin a notice directly onto a student's profile."""
    announcement = StudentAnnouncement.objects.create(
        student=student,
        title=title,
        message=message,
        created_by=created_by,
    )
    if send_email and student.email:
        send_mail(
            subject=title,
            message=message,
            from_email=getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@example.com"),
            recipient_list=[student.email],
            fail_silently=True,
        )
    return announcement


def broadcast(notification, students=None) -> int:
    """Optionally copy an announcement onto every targeted student profile."""
    if notification.audience not in {
        Notification.Audience.STUDENT,
        Notification.Audience.COURSE,
        Notification.Audience.DEPARTMENT,
        Notification.Audience.BATCH,
        Notification.Audience.ALL,
    }:
        return 0
    from students.models import Student

    queryset = Student.objects.filter(status=Student.Status.ACTIVE)
    if notification.audience == Notification.Audience.COURSE:
        queryset = queryset.filter(course_id=notification.course_id)
    elif notification.audience == Notification.Audience.DEPARTMENT:
        queryset = queryset.filter(department_id=notification.department_id)
    elif notification.audience == Notification.Audience.BATCH:
        queryset = queryset.filter(batch_id=notification.batch_id)

    created = 0
    for student in queryset:
        _, was_created = StudentAnnouncement.objects.get_or_create(
            student=student,
            notification=notification,
            defaults={
                "title": notification.title,
                "message": notification.body,
                "created_by": notification.created_by,
            },
        )
        created += int(was_created)
    return created


def mark_all_read(user) -> int:
    return Notification.objects.mark_all_read(user)


def unread_list(user, limit: int = 8) -> list:
    return list(
        Notification.objects.unread_for(user)
        .select_related("created_by")
        .order_by("-is_pinned", "-created_at")[:limit]
    )


def read_history(user, limit: int = 25) -> list:
    return list(
        NotificationRead.objects.filter(user=user)
        .select_related("notification")
        .order_by("-read_at")[:limit]
    )


def expiring_soon(days: int = 3) -> list:
    """Notifications whose expiry is approaching (used by the dashboard)."""
    moment = timezone.now() + dt.timedelta(days=days)
    return list(
        Notification.objects.filter(
            is_active=True, expires_at__isnull=False, expires_at__lte=moment
        ).order_by("expires_at")
    )


def cleanup_expired() -> int:
    """Deactivate notifications whose expiry date has passed."""
    return Notification.objects.filter(
        is_active=True, expires_at__isnull=False, expires_at__lt=timezone.now()
    ).update(is_active=False)


__all__ = [
    "notifications_for_student",
    "notify_student",
    "broadcast",
    "mark_all_read",
    "unread_list",
    "read_history",
    "expiring_soon",
    "cleanup_expired",
]