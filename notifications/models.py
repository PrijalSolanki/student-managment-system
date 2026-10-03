"""Announcements and per-user read receipts."""

from __future__ import annotations

from django.conf import settings
from django.db import models
from django.db.models import Q
from django.db.models.functions import Now
from django.urls import reverse

from core.models import TimeStampedModel
from core.utils import avatar_initials


class NotificationQuerySet(models.QuerySet):
    def active(self):
        return self.filter(is_active=True).filter(
            Q(expires_at__isnull=True) | Q(expires_at__gte=Now())
        )


class NotificationManager(models.Manager.from_queryset(NotificationQuerySet)):
    def active(self):
        return self.get_queryset().active()

    def visible_to(self, user):
        """Notifications a given internal user is allowed to see."""
        queryset = self.get_queryset().active()
        if user is None or not getattr(user, "is_authenticated", False):
            return queryset.none()
        audience = Q(audience=Notification.Audience.ALL)
        if getattr(user, "is_internal_user", False):
            audience |= Q(audience__in=[Notification.Audience.STAFF, Notification.Audience.ADMIN])
        else:
            audience |= Q(audience=Notification.Audience.STUDENT)
        return queryset.filter(audience)

    def unread_for(self, user):
        queryset = self.visible_to(user)
        if queryset is None:
            return queryset.none()
        read_ids = NotificationRead.objects.filter(user=user).values_list(
            "notification_id", flat=True
        )
        return queryset.exclude(id__in=read_ids)

    def mark_all_read(self, user) -> int:
        from django.utils import timezone

        created = 0
        for notification in list(self.unread_for(user)):
            _, was_created = NotificationRead.objects.get_or_create(
                notification=notification,
                user=user,
                defaults={"read_at": timezone.now()},
            )
            if was_created:
                Notification.objects.filter(pk=notification.pk).update(
                    read_count=models.F("read_count") + 1
                )
                created += 1
        return created


class Notification(TimeStampedModel):
    class Priority(models.TextChoices):
        LOW = "LOW", "Low"
        NORMAL = "NORMAL", "Normal"
        HIGH = "HIGH", "High"
        URGENT = "URGENT", "Urgent"

    class Audience(models.TextChoices):
        ALL = "ALL", "Everyone"
        STAFF = "STAFF", "Staff Only"
        ADMIN = "ADMIN", "Administrators"
        STUDENT = "STUDENT", "Students"
        COURSE = "COURSE", "Specific Course"
        DEPARTMENT = "DEPARTMENT", "Specific Department"
        BATCH = "BATCH", "Specific Batch"

    title = models.CharField(max_length=150)
    body = models.TextField()
    priority = models.CharField(max_length=10, choices=Priority.choices, default=Priority.NORMAL)
    audience = models.CharField(max_length=15, choices=Audience.choices, default=Audience.ALL, db_index=True)
    course = models.ForeignKey(
        "academics.Course",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="notifications",
    )
    department = models.ForeignKey(
        "academics.Department",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="notifications",
    )
    batch = models.ForeignKey(
        "academics.Batch",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="notifications",
    )
    is_pinned = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True, db_index=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    action_url = models.CharField(max_length=255, blank=True)
    attachment = models.FileField(upload_to="notifications/", blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="notifications_created",
    )
    read_count = models.PositiveIntegerField(default=0, editable=False)

    objects = NotificationManager()

    class Meta:
        verbose_name = "notification"
        verbose_name_plural = "notifications"
        ordering = ["-is_pinned", "-created_at"]
        indexes = [
            models.Index(fields=["is_active", "created_at"], name="notif_active_created_idx"),
        ]

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        if self.action_url:
            return self.action_url
        return reverse("notifications:notification_list")

    def mark_read(self, user) -> bool:
        from django.utils import timezone

        _, created = NotificationRead.objects.get_or_create(
            notification=self, user=user, defaults={"read_at": timezone.now()}
        )
        if created:
            Notification.objects.filter(pk=self.pk).update(read_count=models.F("read_count") + 1)
            self.refresh_from_db(fields=["read_count"])
        return created

    def is_read_by(self, user) -> bool:
        if not getattr(user, "is_authenticated", False):
            return False
        return NotificationRead.objects.filter(notification=self, user=user).exists()

    @property
    def badge(self):
        return {
            self.Priority.LOW: "secondary",
            self.Priority.NORMAL: "info",
            self.Priority.HIGH: "warning",
            self.Priority.URGENT: "danger",
        }.get(self.priority, "info")

    @property
    def icon(self):
        return {
            self.Priority.LOW: "bi-info-circle",
            self.Priority.NORMAL: "bi-megaphone",
            self.Priority.HIGH: "bi-exclamation-triangle",
            self.Priority.URGENT: "bi-broadcast",
        }.get(self.priority, "bi-megaphone")

    @property
    def scope_label(self):
        labels = []
        if self.department_id:
            labels.append(self.department.name)
        if self.course_id:
            labels.append(self.course.name)
        if self.batch_id:
            labels.append(self.batch.name)
        return " / ".join(labels) or self.get_audience_display()

    @property
    def author_initials(self):
        creator = self.created_by
        return avatar_initials(
            creator.first_name if creator else "", creator.last_name if creator else ""
        )


class NotificationRead(models.Model):
    notification = models.ForeignKey(
        Notification, on_delete=models.CASCADE, related_name="reads"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notification_reads"
    )
    read_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "notification read receipt"
        verbose_name_plural = "notification read receipts"
        ordering = ["-read_at"]
        constraints = [
            models.UniqueConstraint(fields=["notification", "user"], name="uniq_notification_read")
        ]

    def __str__(self):
        return f"{self.user} read '{self.notification.title}'"


class StudentAnnouncement(TimeStampedModel):
    """Notice pinned to one student profile (students have no login)."""

    student = models.ForeignKey(
        "students.Student", on_delete=models.CASCADE, related_name="announcements"
    )
    notification = models.ForeignKey(
        Notification,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="student_announcements",
    )
    title = models.CharField(max_length=150)
    message = models.TextField()
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="student_announcements_created",
    )

    class Meta:
        verbose_name = "student announcement"
        verbose_name_plural = "student announcements"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.student.student_id}: {self.title}"

    @property
    def badge(self):
        return self.notification.badge if self.notification_id else "info"