"""Tests for attendance aggregation and bulk marking."""

from datetime import date, timedelta

from django.test import TestCase
from django.utils import timezone

from attendance.models import Attendance
from attendance.services import (
    attendance_totals,
    daily_report,
    monthly_report,
    save_bulk_attendance,
    student_report,
)


class AttendanceTestBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        from accounts.models import User
        from academics.models import Batch, Course, Department, Semester, Subject
        from students.models import Student
        from teachers.models import Teacher

        cls.user = User.objects.create_superuser(username="att_admin", password="x")
        cls.department = Department.objects.create(code="CSE", name="Computer Science")
        cls.course = Course.objects.create(
            code="BTCS", name="B.Tech CS", department=cls.department, total_semesters=8
        )
        batch = Batch.objects.create(
            name="2023-2027", start_year=2023, end_year=2027, department=cls.department
        )
        semester = Semester.objects.create(number=1, name="Semester 1")
        cls.subject = Subject.objects.create(
            code="CS301", name="Algorithms", course=cls.course, credits=4
        )
        cls.teacher = Teacher.objects.create(
            employee_id="EMP900",
            first_name="Anita",
            email="anita.attendance@example.com",
            phone="9812300050",
            department=cls.department,
        )
        cls.students = [
            Student.objects.create(
                first_name=first,
                email=f"{first.lower()}@example.com",
                phone=f"98123000{60 + index}",
                date_of_birth=date(2004, 1, 1),
                admission_date=date(2023, 7, 1),
                department=cls.department,
                course=cls.course,
                batch=batch,
                semester=semester,
                created_by=cls.user,
            )
            for index, first in enumerate(["Aarav", "Diya", "Ishaan"])
        ]


class TotalsTests(AttendanceTestBase):
    def test_totals_and_percentage(self):
        today = timezone.localdate()
        for student, status in zip(self.students, ["PRESENT", "ABSENT", "LEAVE"]):
            Attendance.objects.create(
                student=student, subject=self.subject, date=today, status=status
            )
        totals = attendance_totals(Attendance.objects.all())
        self.assertEqual(totals["total"], 3)
        self.assertEqual(totals["present"], 1)
        self.assertEqual(totals["absent"], 1)
        self.assertEqual(totals["leave"], 1)
        self.assertAlmostEqual(totals["percentage"], 33.33, places=2)

    def test_empty_queryset_is_safe(self):
        totals = attendance_totals(Attendance.objects.none())
        self.assertEqual(totals["total"], 0)
        self.assertEqual(totals["percentage"], 0.0)


class DailyReportTests(AttendanceTestBase):
    def test_rows_are_grouped_per_subject(self):
        today = timezone.localdate()
        Attendance.objects.create(
            student=self.students[0], subject=self.subject, date=today, status="PRESENT"
        )
        Attendance.objects.create(
            student=self.students[1], subject=self.subject, date=today, status="ABSENT"
        )
        rows = daily_report(today)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["subject__code"], self.subject.code)
        self.assertEqual(rows[0]["total"], 2)
        self.assertEqual(rows[0]["present"], 1)


class MonthlyReportTests(AttendanceTestBase):
    def test_month_totals(self):
        today = timezone.localdate()
        start = today.replace(day=1)
        for offset in range(2):
            Attendance.objects.create(
                student=self.students[0],
                subject=self.subject,
                date=start + timedelta(days=offset),
                status="PRESENT",
            )
        report = monthly_report(today.year, today.month)
        self.assertEqual(report["year"], today.year)
        self.assertEqual(report["month"], today.month)
        self.assertEqual(report["totals"]["total"], 2)
        self.assertEqual(report["totals"]["present"], 2)
        self.assertEqual(len(report["days"]), 2)
        self.assertEqual(report["subjects"][0]["subject_code"], self.subject.code)


class StudentReportTests(AttendanceTestBase):
    def test_percentage_for_single_student(self):
        today = timezone.localdate()
        for offset, status in enumerate(["PRESENT", "PRESENT", "ABSENT", "LEAVE"]):
            Attendance.objects.create(
                student=self.students[0],
                subject=self.subject,
                date=today - timedelta(days=offset),
                status=status,
            )
        report = student_report(self.students[0])
        self.assertEqual(report["totals"]["total"], 4)
        self.assertEqual(report["totals"]["present"], 2)
        self.assertEqual(report["totals"]["percentage"], 50.0)
        self.assertEqual(report["subjects"][0]["subject_code"], self.subject.code)
        self.assertEqual(len(report["recent"]), 4)


class BulkMarkingTests(AttendanceTestBase):
    def _entries(self, today):
        return [
            (
                student.pk,
                status,
                self.subject.pk,
                self.teacher.pk,
                today,
                "",
            )
            for student, status in zip(self.students, ["PRESENT", "ABSENT", "LEAVE"])
        ]

    def test_bulk_create_then_update(self):
        today = timezone.localdate()
        first = save_bulk_attendance(self._entries(today), self.user)
        self.assertEqual(first["created"], 3)
        self.assertEqual(Attendance.objects.count(), 3)

        second = save_bulk_attendance(self._entries(today), self.user)
        self.assertEqual(second["updated"], 3)
        self.assertEqual(Attendance.objects.count(), 3)

    def test_entries_without_status_are_skipped(self):
        today = timezone.localdate()
        entries = [
            (self.students[0].pk, "", self.subject.pk, self.teacher.pk, today, ""),
            (self.students[1].pk, "PRESENT", self.subject.pk, self.teacher.pk, today, ""),
        ]
        summary = save_bulk_attendance(entries, self.user)
        self.assertEqual(summary["created"], 1)
        self.assertEqual(Attendance.objects.count(), 1)

    def test_marking_is_scoped_to_the_given_day(self):
        yesterday = timezone.localdate() - timedelta(days=1)
        save_bulk_attendance(self._entries(yesterday), self.user)
        save_bulk_attendance(self._entries(timezone.localdate()), self.user)
        self.assertEqual(Attendance.objects.count(), 6)