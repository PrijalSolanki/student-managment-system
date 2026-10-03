"""``python manage.py seed_demo`` — realistic sample data for demos/tests.

Requires ``bootstrap`` to have been run first (departments, course, semesters,
subjects and the ``admin`` user must exist). Every generator is idempotent:
objects are looked up by their natural keys before being created, so the
command can be re-run without duplicating rows.
"""

from __future__ import annotations

import random
from datetime import date, timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

TEACHERS = [
    {
        "employee_id": "EMP001",
        "first_name": "Anita",
        "last_name": "Sharma",
        "email": "anita.sharma@example.com",
        "phone": "9812300001",
        "gender": "F",
        "qualification": "Ph.D. Computer Science",
        "specialization": "Data Structures",
        "designation": "Professor",
    },
    {
        "employee_id": "EMP002",
        "first_name": "Rajesh",
        "last_name": "Menon",
        "email": "rajesh.menon@example.com",
        "phone": "9812300002",
        "gender": "M",
        "qualification": "M.Tech Computer Science",
        "specialization": "Databases",
        "designation": "Associate Professor",
    },
    {
        "employee_id": "EMP003",
        "first_name": "Fatima",
        "last_name": "Khan",
        "email": "fatima.khan@example.com",
        "phone": "9812300003",
        "gender": "F",
        "qualification": "M.Tech Information Technology",
        "specialization": "Operating Systems",
        "designation": "Assistant Professor",
    },
]

STUDENTS = [
    ("Aarav", "Sharma", "M", "GENERAL", 0),
    ("Diya", "Patel", "F", "OBC", 1),
    ("Ishaan", "Reddy", "M", "GENERAL", 2),
    ("Kavya", "Nair", "F", "SC", 3),
    ("Rohan", "Gupta", "M", "OBC", 4),
    ("Sneha", "Iyer", "F", "GENERAL", 5),
    ("Vihaan", "Joshi", "M", "ST", 6),
    ("Zoya", "Khan", "F", "EWS", 7),
]

NOTIFICATIONS = [
    {
        "title": "Mid-Semester Examinations Timetable",
        "body": "The mid-semester examination timetable is now published on the exams page.",
        "priority": "HIGH",
        "audience": "ALL",
        "is_pinned": True,
    },
    {
        "title": "Library Week",
        "body": "Library week starts Monday. New arrivals and issue desks are open all week.",
        "priority": "NORMAL",
        "audience": "ALL",
        "is_pinned": False,
    },
    {
        "title": "Fee Payment Deadline",
        "body": "Semester fees must be cleared before the last working day of this month.",
        "priority": "URGENT",
        "audience": "COURSE",
        "is_pinned": True,
    },
]


