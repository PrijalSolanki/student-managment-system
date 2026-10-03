"""Student records, academic promotions and uploaded documents."""

from __future__ import annotations

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.urls import reverse

from academics.models import Batch, Course, Department, Semester
from core.models import TimeStampedModel
from core.utils import avatar_initials, full_name, upload_path
from core.validators import (
    FileSizeValidator,
    validate_document,
    validate_phone,
    validate_pincode,
)


def student_photo_path(instance, filename):
    return upload_path(instance, filename, folder="students")


def document_path(instance, filename):
    return upload_path(instance, filename, folder="documents")


class StudentQuerySet(models.QuerySet):
    def active(self):
        return self.filter(status=Student.Status.ACTIVE)

    def with_details(self):
        return self.select_related("department", "course", "semester", "batch")

    def search(self, term: str):
        if not term:
            return self
        return self.filter(
            Q(student_id__icontains=term)
            | Q(first_name__icontains=term)
            | Q(last_name__icontains=term)
            | Q(email__icontains=term)
            | Q(phone__icontains=term)
            | Q(guardian_name__icontains=term)
            | Q(guardian_phone__icontains=term)
        )


class Student(TimeStampedModel):
    class Gender(models.TextChoices):
        MALE = "M", "Male"
        FEMALE = "F", "Female"
        OTHER = "O", "Other"

    class BloodGroup(models.TextChoices):
        A_POS = "A+", "A+"
        A_NEG = "A-", "A-"
        B_POS = "B+", "B+"
        B_NEG = "B-", "B-"
        O_POS = "O+", "O+"
        O_NEG = "O-", "O-"
        AB_POS = "AB+", "AB+"
        AB_NEG = "AB-", "AB-"

    class Status(models.TextChoices):
        ACTIVE = "ACTIVE", "Active"
        INACTIVE = "INACTIVE", "Inactive"
        ON_LEAVE = "ON_LEAVE", "On Leave"
        SUSPENDED = "SUSPENDED", "Suspended"
        GRADUATED = "GRADUATED", "Graduated"
        DROPPED = "DROPPED", "Dropped"

    student_id = models.CharField(
        max_length=20, unique=True, db_index=True, blank=True, help_text="Enrolment number"
    )
    first_name = models.CharField(max_length=80)
    last_name = models.CharField(max_length=80, blank=True)
    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=20, validators=[validate_phone])
    date_of_birth = models.DateField()
    gender = models.CharField(max_length=1, choices=Gender.choices, default=Gender.MALE, db_index=True)
    blood_group = models.CharField(max_length=4, choices=BloodGroup.choices, blank=True)
    nationality = models.CharField(max_length=60, default="Indian")
    religion = models.CharField(max_length=40, blank=True)
    category = models.CharField(
        max_length=30,
        choices=[
            ("GENERAL", "General"),
            ("OBC", "OBC"),
            ("SC", "SC"),
            ("ST", "ST"),
            ("EWS", "EWS"),
        ],
        blank=True,
    )
    address = models.TextField(blank=True)
    city = models.CharField(max_length=80, blank=True)
    state = models.CharField(max_length=80, blank=True)
    pincode = models.CharField(max_length=10, blank=True, validators=[validate_pincode])
    photo = models.ImageField(upload_to=student_photo_path, blank=True, null=True)
    admission_date = models.DateField(db_index=True)
    department = models.ForeignKey(
        Department, on_delete=models.PROTECT, related_name="students"
    )
    course = models.ForeignKey(Course, on_delete=models.PROTECT, related_name="students")
    semester = models.ForeignKey(
        Semester, on_delete=models.PROTECT, related_name="students"
    )
    batch = models.ForeignKey(
        Batch, on_delete=models.SET_NULL, null=True, blank=True, related_name="students"
    )
    status = models.CharField(
        max_length=12, choices=Status.choices, default=Status.ACTIVE, db_index=True
    )
    guardian_name = models.CharField(max_length=120, blank=True)
    guardian_phone = models.CharField(max_length=20, blank=True, validators=[validate_phone])
    guardian_relation = models.CharField(max_length=30, blank=True)
    emergency_contact = models.CharField(max_length=20, blank=True, validators=[validate_phone])
    previous_qualification = models.CharField(max_length=120, blank=True)
    previous_percentage = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True
    )
    scholarship = models.CharField(max_length=60, blank=True)
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="students_created",
    )

    objects = StudentQuerySet.as_manager()

    class Meta:
        verbose_name = "student"
        verbose_name_plural = "students"
        ordering = ["student_id"]
        indexes = [
            models.Index(fields=["last_name", "first_name"], name="student_name_idx"),
            models.Index(
                fields=["department", "course", "semester"], name="student_academic_idx"
            ),
            models.Index(fields=["status", "admission_date"], name="student_status_idx"),
            models.Index(fields=["email"], name="student_email_idx"),
        ]

    def __str__(self):
        return f"{self.student_id} - {self.full_name}"

    def get_absolute_url(self):
        return reverse("students:student_detail", args=[self.pk])

    def save(self, *args, **kwargs):
        if not self.student_id:
            from core.utils import generate_code

            self.student_id = generate_code("STU", Student, field="student_id", width=5)
        super().save(*args, **kwargs)

    # ------------------------------------------------------------- validation
    def clean(self):
        errors = {}
        if self.date_of_birth and self.admission_date:
            if self.date_of_birth >= self.admission_date:
                errors["date_of_birth"] = "Date of birth must be before the admission date."
            else:
                age = self.admission_date.year - self.date_of_birth.year
                if age < 15:
                    errors["date_of_birth"] = "Student must be at least 15 years old at admission."
                if age > 70:
                    errors["date_of_birth"] = "Please verify the date of birth."
        if self.course_id and self.department_id and self.course.department_id != self.department_id:
            errors["course"] = "The selected course does not belong to the chosen department."
        if self.course_id and self.semester_id:
            if self.semester.number > self.course.total_semesters:
                errors["semester"] = (
                    f"This course only runs up to semester {self.course.total_semesters}."
                )
        if self.previous_percentage is not None and not (0 <= self.previous_percentage <= 100):
            errors["previous_percentage"] = "Percentage must be between 0 and 100."
        if self.email:
            qs = Student.objects.filter(email__iexact=self.email)
            if self.pk:
                qs = qs.exclude(pk=self.pk)
            if qs.exists():
                errors["email"] = "A student with this email address already exists."
        if self.student_id:
            qs = Student.objects.filter(student_id__iexact=self.student_id)
            if self.pk:
                qs = qs.exclude(pk=self.pk)
            if qs.exists():
                errors["student_id"] = "This enrolment number is already in use."
        if errors:
            raise ValidationError(errors)

    # ------------------------------------------------------------- properties
    @property
    def full_name(self):
        return full_name(self.first_name, self.last_name)

    @property
    def initials(self):
        return avatar_initials(self.first_name, self.last_name)

    @property
    def is_active(self):
        return self.status == self.Status.ACTIVE

    @property
    def age(self):
        if not self.date_of_birth:
            return None
        from django.utils import timezone

        today = timezone.localdate()
        return (
            today.year
            - self.date_of_birth.year
            - ((today.month, today.day) < (self.date_of_birth.month, self.date_of_birth.day))
        )

    @property
    def status_badge(self):
        return {
            self.Status.ACTIVE: "success",
            self.Status.INACTIVE: "secondary",
            self.Status.ON_LEAVE: "info",
            self.Status.SUSPENDED: "warning",
            self.Status.GRADUATED: "primary",
            self.Status.DROPPED: "danger",
        }.get(self.status, "secondary")

    def delete(self, *args, **kwargs):
        blockers = []
        if self.attendance_records.exists():
            blockers.append(f"{self.attendance_records.count()} attendance record(s)")
        if self.mark_entries.exists():
            blockers.append(f"{self.mark_entries.count()} mark sheet(s)")
        if self.fee_records.exists():
            blockers.append(f"{self.fee_records.count()} fee record(s)")
        if blockers:
            raise ValidationError(
                f"{self.full_name} cannot be deleted because the record is linked to "
                f"{', '.join(blockers)}. Set the status to 'Inactive' or 'Dropped' instead."
            )
        return super().delete(*args, **kwargs)


