"""Daily student attendance per subject."""

from __future__ import annotations

from django.conf import settings
from django.db import models

from academics.models import Subject
from students.models import Student
from teachers.models import Teacher


class Attendance(models.Model):
    class Status(models.TextChoices):
        PRESENT = "PRESENT", "Present"
        ABSENT = "ABSENT", "Absent"
        LEAVE = "LEAVE", "On Leave"

    student = models.ForeignKey(
        Student, on_delete=models.PROTECT, related_name="attendance_records"
    )
    subject = models.ForeignKey(
        Subject, on_delete=models.PROTECT, related_name="attendance_records"
    )
    teacher = models.ForeignKey(
        Teacher,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="attendance_records",
    )
    date = models.DateField(db_index=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PRESENT)
    remarks = models.CharField(max_length=200, blank=True)
    marked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="attendance_marked",
    )
    marked_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "attendance"
        verbose_name_plural = "attendance records"
        ordering = ["-date", "student__first_name"]
        indexes = [
            models.Index(fields=["date", "subject"], name="att_date_subject_idx"),
            models.Index(fields=["student", "date"], name="att_student_date_idx"),
            models.Index(fields=["status", "date"], name="att_status_date_idx"),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["student", "subject", "date"], name="uniq_attendance_student_subject_date"
            )
        ]

    def __str__(self):
        return f"{self.student.student_id} - {self.subject.code} - {self.date}: {self.get_status_display()}"

    @property
    def status_badge(self):
        return {
            self.Status.PRESENT: "success",
            self.Status.ABSENT: "danger",
            self.Status.LEAVE: "warning",
        }.get(self.status, "secondary")
