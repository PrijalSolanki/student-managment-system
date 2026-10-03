"""Core models: audit trail and institute level settings."""

from __future__ import annotations

from django.conf import settings
from django.db import models
from django.urls import reverse
from django.utils import timezone


class TimeStampedModel(models.Model):
    """Abstract base providing created/updated timestamps."""

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class SiteSetting(TimeStampedModel):
    """Singleton row holding institute branding / academic configuration."""

    institute_name = models.CharField(max_length=200, default="Springfield Institute of Technology")
    institute_code = models.CharField(max_length=20, default="SIT", blank=True)
    address = models.TextField(blank=True)
    city = models.CharField(max_length=100, blank=True)
    state = models.CharField(max_length=100, blank=True)
    pincode = models.CharField(max_length=10, blank=True)
    phone = models.CharField(max_length=20, blank=True)
    email = models.EmailField(blank=True)
    website = models.URLField(blank=True)
    logo = models.ImageField(upload_to="branding/", blank=True, null=True)
    academic_year = models.CharField(max_length=20, default="2024-2025")
    current_semester = models.PositiveSmallIntegerField(default=1)
    pass_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=40,
        help_text="Minimum overall percentage required to pass.",
    )
    attendance_shortage_percentage = models.DecimalField(
        max_digits=5, decimal_places=2, default=75
    )
    currency_symbol = models.CharField(max_length=10, default="₹")
    receipt_prefix = models.CharField(max_length=10, default="RCPT")
    id_card_validity_months = models.PositiveSmallIntegerField(default=12)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="setting_updates",
    )

    class Meta:
        verbose_name = "site setting"
        verbose_name_plural = "site settings"

    def __str__(self):
        return self.institute_name

    def save(self, *args, **kwargs):
        self.pk = 1  # enforce singleton
        super().save(*args, **kwargs)

    @classmethod
    def load(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


class AuditLog(models.Model):
    """Activity / audit trail for every meaningful change in the system."""

    class Action(models.TextChoices):
        CREATE = "CREATE", "Create"
        UPDATE = "UPDATE", "Update"
        DELETE = "DELETE", "Delete"
        VIEW = "VIEW", "View"
        LOGIN = "LOGIN", "Login"
        LOGOUT = "LOGOUT", "Logout"
        LOGIN_FAILED = "LOGIN_FAILED", "Login failed"
        EXPORT = "EXPORT", "Export"
        PRINT = "PRINT", "Print"
        PAYMENT = "PAYMENT", "Payment"
        PROMOTE = "PROMOTE", "Promote"
        UPLOAD = "UPLOAD", "Upload"
        DOWNLOAD = "DOWNLOAD", "Download"
        STATUS_CHANGE = "STATUS_CHANGE", "Status change"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_logs",
    )
    username_snapshot = models.CharField(max_length=150, blank=True)
    action = models.CharField(max_length=20, choices=Action.choices, db_index=True)
    module = models.CharField(max_length=50, blank=True, db_index=True)
    record_type = models.CharField(max_length=50, blank=True)
    record_id = models.CharField(max_length=64, blank=True, db_index=True)
    record_repr = models.CharField(max_length=255, blank=True)
    description = models.TextField(blank=True)
    changes = models.JSONField(blank=True, null=True)
    http_method = models.CharField(max_length=10, blank=True)
    path = models.CharField(max_length=255, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=255, blank=True)
    status_code = models.PositiveSmallIntegerField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        verbose_name = "audit log"
        verbose_name_plural = "audit logs"
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(fields=["module", "action"], name="audit_module_action_idx"),
            models.Index(fields=["user", "created_at"], name="audit_user_created_idx"),
        ]

    def __str__(self):
        return f"{self.get_action_display()} {self.module} {self.record_repr}".strip()

    def get_absolute_url(self):
        if self.pk:
            return reverse("core:audit_detail", args=[self.pk])
        return ""

    @property
    def icon(self):
        return {
            self.Action.CREATE: "bi-plus-circle",
            self.Action.UPDATE: "bi-pencil-square",
            self.Action.DELETE: "bi-trash",
            self.Action.LOGIN: "bi-box-arrow-in-right",
            self.Action.LOGOUT: "bi-box-arrow-right",
            self.Action.LOGIN_FAILED: "bi-shield-exclamation",
            self.Action.EXPORT: "bi-download",
            self.Action.PRINT: "bi-printer",
            self.Action.PAYMENT: "bi-cash-coin",
            self.Action.PROMOTE: "bi-arrow-up-circle",
            self.Action.UPLOAD: "bi-cloud-arrow-up",
            self.Action.DOWNLOAD: "bi-cloud-arrow-down",
            self.Action.VIEW: "bi-eye",
            self.Action.STATUS_CHANGE: "bi-toggle-on",
        }.get(self.action, "bi-activity")

    @property
    def badge_class(self):
        return {
            self.Action.CREATE: "bg-success",
            self.Action.UPDATE: "bg-primary",
            self.Action.DELETE: "bg-danger",
            self.Action.LOGIN: "bg-info",
            self.Action.LOGOUT: "bg-secondary",
            self.Action.LOGIN_FAILED: "bg-danger",
            self.Action.EXPORT: "bg-dark",
            self.Action.PRINT: "bg-dark",
            self.Action.PAYMENT: "bg-success",
            self.Action.PROMOTE: "bg-warning",
            self.Action.UPLOAD: "bg-info",
            self.Action.DOWNLOAD: "bg-info",
            self.Action.VIEW: "bg-secondary",
            self.Action.STATUS_CHANGE: "bg-warning",
        }.get(self.action, "bg-secondary")