class StudentPromotion(TimeStampedModel):
    """Audit trail of academic promotions / transfers."""

    student = models.ForeignKey(
        Student, on_delete=models.CASCADE, related_name="promotions"
    )
    from_semester = models.ForeignKey(
        Semester, on_delete=models.SET_NULL, null=True, blank=True, related_name="promotions_from"
    )
    to_semester = models.ForeignKey(
        Semester, on_delete=models.SET_NULL, null=True, blank=True, related_name="promotions_to"
    )
    from_batch = models.ForeignKey(
        Batch, on_delete=models.SET_NULL, null=True, blank=True, related_name="promotions_from"
    )
    to_batch = models.ForeignKey(
        Batch, on_delete=models.SET_NULL, null=True, blank=True, related_name="promotions_to"
    )
    from_course = models.ForeignKey(
        Course, on_delete=models.SET_NULL, null=True, blank=True, related_name="promotions_from"
    )
    to_course = models.ForeignKey(
        Course, on_delete=models.SET_NULL, null=True, blank=True, related_name="promotions_to"
    )
    from_department = models.ForeignKey(
        Department,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="promotions_from",
    )
    to_department = models.ForeignKey(
        Department,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="promotions_to",
    )
    academic_year_from = models.CharField(max_length=20, blank=True)
    academic_year_to = models.CharField(max_length=20, blank=True)
    promotion_type = models.CharField(
        max_length=20,
        choices=[
            ("SEMESTER", "Semester Promotion"),
            ("BATCH", "Batch Promotion"),
            ("COURSE_CHANGE", "Course Change"),
            ("DEPARTMENT_CHANGE", "Department Change"),
            ("REVISION", "Backlog / Revision"),
        ],
        default="SEMESTER",
    )
    reason = models.CharField(max_length=255, blank=True)
    remarks = models.TextField(blank=True)
    promoted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="student_promotions",
    )

    class Meta:
        verbose_name = "student promotion"
        verbose_name_plural = "student promotions"
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["student", "-created_at"], name="promo_student_idx")]

    def __str__(self):
        return f"{self.student.full_name}: {self.get_promotion_type_display()} ({self.created_at:%d %b %Y})"

    @property
    def summary(self):
        changes = []
        if self.from_semester_id and self.to_semester_id and self.from_semester_id != self.to_semester_id:
            changes.append(f"Semester {self.from_semester} -> {self.to_semester}")
        if self.from_batch_id and self.to_batch_id and self.from_batch_id != self.to_batch_id:
            changes.append(f"Batch {self.from_batch} -> {self.to_batch}")
        if self.from_course_id and self.to_course_id and self.from_course_id != self.to_course_id:
            changes.append(f"Course {self.from_course.code} -> {self.to_course.code}")
        if (
            self.from_department_id
            and self.to_department_id
            and self.from_department_id != self.to_department_id
        ):
            changes.append(f"Department {self.from_department.code} -> {self.to_department.code}")
        return ", ".join(changes) or "No academic change recorded"