class Command(BaseCommand):
    help = "Populate the database with realistic demo data (teachers, students, attendance, exams, fees)."

    def add_arguments(self, parser):
        parser.add_argument("--random-seed", type=int, default=20240101, help="RNG seed for reproducible data.")

    @transaction.atomic
    def handle(self, *args, **options):
        from accounts.models import User
        from academics.models import Course, Department, Semester, Subject
        from attendance.models import Attendance
        from core.models import SiteSetting
        from exams.models import Exam, ExamSubject, MarkEntry
        from exams.services import recalculate_exam_results
        from fees.models import FeeRecord, FeeStructure, FeeType
        from fees.services import bulk_generate_invoices, pay_oldest_first
        from notifications.models import Notification
        from students.models import Student
        from teachers.models import SubjectAssignment, Teacher

        rng = random.Random(options["random_seed"])
        user = User.objects.filter(is_superuser=True).order_by("pk").first()
        if user is None:
            raise CommandError("No superuser found. Run `python manage.py bootstrap` first.")

        site = SiteSetting.load()
        academic_year = site.academic_year

        department = Department.objects.filter(code="CSE").first()
        course = Course.objects.filter(code="BTCS").first()
        if department is None or course is None:
            raise CommandError(
                "Base academics missing. Run `python manage.py bootstrap` first."
            )
        semesters = list(Semester.objects.filter(number__lte=4).order_by("number"))
        subjects = list(Subject.objects.filter(course=course).order_by("code"))
        if not semesters or not subjects:
            raise CommandError("No semesters/subjects found. Run `python manage.py bootstrap` first.")

        # ---------------------------------------------------------------- staff
        created_teachers = 0
        teachers = []
        for payload in TEACHERS:
            teacher, was_created = Teacher.objects.get_or_create(
                email=payload["email"],
                defaults={
                    **payload,
                    "department": department,
                    "joining_date": date(2018, 7, 1),
                    "salary": Decimal("75000.00"),
                    "state": "Karnataka",
                    "city": "Bengaluru",
                },
            )
            teachers.append(teacher)
            created_teachers += int(was_created)

        # ------------------------------------------------------------- students
        created_students = 0
        students = []
        cohort = self._batch(department, "2022-2026")
        for first_name, last_name, gender, category, _ in STUDENTS:
            email = f"{first_name.lower()}.{last_name.lower()}@student.example.com"
            student, was_created = Student.objects.get_or_create(
                email=email,
                defaults={
                    "first_name": first_name,
                    "last_name": last_name,
                    "phone": f"9822{rng.randint(100000, 999999)}",
                    "date_of_birth": date(2003, rng.randint(1, 12), rng.randint(1, 28)),
                    "gender": gender,
                    "category": category,
                    "admission_date": date(2022, 7, 15),
                    "department": department,
                    "course": course,
                    "semester": semesters[0],
                    "batch": cohort,
                    "guardian_name": f"{first_name}'s Guardian",
                    "guardian_phone": f"9845{rng.randint(100000, 999999)}",
                    "guardian_relation": "Parent",
                    "state": "Karnataka",
                    "city": "Bengaluru",
                    "created_by": user,
                },
            )
            students.append(student)
            created_students += int(was_created)

        for teacher, subject in zip(teachers, subjects):
            SubjectAssignment.objects.get_or_create(
                teacher=teacher,
                subject=subject,
                defaults={"academic_year": academic_year, "assigned_by": user},
            )

        # ----------------------------------------------------------- attendance
        marked_at = timezone.localdate()
        attendance_rows = 0
        statuses = ["PRESENT", "PRESENT", "PRESENT", "ABSENT", "LEAVE"]
        for offset in range(1, 6):
            day = marked_at - timedelta(days=offset)
            if day.weekday() >= 5:
                continue
            for index, student in enumerate(students):
                subject = subjects[index % len(subjects)]
                teacher = teachers[index % len(teachers)]
                _, was_created = Attendance.objects.get_or_create(
                    student=student,
                    subject=subject,
                    date=day,
                    defaults={
                        "teacher": teacher,
                        "status": statuses[rng.randrange(len(statuses))],
                        "marked_by": user,
                    },
                )
                attendance_rows += int(was_created)

        # ------------------------------------------------------------ fee plans
        fee_types = []
        for name, code in [("Tuition Fee", "TUI"), ("Examination Fee", "EXM"), ("Library Fee", "LIB")]:
            fee_type, _ = FeeType.objects.get_or_create(
                name=name, defaults={"code": code, "is_mandatory": True}
            )
            fee_types.append(fee_type)

        structures = []
        for fee_type, amount in zip(fee_types, [50000, 2500, 1500]):
            structure, _ = FeeStructure.objects.get_or_create(
                fee_type=fee_type,
                course=course,
                semester=semesters[0],
                department=department,
                academic_year=academic_year,
                defaults={"amount": Decimal(str(amount)), "frequency": "SEMESTER"},
            )
            structures.append(structure)

        invoices_created = 0
        payments_created = 0
        for structure in structures:
            summary = bulk_generate_invoices(
                structure,
                students=Student.objects.filter(
                    status=Student.Status.ACTIVE, batch=cohort
                ),
                due_date=marked_at + timedelta(days=30),
                academic_year=academic_year,
                user=user,
            )
            invoices_created += summary["created"]

        for index, student in enumerate(students):
            has_open_invoice = FeeRecord.objects.filter(student=student).exclude(
                status__in=[FeeRecord.Status.PAID, FeeRecord.Status.CANCELLED]
            ).exists()
            if not has_open_invoice:
                continue
            applied = pay_oldest_first(
                student,
                Decimal("10000.00"),
                method="ONLINE" if index % 2 else "CASH",
                payment_date=marked_at - timedelta(days=index),
                received_by=user,
            )
            payments_created += len(applied)

        # --------------------------------------------------------------- exams
        exam, _ = Exam.objects.get_or_create(
            code="MID1BTCS",
            defaults={
                "name": "Mid-Semester I Examination",
                "exam_type": "SEMESTER",
                "course": course,
                "semester": semesters[0],
                "academic_year": academic_year,
                "start_date": marked_at - timedelta(days=20),
                "end_date": marked_at - timedelta(days=10),
                "total_marks": 300,
                "passing_marks": 120,
                "passing_percentage": 40,
                "is_published": True,
                "results_published": True,
                "created_by": user,
            },
        )
        exam_subjects = []
        for subject in subjects[:3]:
            exam_subject, _ = ExamSubject.objects.get_or_create(
                exam=exam,
                subject=subject,
                defaults={
                    "max_marks": 100,
                    "pass_marks": 40,
                    "exam_date": marked_at - timedelta(days=18),
                    "exam_time": "10:00 AM - 12:00 PM",
                    "venue": "Exam Hall A",
                },
            )
            exam_subjects.append(exam_subject)

        marks_created = 0
        for index, student in enumerate(students):
            ability = 45 + index * 6
            for exam_subject in exam_subjects:
                score = max(20, min(100, ability + rng.randint(-12, 12)))
                _, was_created = MarkEntry.objects.get_or_create(
                    exam=exam,
                    exam_subject=exam_subject,
                    student=student,
                    defaults={
                        "marks_obtained": score,
                        "is_absent": index == len(students) - 1 and exam_subject == exam_subjects[-1],
                        "entered_by": user,
                    },
                )
                marks_created += int(was_created)
        result_summary = recalculate_exam_results(
            exam, students=Student.objects.filter(batch=cohort, semester=semesters[0])
        )

        # --------------------------------------------------------- notifications
        notifications_created = 0
        for payload in NOTIFICATIONS:
            _, was_created = Notification.objects.get_or_create(
                title=payload["title"],
                defaults={
                    "body": payload["body"],
                    "priority": payload["priority"],
                    "audience": payload["audience"],
                    "course": course,
                    "is_pinned": payload["is_pinned"],
                    "created_by": user,
                    "expires_at": timezone.now() + timedelta(days=30),
                },
            )
            notifications_created += int(was_created)

        # --------------------------------------------------------------- report
        self.stdout.write(self.style.SUCCESS("Demo data ready."))
        self.stdout.write(f"  academic year     : {academic_year}")
        self.stdout.write(f"  teachers created  : {created_teachers}")
        self.stdout.write(f"  students created  : {created_students}")
        self.stdout.write(f"  attendance rows   : {attendance_rows}")
        self.stdout.write(f"  fee structures    : {len(structures)}")
        self.stdout.write(f"  invoices created  : {invoices_created}")
        self.stdout.write(f"  payments recorded : {payments_created}")
        self.stdout.write(f"  exam + subjects   : {exam.code} ({len(exam_subjects)} subjects)")
        self.stdout.write(f"  mark entries      : {marks_created}")
        self.stdout.write(f"  results generated : {result_summary.get('created', 0)}")
        self.stdout.write(f"  notifications     : {notifications_created}")

    # ------------------------------------------------------------------ helpers
    def _batch(self, department, name):
        from academics.models import Batch

        start_year = int(name.split("-")[0])
        batch, _ = Batch.objects.get_or_create(
            name=name,
            department=department,
            defaults={"start_year": start_year, "end_year": start_year + 4},
        )
        return batch