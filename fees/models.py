"""Fee structure, invoices (fee records) and payments."""

from __future__ import annotations

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.urls import reverse
from django.utils import timezone

from academics.models import Course, Department, Semester
from core.models import TimeStampedModel
from core.utils import generate_code
from students.models import Student


class FeeType(TimeStampedModel):
    """A named charge such as tuition, hostel or library."""

    name = models.CharField(max_length=80, unique=True)
    code = models.CharField(max_length=20, unique=True, blank=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    is_mandatory = models.BooleanField(default=True)

    class Meta:
        verbose_name = "fee type"
        verbose_name_plural = "fee types"
        ordering = ["name"]

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse("fees:fee_type_list")

    def save(self, *args, **kwargs):
        if not self.code:
            self.code = generate_code("FT", FeeType, width=3)
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        if self.fee_records.exists():
            raise ValidationError(
                f"'{self.name}' cannot be deleted because it is used by "
                f"{self.fee_records.count()} fee record(s)."
            )
        return super().delete(*args, **kwargs)


class FeeStructure(TimeStampedModel):
    """Default amount of a fee type for a course/semester/department."""

    fee_type = models.ForeignKey(
        FeeType, on_delete=models.PROTECT, related_name="structures"
    )
    course = models.ForeignKey(
        Course, on_delete=models.CASCADE, null=True, blank=True, related_name="fee_structures"
    )
    semester = models.ForeignKey(
        Semester, on_delete=models.CASCADE, null=True, blank=True, related_name="fee_structures"
    )
    department = models.ForeignKey(
        Department,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="fee_structures",
    )
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    frequency = models.CharField(max_length=20, default="SEMESTER")
    academic_year = models.CharField(max_length=20, blank=True)
    is_active = models.BooleanField(default=True)
    description = models.CharField(max_length=255, blank=True)

    class Meta:
        verbose_name = "fee structure"
        verbose_name_plural = "fee structures"
        ordering = ["fee_type__name", "-academic_year"]
        constraints = [
            models.UniqueConstraint(
                fields=["fee_type", "course", "semester", "academic_year"],
                name="uniq_fee_structure_scope",
            )
        ]

    def __str__(self):
        scope = self.course.name if self.course_id else (self.department.name if self.department_id else "All")
        return f"{self.fee_type.name} - {scope} = {self.amount}"

    def students_queryset(self):
        """Students this structure applies to (scope based)."""
        queryset = Student.objects.filter(status=Student.Status.ACTIVE)
        if self.course_id:
            queryset = queryset.filter(course=self.course)
        elif self.department_id:
            queryset = queryset.filter(department=self.department)
        if self.semester_id:
            queryset = queryset.filter(semester=self.semester)
        return queryset.select_related("course", "semester", "department").order_by("student_id")

    def scope_label(self):
        parts = []
        if self.department_id:
            parts.append(self.department.name)
        if self.course_id:
            parts.append(self.course.name)
        if self.semester_id:
            parts.append(f"Semester {self.semester.number}")
        return " / ".join(parts) or "All students"

    def delete(self, *args, **kwargs):
        if self.billed_records.exists():
            raise ValidationError(
                "This fee structure has already been billed and cannot be deleted. "
                "Deactivate it instead."
            )
        return super().delete(*args, **kwargs)


class FeeRecord(TimeStampedModel):
    """An invoice raised against a student."""

    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        PARTIAL = "PARTIAL", "Partially Paid"
        PAID = "PAID", "Paid"
        OVERDUE = "OVERDUE", "Overdue"
        CANCELLED = "CANCELLED", "Cancelled"

    invoice_no = models.CharField(max_length=30, unique=True, db_index=True)
    student = models.ForeignKey(
        Student, on_delete=models.PROTECT, related_name="fee_records"
    )
    fee_type = models.ForeignKey(FeeType, on_delete=models.PROTECT, related_name="fee_records")
    fee_structure = models.ForeignKey(
        FeeStructure,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="billed_records",
    )
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    discount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    due_date = models.DateField()
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING, db_index=True)
    academic_year = models.CharField(max_length=20, blank=True)
    notes = models.CharField(max_length=255, blank=True)
    is_carried_forward = models.BooleanField(default=False)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="fee_records_created",
    )

    class Meta:
        verbose_name = "fee record"
        verbose_name_plural = "fee records"
        ordering = ["-due_date", "-created_at"]
        indexes = [
            models.Index(fields=["student", "status"], name="fee_student_status_idx"),
            models.Index(fields=["due_date", "status"], name="fee_due_status_idx"),
        ]

    def __str__(self):
        return f"{self.invoice_no} - {self.student.full_name} ({self.net_amount})"

    def get_absolute_url(self):
        return reverse("fees:fee_record_detail", args=[self.pk])

    def save(self, *args, **kwargs):
        if not self.invoice_no:
            self.invoice_no = generate_code("INV", FeeRecord, field="invoice_no", width=6)
        self.refresh_status()
        super().save(*args, **kwargs)

    def clean(self):
        if self.discount and self.amount and self.discount > self.amount:
            raise ValidationError({"discount": "Discount cannot exceed the fee amount."})

    def delete(self, *args, **kwargs):
        if self.payments.exists():
            raise ValidationError(
                f"Invoice '{self.invoice_no}' has {self.payments.count()} payment(s) and cannot "
                "be deleted. Cancel it instead."
            )
        return super().delete(*args, **kwargs)

    # ------------------------------------------------------------------ derived
    @property
    def net_amount(self):
        return round(float(self.amount or 0) - float(self.discount or 0), 2)

    @property
    def paid_amount(self):
        total = sum(
            float(payment.amount) for payment in self.payments.all() if not payment.is_cancelled
        )
        return round(total, 2)

    @property
    def remaining_amount(self):
        return round(max(0.0, self.net_amount - self.paid_amount), 2)

    @property
    def payment_percentage(self):
        if not self.net_amount:
            return 100.0
        return round((self.paid_amount / self.net_amount) * 100, 2)

    @property
    def is_overdue(self):
        from django.utils import timezone

        return self.due_date < timezone.localdate() and self.remaining_amount > 0

    @property
    def days_overdue(self):
        from django.utils import timezone

        if not self.is_overdue:
            return 0
        return (timezone.localdate() - self.due_date).days

    @property
    def status_badge(self):
        return {
            self.Status.PAID: "success",
            self.Status.PARTIAL: "info",
            self.Status.PENDING: "warning",
            self.Status.OVERDUE: "danger",
            self.Status.CANCELLED: "secondary",
        }.get(self.status, "secondary")

    def refresh_status(self):
        """Recompute the status from the payments already recorded."""
        if self.status == self.Status.CANCELLED:
            return self.status
        paid = sum(
            float(payment.amount)
            for payment in (self.payments.all() if self.pk else [])
            if not payment.is_cancelled
        )
        net = round(float(self.amount or 0) - float(self.discount or 0), 2)
        if net <= 0:
            self.status = self.Status.PAID
        elif paid <= 0:
            from django.utils import timezone

            self.status = (
                self.Status.OVERDUE
                if self.due_date and self.due_date < timezone.localdate()
                else self.Status.PENDING
            )
        elif paid + 0.005 >= net:
            self.status = self.Status.PAID
        else:
            self.status = self.Status.PARTIAL
        return self.status


