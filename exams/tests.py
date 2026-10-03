"""Tests for grading, mark entry and automatic result calculation."""

from datetime import date
from decimal import Decimal

from django.test import TestCase

from exams.models import Exam, ExamSubject, MarkEntry, Result
from exams.services import (
    calculate_grade,
    grade_description,
    grade_point,
    overall_percentage,
    rank_of_student,
    recalculate_result,
)


class GradeScaleTests(TestCase):
    def test_boundaries(self):
        self.assertEqual(calculate_grade(95)["grade"], "A+")
        self.assertEqual(calculate_grade(85)["grade"], "A")
        self.assertEqual(calculate_grade(75)["grade"], "B+")
        self.assertEqual(calculate_grade(65)["grade"], "B")
        self.assertEqual(calculate_grade(55)["grade"], "C")
        self.assertEqual(calculate_grade(45)["grade"], "D")
        self.assertEqual(calculate_grade(10)["grade"], "F")

    def test_exact_lower_bounds(self):
        self.assertEqual(calculate_grade(90)["grade"], "A+")
        self.assertEqual(calculate_grade(80)["grade"], "A")
        self.assertEqual(calculate_grade(40)["grade"], "D")

    def test_unknown_grade_is_safe(self):
        self.assertEqual(grade_description("Z"), "")
        self.assertEqual(grade_point("Z"), Decimal("0.00"))


class ResultCalculationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        from accounts.models import User
        from academics.models import Batch, Course, Department, Semester, Subject
        from students.models import Student

        user = User.objects.create_superuser(username="calc_admin", password="x")
        department = Department.objects.create(code="CSE", name="Computer Science")
        course = Course.objects.create(
            code="BTCS", name="B.Tech CS", department=department, total_semesters=8
        )
        batch = Batch.objects.create(
            name="2023-2027", start_year=2023, end_year=2027, department=department
        )
        semester = Semester.objects.create(number=1, name="Semester 1")
        subject_a = Subject.objects.create(code="CS201", name="Data Structures", course=course, credits=4)
        subject_b = Subject.objects.create(code="CS202", name="Databases", course=course, credits=4)

        cls.students = []
        for first, score_a, score_b in [
            ("Topper", 95, 90),
            ("Middle", 60, 55),
            ("Fail", 20, 30),
        ]:
            student = Student.objects.create(
                first_name=first,
                email=f"{first.lower()}@example.com",
                phone="9812300010",
                date_of_birth=date(2004, 1, 1),
                admission_date=date(2023, 7, 1),
                department=department,
                course=course,
                batch=batch,
                semester=semester,
                created_by=user,
            )
            student.demo_scores = (score_a, score_b)
            cls.students.append(student)

        cls.exam = Exam.objects.create(
            name="Mid Sem I",
            code="MID1",
            course=course,
            semester=semester,
            academic_year="2024-2025",
            start_date=date(2024, 6, 1),
            end_date=date(2024, 6, 10),
            total_marks=200,
            passing_marks=80,
            created_by=user,
        )
        cls.exam_subjects = [
            ExamSubject.objects.create(exam=cls.exam, subject=subject_a, max_marks=100, pass_marks=40),
            ExamSubject.objects.create(exam=cls.exam, subject=subject_b, max_marks=100, pass_marks=40),
        ]

    def _enter_marks(self, student, score_a, score_b):
        for exam_subject, score in zip(self.exam_subjects, [score_a, score_b]):
            MarkEntry.objects.create(
                exam=self.exam,
                exam_subject=exam_subject,
                student=student,
                marks_obtained=Decimal(str(score)),
                entered_by=self.exam.created_by,
            )

    def test_result_is_created_with_totals(self):
        topper = self.students[0]
        self._enter_marks(topper, 95, 90)
        outcome = recalculate_result(self.exam, topper)
        self.assertEqual(outcome["created"], 1)

        result = Result.objects.get(exam=self.exam, student=topper)
        self.assertEqual(result.total_marks, Decimal("185"))
        self.assertEqual(result.max_marks, Decimal("200"))
        self.assertEqual(result.percentage, Decimal("92.50"))
        self.assertEqual(result.grade, "A+")
        self.assertTrue(result.is_pass)
        self.assertEqual(result.failed_subjects, 0)

    def test_failed_subjects_are_counted(self):
        failing = self.students[2]
        self._enter_marks(failing, 20, 30)
        recalculate_result(self.exam, failing)
        result = Result.objects.get(exam=self.exam, student=failing)
        self.assertFalse(result.is_pass)
        self.assertEqual(result.failed_subjects, 2)
        self.assertEqual(result.grade, "F")

    def test_absent_subject_counts_as_absent(self):
        student = self.students[1]
        self._enter_marks(student, 60, 55)
        MarkEntry.objects.filter(
            exam=self.exam, exam_subject=self.exam_subjects[1], student=student
        ).update(is_absent=True)
        recalculate_result(self.exam, student)
        result = Result.objects.get(exam=self.exam, student=student)
        self.assertEqual(result.absent_subjects, 1)
        self.assertEqual(result.total_marks, Decimal("60"))

    def test_recalculate_updates_instead_of_duplicating(self):
        student = self.students[1]
        self._enter_marks(student, 60, 55)
        recalculate_result(self.exam, student)
        second = recalculate_result(self.exam, student)
        self.assertEqual(second["updated"], 1)
        self.assertEqual(Result.objects.filter(exam=self.exam, student=student).count(), 1)

    def test_no_exam_subjects_is_skipped(self):
        from exams.models import ExamSubject as ES

        ES.objects.filter(exam=self.exam).delete()
        outcome = recalculate_result(self.exam, self.students[0])
        self.assertEqual(outcome["skipped"], 1)

    def test_ranks_are_dense_and_one_based(self):
        for student in self.students:
            self._enter_marks(student, *student.demo_scores)
            recalculate_result(self.exam, student)
        self.assertEqual(rank_of_student(self.exam, self.students[0]), 1)
        self.assertEqual(rank_of_student(self.exam, self.students[2]), 3)

    def test_overall_percentage_averages_results(self):
        for student in self.students[:2]:
            self._enter_marks(student, *student.demo_scores)
            recalculate_result(self.exam, student)
        average = overall_percentage(self.students[0])
        self.assertGreater(average, 0)