class StudentDocument(TimeStampedModel):
    class DocumentType(models.TextChoices):
        AADHAAR = "AADHAAR", "Aadhaar / National ID"
        BIRTH_CERTIFICATE = "BIRTH_CERTIFICATE", "Birth Certificate"
        MARKSHEET = "MARKSHEET", "Previous Marksheet"
        TRANSFER_CERTIFICATE = "TRANSFER_CERTIFICATE", "Transfer Certificate"
        CASTE_CERTIFICATE = "CASTE_CERTIFICATE", "Caste / Category Certificate"
        PHOTO_ID = "PHOTO_ID", "Photo ID Card"
        OTHER = "OTHER", "Other Document"

    student = models.ForeignKey(
        Student, on_delete=models.CASCADE, related_name="documents"
    )
    document_type = models.CharField(
        max_length=25, choices=DocumentType.choices, default=DocumentType.OTHER
    )
    title = models.CharField(max_length=150)
    file = models.FileField(
        upload_to=document_path,
        validators=[
            FileSizeValidator(5),
            validate_document,
        ],
    )
    description = models.CharField(max_length=255, blank=True)
    file_size = models.PositiveIntegerField(default=0)
    content_type = models.CharField(max_length=100, blank=True)
    expiry_date = models.DateField(null=True, blank=True)
    is_verified = models.BooleanField(default=False)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="documents_uploaded",
    )

    class Meta:
        verbose_name = "student document"
        verbose_name_plural = "student documents"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["student", "document_type"], name="doc_student_type_idx")
        ]

    def __str__(self):
        return f"{self.title} ({self.get_document_type_display()})"

    def save(self, *args, **kwargs):
        if self.file:
            try:
                self.file_size = self.file.size
            except (OSError, ValueError):  # pragma: no cover
                self.file_size = 0
            self.content_type = getattr(self.file, "content_type", "") or ""
        super().save(*args, **kwargs)

    @property
    def extension(self):
        import os

        return os.path.splitext(self.file.name)[1].lower().lstrip(".")

    @property
    def size_human(self):
        from core.utils import file_size_human

        return file_size_human(self.file_size)

    @property
    def icon(self):
        return {
            "pdf": "bi-file-earmark-pdf",
            "jpg": "bi-file-earmark-image",
            "jpeg": "bi-file-earmark-image",
            "png": "bi-file-earmark-image",
            "doc": "bi-file-earmark-word",
            "docx": "bi-file-earmark-word",
            "xls": "bi-file-earmark-excel",
            "xlsx": "bi-file-earmark-excel",
        }.get(self.extension, "bi-file-earmark")

    @property
    def is_expired(self):
        from django.utils import timezone

        return bool(self.expiry_date and self.expiry_date < timezone.localdate())
