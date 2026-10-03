"""Custom user model with role based access control."""

from __future__ import annotations

from django.contrib.auth.models import AbstractUser
from django.db import models
from django.urls import reverse

from core.validators import validate_phone


class User(AbstractUser):
    """Internal user (Admin / Staff) of the Student Management System."""

    class Role(models.TextChoices):
        ADMIN = "ADMIN", "Administrator"
        STAFF = "STAFF", "Staff"

    role = models.CharField(max_length=10, choices=Role.choices, default=Role.STAFF, db_index=True)
    phone = models.CharField(max_length=20, blank=True, validators=[validate_phone])
    designation = models.CharField(max_length=80, blank=True)
    department = models.ForeignKey(
        "academics.Department",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="staff_members",
    )
    avatar = models.ImageField(upload_to="avatars/", blank=True, null=True)
    address = models.TextField(blank=True)
    date_of_birth = models.DateField(null=True, blank=True)

    class Meta(AbstractUser.Meta):
        verbose_name = "user"
        verbose_name_plural = "users"
        ordering = ["first_name", "last_name", "username"]

    def __str__(self):
        return self.get_full_name() or self.username

    def get_absolute_url(self):
        return reverse("accounts:user_detail", args=[self.pk])

    def save(self, *args, **kwargs):
        if self.is_superuser:
            self.role = self.Role.ADMIN
        if self.is_staff and self.role != self.Role.ADMIN and not self.pk:
            self.role = self.Role.STAFF
        super().save(*args, **kwargs)

    # ------------------------------------------------------------------ roles
    @property
    def is_admin(self) -> bool:
        return self.is_superuser or self.role == self.Role.ADMIN

    @property
    def is_internal_user(self) -> bool:
        return bool(
            self.is_active
            and (self.role in {self.Role.ADMIN, self.Role.STAFF} or self.is_superuser)
        )

    @property
    def role_badge(self) -> str:
        return "danger" if self.is_admin else "primary"

    @property
    def display_name(self) -> str:
        return self.get_full_name() or self.username

    @property
    def initials(self) -> str:
        first = (self.first_name or self.username[:1])[:1]
        last = (self.last_name or "")[:1]
        return f"{first}{last}".upper()

    def can(self, action: str) -> bool:
        """Coarse grained capability check used by the templates."""
        capabilities = {
            "delete_records": self.is_admin,
            "manage_users": self.is_admin,
            "manage_settings": self.is_admin,
            "manage_academics": self.is_admin,
            "manage_fees": self.is_admin,
            "manage_teachers": self.is_admin,
            "manage_students": self.is_internal_user,
            "mark_attendance": self.is_internal_user,
            "manage_exams": self.is_internal_user,
            "manage_notifications": self.is_internal_user,
            "view_reports": self.is_internal_user,
            "export_data": self.is_internal_user,
            "send_notifications": self.is_internal_user,
            "promote_students": self.is_internal_user,
        }
        return capabilities.get(action, False)
