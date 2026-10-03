"""Examinations, mark entry and computed results."""

from __future__ import annotations

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.urls import reverse

from academics.models import Course, Semester, Subject
from core.models import TimeStampedModel
from students.models import Student


class Exam(TimeStampedModel):
    class ExamType(models.TextChoices):
        UNIT = "UNIT", "Unit Test"
        INTERNAL = "INTERNAL", "Internal Assessment"
        MIDTERM = "MIDTERM", "Mid Term"
        SEMESTER = "SEMESTER", "Semester Exam"
        PRACTICAL = "PRACTICAL", "Practical Exam"
        VIVA = "VIVA", "Viva Voce"
        SUPPLEMENT = "SUPPLEMENT", "Supplementary Exam"
        FINAL = "FINAL", "Final Exam"

    name = models.CharField(max_length=150)
    code = models.CharField(max_length=30, unique=True, db_index=True)
    exam_type = models.CharField(max_length=15, choices=ExamType.choices, default=ExamType.SEMESTER)
    course = models.ForeignKey(Course, on_delete=models.PROTECT, related_name="exams")
    semester = models.ForeignKey(Semester, on_delete=models.PROTECT, related_name="exams")
    academic_year = models.CharField(max_length=20, blank=True)
    start_date = models.DateField()
    end_date = models.DateField()
    total_marks = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    passing_marks = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    passing_percentage = models.DecimalField(
        max_digits=5, decimal_places=2, default=40, help_text="Minimum overall percentage to pass."
    )
    is_published = models.BooleanField(default=False, db_index=True)
    results_published = models.BooleanField(default=False)
    allow_marks_entry = models.BooleanField(default=True)
    description = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="exams_created",
    )

    class Meta:
        verbose_name = "exam"
        verbose_name_plural = "exams"
        ordering = ["-start_date", "name"]
        indexes = [
            models.Index(fields=["course", "semester"], name="exam_course_sem_idx"),
            models.Index(fields=["start_date", "end_date"], name="exam_date_idx"),
        ]

    def __str__(self):
        return f"{self.code} - {self.name}"

    def get_absolute_url(self):
        return reverse("exams:exam_detail", args=[self.pk])

    def clean(self):
        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise ValidationError({"end_date": "End date cannot be before the start date."})
        if self.passing_percentage is not None and not (0 < float(self.passing_percentage) <= 100):
            raise ValidationError({"passing_percentage": "Passing percentage must be between 0 and 100."})
        if self.total_marks and self.passing_marks and self.passing_marks > self.total_marks:
            raise ValidationError({"passing_marks": "Passing marks cannot exceed total marks."})

    @property
    def department(self):
        return self.course.department if self.course_id else None

    @property
    def subject_count(self):
        return self.exam_subjects.count()

    @property
    def result_count(self):
        return self.results.count()

    @property
    def status_badge(self):
        from django.utils import timezone

        today = timezone.localdate()
        if self.results_published:
            return "success"
        if today < self.start_date:
            return "info"
        if self.start_date <= today <= self.end_date:
            return "warning"
        return "secondary"

    def recalculate(self, publish: bool | None = None):
        from exams.services import recalculate_exam_results

        result = recalculate_exam_results(self)
        if publish is not None:
            self.results_published = publish
            self.save(update_fields=["results_published", "updated_at"])
        return result

    def delete(self, *args, **kwargs):
        if self.results.exists():
            raise ValidationError(
                f"'{self.name}' cannot be deleted because {self.results.count()} result(s) exist."
            )
        return super().delete(*args, **kwargs)


class ExamSubject(models.Model):
    """A subject included in an exam, with its own maximum marks."""

    exam = models.ForeignKey(Exam, on_delete=models.CASCADE, related_name="exam_subjects")
    subject = models.ForeignKey(
        Subject, on_delete=models.PROTECT, related_name="exam_subjects"
    )
    max_marks = models.DecimalField(max_digits=7, decimal_places=2, default=100)
    exam_date = models.DateField(null=True, blank=True)
    exam_time = models.CharField(max_length=60, blank=True)
    venue = models.CharField(max_length=100, blank=True)
    instructions = models.CharField(max_length=255, blank=True)

    class Meta:
        verbose_name = "exam subject"
        verbose_name_plural = "exam subjects"
        ordering = ["subject__code"]
        constraints = [
            models.UniqueConstraint(fields=["exam", "subject"], name="uniq_exam_subject")
        ]

    def __str__(self):
        return f"{self.exam.code} - {self.subject.code}"

    @property
    def pass_marks(self):
        exam = self.exam
        if exam and exam.passing_percentage:
            return round(float(self.max_marks) * float(exam.passing_percentage) / 100, 2)
        return 0.0

    @property
    def subject_name(self):
        return self.subject.name

    @property
    def subject_code(self):
        return self.subject.code

    @property
    def credits(self):
        return self.subject.credits


