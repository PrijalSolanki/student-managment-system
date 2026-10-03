"""Academic master data: departments, semesters, batches, courses, subjects."""

from __future__ import annotations

from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.urls import reverse
from django.utils.text import slugify

from core.models import TimeStampedModel
from core.validators import validate_code


class Department(TimeStampedModel):
    code = models.CharField(
        max_length=10, unique=True, db_index=True, validators=[validate_code], help_text="e.g. CSE"
    )
    name = models.CharField(max_length=120, unique=True)
    description = models.TextField(blank=True)
    hod = models.CharField(
        max_length=120,
        blank=True,
        help_text="Head of Department (name of the faculty member).",
    )
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=20, blank=True)
    established_year = models.PositiveSmallIntegerField(null=True, blank=True)
    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        verbose_name = "department"
        verbose_name_plural = "departments"
        ordering = ["name"]
        indexes = [models.Index(fields=["name"], name="dept_name_idx")]

    def __str__(self):
        return f"{self.code} - {self.name}"

    def get_absolute_url(self):
        return reverse("academics:department_detail", args=[self.pk])

    def save(self, *args, **kwargs):
        if self.code:
            self.code = slugify(self.code.replace(" ", "")).upper()[:10]
        super().save(*args, **kwargs)

    def clean(self):
        if self.established_year and self.established_year > 2100:
            raise ValidationError({"established_year": "Enter a valid year."})

    @property
    def student_count(self):
        return self.students.count()

    @property
    def teacher_count(self):
        return self.teachers.count()

    @property
    def course_count(self):
        return self.courses.count()

    @property
    def head(self):
        return getattr(self, "head_teacher", None)


class Semester(models.Model):
    number = models.PositiveSmallIntegerField(unique=True, validators=[MinValueValidator(1)])
    name = models.CharField(max_length=40, blank=True)
    is_current = models.BooleanField(default=False)

    class Meta:
        verbose_name = "semester"
        verbose_name_plural = "semesters"
        ordering = ["number"]

    def __str__(self):
        return self.name or f"Semester {self.number}"

    def save(self, *args, **kwargs):
        if not self.name:
            self.name = f"Semester {self.number}"
        super().save(*args, **kwargs)

    @classmethod
    def current(cls):
        obj = cls.objects.filter(is_current=True).first()
        if obj:
            return obj
        return cls.objects.order_by("number").first()


class Batch(TimeStampedModel):
    """Student intake batch, e.g. ``2022-2026``."""

    name = models.CharField(max_length=30, unique=True, help_text="e.g. 2022-2026")
    start_year = models.PositiveSmallIntegerField()
    end_year = models.PositiveSmallIntegerField()
    department = models.ForeignKey(
        Department,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="batches",
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = "batch"
        verbose_name_plural = "batches"
        ordering = ["-start_year"]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if self.start_year and self.end_year and self.end_year < self.start_year:
            raise ValidationError({"end_year": "End year must be after the start year."})
        if not self.name and self.start_year and self.end_year:
            self.name = f"{self.start_year}-{self.end_year}"
        super().save(*args, **kwargs)

    @property
    def duration_years(self):
        if self.start_year and self.end_year:
            return self.end_year - self.start_year
        return 0

    @property
    def student_count(self):
        return self.students.count()


class Course(TimeStampedModel):
    name = models.CharField(max_length=140)
    code = models.CharField(max_length=20, unique=True, db_index=True, validators=[validate_code])
    department = models.ForeignKey(
        Department, on_delete=models.PROTECT, related_name="courses"
    )
    level = models.CharField(
        max_length=30,
        choices=[
            ("UG", "Under Graduate"),
            ("PG", "Post Graduate"),
            ("DIPLOMA", "Diploma"),
            ("CERTIFICATE", "Certificate"),
        ],
        default="UG",
    )
    duration_years = models.PositiveSmallIntegerField(default=4, validators=[MinValueValidator(1)])
    total_semesters = models.PositiveSmallIntegerField(default=8)
    annual_fee = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    description = models.TextField(blank=True)
    eligibility = models.CharField(max_length=255, blank=True)
    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        verbose_name = "course"
        verbose_name_plural = "courses"
        ordering = ["name"]
        indexes = [
            models.Index(fields=["department", "is_active"], name="course_dept_active_idx")
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["code", "department"], name="uniq_course_code_per_department"
            )
        ]

    def __str__(self):
        return f"{self.code} - {self.name}"

    def get_absolute_url(self):
        return reverse("academics:course_detail", args=[self.pk])

    def save(self, *args, **kwargs):
        if self.code:
            self.code = slugify(self.code.replace(" ", "")).upper()[:20]
        super().save(*args, **kwargs)

    @property
    def student_count(self):
        return self.students.count()

    @property
    def subject_count(self):
        return self.subjects.count()

    def delete(self, *args, **kwargs):
        blockers = []
        if self.students.exists():
            blockers.append(f"{self.students.count()} student(s)")
        if self.subjects.exists():
            blockers.append(f"{self.subjects.count()} subject(s)")
        if blockers:
            raise ValidationError(
                f"'{self.name}' cannot be deleted because it is linked to "
                f"{' and '.join(blockers)}. Mark the course as inactive instead."
            )
        return super().delete(*args, **kwargs)


class Subject(TimeStampedModel):
    name = models.CharField(max_length=140)
    code = models.CharField(max_length=20, unique=True, db_index=True, validators=[validate_code])
    course = models.ForeignKey(Course, on_delete=models.PROTECT, related_name="subjects")
    semester = models.ForeignKey(Semester, on_delete=models.PROTECT, related_name="subjects")
    credits = models.PositiveSmallIntegerField(default=4, validators=[MinValueValidator(1)])
    subject_type = models.CharField(
        max_length=20,
        choices=[("THEORY", "Theory"), ("PRACTICAL", "Practical"), ("BOTH", "Theory + Practical")],
        default="THEORY",
    )
    lecture_hours = models.PositiveSmallIntegerField(default=4)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        verbose_name = "subject"
        verbose_name_plural = "subjects"
        ordering = ["semester__number", "name"]
        indexes = [
            models.Index(fields=["course", "semester"], name="subject_course_sem_idx"),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["course", "semester", "name"], name="uniq_subject_per_course_sem"
            )
        ]

    def __str__(self):
        return f"{self.code} - {self.name}"

    def get_absolute_url(self):
        return reverse("academics:subject_detail", args=[self.pk])

    def save(self, *args, **kwargs):
        if self.code:
            self.code = slugify(self.code.replace(" ", "")).upper()[:20]
        super().save(*args, **kwargs)

    def clean(self):
        if self.course_id and self.semester_id and self.semester.number > self.course.total_semesters:
            raise ValidationError(
                {"semester": f"Semester cannot exceed {self.course.total_semesters} for this course."}
            )

    @property
    def assigned_teachers(self):
        from teachers.models import Teacher

        return Teacher.objects.filter(
            subject_assignments__subject=self, is_active=True
        ).distinct()

    @property
    def teacher_names(self) -> str:
        """Comma separated list of teachers assigned to this subject."""
        names = [
            assignment.teacher.full_name
            for assignment in self.assignments.select_related("teacher")
        ]
        return ", ".join(names)

    @property
    def student_count(self):
        return self.course.students.count()
