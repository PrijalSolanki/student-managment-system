"""Teacher records and subject assignments."""

from __future__ import annotations

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.urls import reverse

from academics.models import Department, Subject
from core.models import TimeStampedModel
from core.utils import avatar_initials, full_name, upload_path
from core.validators import validate_phone, validate_pincode


def teacher_photo_path(instance, filename):
    return upload_path(instance, filename, folder="teachers")


class Teacher(TimeStampedModel):
    class Gender(models.TextChoices):
        MALE = "M", "Male"
        FEMALE = "F", "Female"
        OTHER = "O", "Other"

    class Status(models.TextChoices):
        ACTIVE = "ACTIVE", "Active"
        ON_LEAVE = "ON_LEAVE", "On Leave"
        INACTIVE = "INACTIVE", "Inactive"

    employee_id = models.CharField(max_length=20, unique=True, db_index=True, blank=True)
    first_name = models.CharField(max_length=80)
    last_name = models.CharField(max_length=80, blank=True)
    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=20, validators=[validate_phone])
    gender = models.CharField(max_length=1, choices=Gender.choices, default=Gender.MALE)
    date_of_birth = models.DateField(null=True, blank=True)
    blood_group = models.CharField(max_length=5, blank=True)
    qualification = models.CharField(max_length=120, blank=True)
    specialization = models.CharField(max_length=120, blank=True)
    designation = models.CharField(max_length=80, blank=True)
    department = models.ForeignKey(
        Department,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="teachers",
    )
    joining_date = models.DateField(null=True, blank=True)
    salary = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    address = models.TextField(blank=True)
    city = models.CharField(max_length=80, blank=True)
    state = models.CharField(max_length=80, blank=True)
    pincode = models.CharField(max_length=10, blank=True, validators=[validate_pincode])
    photo = models.ImageField(upload_to=teacher_photo_path, blank=True, null=True)
    bio = models.TextField(blank=True)
    status = models.CharField(
        max_length=10, choices=Status.choices, default=Status.ACTIVE, db_index=True
    )
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="teacher_profile",
        help_text="Optional portal login for this teacher.",
    )

    class Meta:
        verbose_name = "teacher"
        verbose_name_plural = "teachers"
        ordering = ["first_name", "last_name"]
        indexes = [
            models.Index(fields=["last_name", "first_name"], name="teacher_name_idx"),
            models.Index(fields=["department", "status"], name="teacher_dept_status_idx"),
        ]

    def __str__(self):
        return f"{self.employee_id} - {self.full_name}"

    def get_absolute_url(self):
        return reverse("teachers:teacher_detail", args=[self.pk])

    def save(self, *args, **kwargs):
        if not self.employee_id:
            from core.utils import generate_code

            self.employee_id = generate_code("TCH", Teacher, field="employee_id", width=4)
        super().save(*args, **kwargs)

    def clean(self):
        if self.date_of_birth and self.joining_date and self.date_of_birth > self.joining_date:
            raise ValidationError(
                {"date_of_birth": "Date of birth must be before the joining date."}
            )
        if self.salary and self.salary < 0:
            raise ValidationError({"salary": "Salary cannot be negative."})

    @property
    def full_name(self):
        return full_name(self.first_name, self.last_name)

    @property
    def initials(self):
        return avatar_initials(self.first_name, self.last_name)

    @property
    def subject_count(self):
        return self.assignments.count()

    @property
    def subjects(self):
        return Subject.objects.filter(assignments__teacher=self).distinct()

    @property
    def is_active(self):
        return self.status == self.Status.ACTIVE

    @property
    def experience_years(self):
        from django.utils import timezone

        if not self.joining_date:
            return 0
        today = timezone.localdate()
        return max(0, today.year - self.joining_date.year)


class SubjectAssignment(TimeStampedModel):
    """Many-to-many link between teachers and subjects."""

    teacher = models.ForeignKey(Teacher, on_delete=models.CASCADE, related_name="assignments")
    subject = models.ForeignKey(
        Subject, on_delete=models.CASCADE, related_name="assignments"
    )
    academic_year = models.CharField(max_length=20, blank=True)
    is_primary = models.BooleanField(default=True)
    remarks = models.CharField(max_length=200, blank=True)
    assigned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="subject_assignments_made",
    )

    class Meta:
        verbose_name = "subject assignment"
        verbose_name_plural = "subject assignments"
        ordering = ["subject__code"]
        constraints = [
            models.UniqueConstraint(
                fields=["teacher", "subject"], name="uniq_teacher_subject_assignment"
            )
        ]

    def __str__(self):
        return f"{self.teacher.full_name} -> {self.subject.code}"

    def clean(self):
        if (
            self.teacher_id
            and self.subject_id
            and self.teacher.department_id
            and self.teacher.department_id != self.subject.course.department_id
        ):
            raise ValidationError(
                {"teacher": "Teacher and subject belong to different departments."}
            )
