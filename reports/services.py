"""Cross-module analytics. Every figure is aggregated from the database."""

from __future__ import annotations

from django.db.models import Avg, Count, Q
from django.utils import timezone

from core.utils import percent


# --------------------------------------------------------------------- students
def enrollment_summary() -> dict:
    from academics.models import Course, Department
    from students.models import Student

    aggregate = Student.objects.aggregate(
        total=Count("id"),
        male=Count("id", filter=Q(gender=Student.Gender.MALE)),
        female=Count("id", filter=Q(gender=Student.Gender.FEMALE)),
        other=Count("id", filter=Q(gender=Student.Gender.OTHER)),
        active=Count("id", filter=Q(status=Student.Status.ACTIVE)),
        inactive=Count("id", filter=Q(status=Student.Status.INACTIVE)),
        graduated=Count("id", filter=Q(status=Student.Status.GRADUATED)),
        on_leave=Count("id", filter=Q(status=Student.Status.ON_LEAVE)),
    )
    by_department = list(
        Department.objects.annotate(
            total=Count("students", distinct=True),
            active=Count(
                "students",
                filter=Q(students__status=Student.Status.ACTIVE),
                distinct=True,
            ),
        )
        .filter(total__gt=0)
        .order_by("-total")
    )
    by_course = list(
        Course.objects.annotate(total=Count("students", distinct=True))
        .filter(total__gt=0)
        .order_by("-total")[:12]
    )
    by_semester = list(
        Student.objects.values("semester__number", "semester__name")
        .annotate(total=Count("id"))
        .order_by("semester__number")
    )
    return {
        **aggregate,
        "male_percentage": percent(aggregate["male"], aggregate["total"]),
        "female_percentage": percent(aggregate["female"], aggregate["total"]),
        "by_department": by_department,
        "by_course": by_course,
        "by_semester": by_semester,
    }


def admission_trend(months: int = 12) -> dict:
    from students.models import Student

    labels, values = [], []
    today = timezone.localdate()
    year, month = today.year, today.month
    buckets = []
    for _ in range(months):
        buckets.append((year, month))
        month -= 1
        if month == 0:
            month = 12
            year -= 1
    buckets.reverse()
    rows = {
        (row["admission_date__year"], row["admission_date__month"]): row["total"]
        for row in Student.objects.filter(
            admission_date__year__gte=buckets[0][0]
        )
        .values("admission_date__year", "admission_date__month")
        .annotate(total=Count("id"))
    }
    for year, month in buckets:
        labels.append(f"{month:02d}/{str(year)[2:]}")
        values.append(rows.get((year, month), 0))
    return {"labels": labels, "values": values}


# ------------------------------------------------------------------ attendance
def attendance_summary(start=None, end=None) -> dict:
    from attendance.models import Attendance

    queryset = Attendance.objects.all()
    if start:
        queryset = queryset.filter(date__gte=start)
    if end:
        queryset = queryset.filter(date__lte=end)

    aggregate = queryset.aggregate(
        total=Count("id"),
        present=Count("id", filter=Q(status=Attendance.Status.PRESENT)),
        absent=Count("id", filter=Q(status=Attendance.Status.ABSENT)),
        leave=Count("id", filter=Q(status=Attendance.Status.LEAVE)),
        days=Count("date", distinct=True),
    )
    daily = list(
        queryset.values("date")
        .annotate(
            total=Count("id"),
            present=Count("id", filter=Q(status=Attendance.Status.PRESENT)),
        )
        .order_by("date")
    )
    return {
        **aggregate,
        "percentage": percent(aggregate["present"], aggregate["total"]),
        "absent_percentage": percent(aggregate["absent"], aggregate["total"]),
        "daily": daily,
        "labels": [row["date"].strftime("%d %b") for row in daily],
        "present_values": [row["present"] for row in daily],
        "absent_values": [row["total"] - row["present"] for row in daily],
    }


def attendance_by_department() -> list[dict]:
    from attendance.models import Attendance
    from students.models import Student

    rows = (
        Attendance.objects.values("student__department__name")
        .annotate(
            total=Count("id"),
            present=Count("id", filter=Q(status=Attendance.Status.PRESENT)),
            absent=Count("id", filter=Q(status=Attendance.Status.ABSENT)),
            leave=Count("id", filter=Q(status=Attendance.Status.LEAVE)),
        )
        .order_by("-total")
    )
    return [
        {
            "department": row["student__department__name"] or "Unassigned",
            "total": row["total"],
            "present": row["present"],
            "absent": row["absent"],
            "leave": row["leave"],
            "percentage": percent(row["present"], row["total"]),
        }
        for row in rows
    ]


