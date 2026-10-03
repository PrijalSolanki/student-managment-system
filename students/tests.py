"""Tests for enrolment, promotions and per-student summary services."""

from datetime import date
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from students.models import Student, StudentPromotion
from students.services import promote_student, student_attendance_summary, student_fee_summary


class StudentTestBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        from accounts.models import User
        from academics.models import Batch, Course, Department, Semester

        cls.user = User.objects.create_superuser(username="stu_admin", password="x")
        cls.department = Department.objects.create(code="CSE", name="Computer Science")
        cls.course = Course.objects.create(
            code="BTCS", name="B.Tech CS", department=cls.department, total_semesters=8
        )
        cls.batch = Batch.objects.create(
            name="2023-2027", start_year=2023, end_year=2027, department=cls.department
        )
        cls.semester_1 = Semester.objects.create(number=1, name="Semester 1")
        cls.semester_2 = Semester.objects.create(number=2, name="Semester 2")

    def make_student(self, first="Aarav", email=None):
        return Student.objects.create(
            first_name=first,
            last_name="Test",
            email=email or f"{first.lower()}@example.com",
            phone="9812300030",
            date_of_birth=date(2004, 5, 5),
            admission_date=date(2023, 7, 1),
            department=self.department,
            course=self.course,
            batch=self.batch,
            semester=self.semester_1,
            created_by=self.user,
        )


class StudentModelTests(StudentTestBase):
    def test_student_id_is_generated(self):
        student = self.make_student()
        self.assertTrue(student.student_id.startswith("STU"))
        self.assertEqual(student.student_id, "STU00001")

    def test_student_ids_are_unique(self):
        first = self.make_student("Aarav")
        second = self.make_student("Riya", email="riya@example.com")
        self.assertNotEqual(first.student_id, second.student_id)

    def test_full_name_is_readable(self):
        self.assertEqual(self.make_student().full_name, "Aarav Test")

    def test_active_queryset_filters_status(self):
        active = self.make_student("Active")
        dropped = self.make_student("Dropped", email="dropped@example.com")
        dropped.status = Student.Status.DROPPED
        dropped.save()
        self.assertIn(active, Student.objects.active())
        self.assertNotIn(dropped, Student.objects.active())


class PromotionTests(StudentTestBase):
    def test_promotion_moves_student_and_records_history(self):
        student = self.make_student()
        promotion = promote_student(
            student,
            to_semester=self.semester_2,
            promotion_type="SEMESTER",
            reason="Cleared semester 1",
            promoted_by=self.user,
        )
        student.refresh_from_db()
        self.assertEqual(student.semester, self.semester_2)
        self.assertEqual(promotion.from_semester, self.semester_1)
        self.assertEqual(promotion.to_semester, self.semester_2)
        self.assertEqual(StudentPromotion.objects.filter(student=student).count(), 1)

    def test_promotion_keeps_course_when_not_changed(self):
        student = self.make_student()
        promote_student(student, to_semester=self.semester_2)
        student.refresh_from_db()
        self.assertEqual(student.course, self.course)
        self.assertEqual(student.department, self.department)


class StudentSummaryTests(StudentTestBase):
    def test_attendance_summary_percentages(self):
        from datetime import timedelta

        from attendance.models import Attendance

        student = self.make_student()
        subject = self.course.subjects.create(
            code="CS301", name="Algorithms", course=self.course, credits=4
        )
        today = timezone.localdate()
        for offset, status in enumerate(["PRESENT", "PRESENT", "ABSENT", "PRESENT"]):
            Attendance.objects.create(
                student=student,
                subject=subject,
                date=today - timedelta(days=offset),
                status=status,
            )
        summary = student_attendance_summary(student)
        self.assertEqual(summary["total"], 4)
        self.assertEqual(summary["present"], 3)
        self.assertEqual(summary["absent"], 1)
        self.assertEqual(summary["percentage"], 75.0)

    def test_fee_summary_totals(self):
        from fees.models import FeeType
        from fees.services import record_payment

        student = self.make_student()
        fee_type = FeeType.objects.create(name="Tuition Fee", code="TUI")
        first = self._invoice(student, fee_type, Decimal("1000"))
        second = self._invoice(student, fee_type, Decimal("2000"))
        record_payment(student, Decimal("1000"), fee_record=first)

        summary = student_fee_summary(student)
        self.assertEqual(summary["billed"], 3000.0)
        self.assertEqual(summary["paid"], 1000.0)
        self.assertEqual(summary["pending"], 2000.0)
        self.assertEqual(summary["records"], 2)
        self.assertEqual(second.paid_amount, 0.0)

    def _invoice(self, student, fee_type, amount):
        from datetime import timedelta

        from fees.models import FeeRecord

        return FeeRecord.objects.create(
            student=student,
            fee_type=fee_type,
            amount=amount,
            due_date=date.today() + timedelta(days=30),
        )