class MarkEntry(models.Model):
    exam = models.ForeignKey(Exam, on_delete=models.CASCADE, related_name="mark_entries")
    exam_subject = models.ForeignKey(
        ExamSubject, on_delete=models.CASCADE, related_name="mark_entries"
    )
    student = models.ForeignKey(
        Student, on_delete=models.PROTECT, related_name="mark_entries"
    )
    marks_obtained = models.DecimalField(
        max_digits=7, decimal_places=2, null=True, blank=True
    )
    is_absent = models.BooleanField(default=False)
    remarks = models.CharField(max_length=200, blank=True)
    entered_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="marks_entered",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "mark entry"
        verbose_name_plural = "mark entries"
        ordering = ["exam_subject__subject__code", "student__student_id"]
        indexes = [
            models.Index(fields=["exam", "student"], name="mark_exam_student_idx"),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["exam_subject", "student"], name="uniq_mark_exam_subject_student"
            )
        ]

    def __str__(self):
        return f"{self.student.student_id} - {self.exam_subject.subject.code}: {self.display_marks}"

    def clean(self):
        max_marks = self.exam_subject.max_marks
        marks = self.marks_obtained
        if self.is_absent:
            if marks not in (None, 0):
                raise ValidationError(
                    {"marks_obtained": "Marks cannot be entered for an absent student."}
                )
            return
        if marks is None:
            return
        if marks < 0:
            raise ValidationError({"marks_obtained": "Marks cannot be negative."})
        if marks > max_marks:
            raise ValidationError(
                {"marks_obtained": f"Marks cannot exceed the maximum ({max_marks})."}
            )

    @property
    def display_marks(self):
        if self.is_absent:
            return "Absent"
        return "-" if self.marks_obtained is None else self.marks_obtained

    @property
    def percentage(self):
        if self.is_absent or self.marks_obtained is None or not self.exam_subject.max_marks:
            return 0.0
        return round(
            (float(self.marks_obtained) / float(self.exam_subject.max_marks)) * 100, 2
        )

    @property
    def is_pass(self):
        if self.is_absent:
            return False
        if self.marks_obtained is None:
            return False
        return float(self.marks_obtained) >= float(self.exam_subject.pass_marks)


class Result(models.Model):
    """Computed result sheet for one student in one exam."""

    exam = models.ForeignKey(Exam, on_delete=models.CASCADE, related_name="results")
    student = models.ForeignKey(
        Student, on_delete=models.PROTECT, related_name="results"
    )
    total_marks = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    max_marks = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    percentage = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    grade = models.CharField(max_length=3, blank=True)
    grade_point = models.DecimalField(max_digits=4, decimal_places=2, default=0)
    is_pass = models.BooleanField(default=False)
    failed_subjects = models.PositiveSmallIntegerField(default=0)
    absent_subjects = models.PositiveSmallIntegerField(default=0)
    calculated_at = models.DateTimeField(auto_now=True)
    published = models.BooleanField(default=False)

    class Meta:
        verbose_name = "result"
        verbose_name_plural = "results"
        ordering = ["-percentage"]
        constraints = [
            models.UniqueConstraint(fields=["exam", "student"], name="uniq_result_exam_student")
        ]
        indexes = [
            models.Index(fields=["grade", "percentage"], name="result_grade_idx"),
        ]

    def __str__(self):
        return f"{self.student.full_name} - {self.exam.code}: {self.grade} ({self.percentage}%)"

    def get_absolute_url(self):
        return reverse("exams:result_detail", args=[self.pk])

    @property
    def result_badge(self):
        return "success" if self.is_pass else "danger"

    @property
    def grade_class(self):
        from exams.services import grade_description

        return grade_description(self.grade)