class Payment(TimeStampedModel):
    """Money received against one or more invoices."""

    class Method(models.TextChoices):
        CASH = "CASH", "Cash"
        BANK = "BANK", "Bank Transfer"
        CHEQUE = "CHEQUE", "Cheque"
        CARD = "CARD", "Card"
        MOBILE = "MOBILE", "Mobile Banking"
        ONLINE = "ONLINE", "Online Gateway"

    receipt_no = models.CharField(max_length=30, unique=True, db_index=True)
    student = models.ForeignKey(
        Student, on_delete=models.PROTECT, related_name="payments"
    )
    fee_record = models.ForeignKey(
        FeeRecord,
        on_delete=models.PROTECT,
        related_name="payments",
        null=True,
        blank=True,
        help_text="Leave empty to settle several invoices at once.",
    )
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    payment_date = models.DateField(default=timezone.localdate)
    method = models.CharField(max_length=10, choices=Method.choices, default=Method.CASH)
    reference_no = models.CharField(max_length=60, blank=True)
    remarks = models.CharField(max_length=255, blank=True)
    is_cancelled = models.BooleanField(default=False)
    received_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="payments_received",
    )

    class Meta:
        verbose_name = "payment"
        verbose_name_plural = "payments"
        ordering = ["-payment_date", "-created_at"]
        indexes = [
            models.Index(fields=["payment_date", "method"], name="payment_date_method_idx"),
        ]

    def __str__(self):
        return f"{self.receipt_no} - {self.student.full_name} ({self.amount})"

    def get_absolute_url(self):
        return reverse("fees:payment_detail", args=[self.pk])

    def save(self, *args, **kwargs):
        if not self.receipt_no:
            from core.utils import unique_receipt_number

            self.receipt_no = unique_receipt_number()
        super().save(*args, **kwargs)

    def clean(self):
        if self.amount is not None and self.amount <= 0:
            raise ValidationError({"amount": "Payment amount must be greater than zero."})

    def delete(self, *args, **kwargs):
        if self.is_cancelled:
            return super().delete(*args, **kwargs)
        raise ValidationError(
            "Payments cannot be deleted once recorded. Cancel the payment instead so the "
            "audit trail is preserved."
        )

    @property
    def applied(self):
        if not self.fee_record_id:
            return "Multiple invoices"
        return self.fee_record.invoice_no

    @property
    def status_badge(self):
        return "secondary" if self.is_cancelled else "success"

    def cancel(self):
        self.is_cancelled = True
        self.save(update_fields=["is_cancelled", "updated_at"])
        if self.fee_record_id:
            self.fee_record.refresh_status()
            self.fee_record.save(update_fields=["status", "updated_at"])