def defaulters(limit: int = 20, threshold: float = 75.0) -> list[dict]:
    """Students whose attendance is below ``threshold``."""
    from attendance.models import Attendance
    from students.models import Student

    rows = (
        Attendance.objects.values(
            "student_id",
            "student__student_id",
            "student__first_name",
            "student__last_name",
            "student__course__name",
        )
        .annotate(
            total=Count("id"),
            present=Count("id", filter=Q(status=Attendance.Status.PRESENT)),
            absent=Count("id", filter=Q(status=Attendance.Status.ABSENT)),
        )
        .order_by("-absent")
    )
    output = []
    for row in rows:
        percentage = percent(row["present"], row["total"])
        if percentage >= threshold:
            continue
        output.append(
            {
                "student_id": row["student__student_id"],
                "name": f"{row['student__first_name']} {row['student__last_name']}".strip(),
                "course": row["student__course__name"] or "-",
                "total": row["total"],
                "present": row["present"],
                "absent": row["absent"],
                "percentage": percentage,
            }
        )
        if len(output) >= limit:
            break
    return output


# ------------------------------------------------------------------- academics
def academic_summary() -> dict:
    from academics.models import Batch, Course, Department, Subject
    from teachers.models import SubjectAssignment, Teacher

    return {
        "departments": Department.objects.count(),
        "courses": Course.objects.filter(is_active=True).count(),
        "subjects": Subject.objects.filter(is_active=True).count(),
        "batches": Batch.objects.filter(is_active=True).count(),
        "teachers": Teacher.objects.filter(status=Teacher.Status.ACTIVE).count(),
        "assignments": SubjectAssignment.objects.count(),
        "subject_load": list(
            Subject.objects.annotate(
                teachers=Count("assignments", distinct=True),
                students=Count("course__students", distinct=True),
            )
            .filter(is_active=True)
            .order_by("-teachers")[:10]
        ),
    }


# ---------------------------------------------------------------------- exams
def performance_summary() -> dict:
    from exams.models import Exam, Result

    aggregate = Result.objects.aggregate(
        total=Count("id"),
        passed=Count("id", filter=Q(is_pass=True)),
        failed=Count("id", filter=Q(is_pass=False)),
        average=Avg("percentage"),
    )
    grades = list(
        Result.objects.values("grade")
        .annotate(total=Count("id"))
        .order_by("grade")
    )
    toppers = list(
        Result.objects.select_related("exam", "student")
        .order_by("-percentage")[:20]
    )
    exam_rows = list(
        Exam.objects.annotate(
            results_total=Count("results", distinct=True),
            passed=Count("results", filter=Q(results__is_pass=True), distinct=True),
        )
        .order_by("-start_date")[:12]
    )
    return {
        **aggregate,
        "average_percentage": round(float(aggregate["average"] or 0), 2),
        "pass_percentage": percent(aggregate["passed"], aggregate["total"]),
        "grades": grades,
        "toppers": toppers,
        "exams": exam_rows,
    }


def toppers_report(limit: int = 25) -> list[dict]:
    from exams.models import Result

    rows = (
        Result.objects.select_related("exam", "student", "student__course")
        .filter(is_pass=True)
        .order_by("-percentage")[:limit]
    )
    return [
        {
            "result": row,
            "student": row.student,
            "exam": row.exam,
            "percentage": float(row.percentage or 0),
            "grade": row.grade,
        }
        for row in rows
    ]


# ------------------------------------------------------------------------ fees
def fee_snapshot() -> dict:
    from fees.services import fee_summary

    return fee_summary()


# ------------------------------------------------------------------- teachers
def teacher_snapshot() -> dict:
    from django.db.models import Sum

    from teachers.models import SubjectAssignment, Teacher

    aggregate = Teacher.objects.aggregate(
        total=Count("id"),
        active=Count("id", filter=Q(status=Teacher.Status.ACTIVE)),
        on_leave=Count("id", filter=Q(status=Teacher.Status.ON_LEAVE)),
        payroll=Sum("salary"),
    )
    workload = (
        SubjectAssignment.objects.values(
            "teacher__employee_id", "teacher__first_name", "teacher__last_name"
        )
        .annotate(subjects=Count("id"))
        .order_by("-subjects")[:15]
    )
    return {
        **aggregate,
        "average_workload": round(
            (aggregate["total"] and SubjectAssignment.objects.count() / aggregate["total"]) or 0, 2
        ),
        "workload": [
            {
                "teacher_id": row["teacher__employee_id"],
                "name": f"{row['teacher__first_name']} {row['teacher__last_name']}".strip(),
                "subjects": row["subjects"],
            }
            for row in workload
        ],
    }


# ------------------------------------------------------------------ dashboard
def everything() -> dict:
    """All report datasets used by the print-friendly overview page."""
    return {
        "generated_at": timezone.localtime(),
        "enrollment": enrollment_summary(),
        "attendance": attendance_summary(),
        "academics": academic_summary(),
        "performance": performance_summary(),
        "fees": fee_snapshot(),
        "teachers": teacher_snapshot(),
        "admissions": admission_trend(),
    }