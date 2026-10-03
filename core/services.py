"""Dashboard aggregation services (all statistics come from the database)."""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

from django.db.models import Avg, Count, DecimalField, F, Q, Sum, Value
from django.db.models.functions import Coalesce
from django.utils import timezone

from core.utils import percent


def _d(value) -> float:
    return float(value or 0)


def dashboard_stats() -> dict:
    """Compute every number displayed on the dashboard."""
    from academics.models import Course, Department, Subject
    from attendance.models import Attendance
    from exams.models import Exam, Result
    from fees.models import FeeRecord, Payment
    from notifications.models import Notification
    from students.models import Student
    from teachers.models import Teacher

    today = timezone.localdate()
    month_start = today.replace(day=1)

    students_qs = Student.objects.all()
    student_agg = students_qs.aggregate(
        total=Count("id"),
        male=Count("id", filter=Q(gender=Student.Gender.MALE)),
        female=Count("id", filter=Q(gender=Student.Gender.FEMALE)),
        other=Count("id", filter=Q(gender=Student.Gender.OTHER)),
        active=Count("id", filter=Q(status=Student.Status.ACTIVE)),
        inactive=Count("id", filter=Q(status=Student.Status.INACTIVE)),
        graduated=Count("id", filter=Q(status=Student.Status.GRADUATED)),
        on_leave=Count("id", filter=Q(status=Student.Status.ON_LEAVE)),
        this_month=Count("id", filter=Q(admission_date__gte=month_start)),
    )

    teacher_qs = Teacher.objects.all()
    teacher_agg = teacher_qs.aggregate(
        total=Count("id"),
        active=Count("id", filter=Q(status=Teacher.Status.ACTIVE)),
        on_leave=Count("id", filter=Q(status=Teacher.Status.ON_LEAVE)),
        inactive=Count("id", filter=Q(status=Teacher.Status.INACTIVE)),
        male=Count("id", filter=Q(gender=Teacher.Gender.MALE)),
        female=Count("id", filter=Q(gender=Teacher.Gender.FEMALE)),
        payroll=Coalesce(
            Sum("salary", filter=Q(status=Teacher.Status.ACTIVE)),
            Value(Decimal("0")),
            output_field=DecimalField(max_digits=14, decimal_places=2),
        ),
    )

    # ---------------------------------------------------------------- attendance
    today_attendance = Attendance.objects.filter(date=today)
    today_counts = today_attendance.aggregate(
        total=Count("id"),
        present=Count("id", filter=Q(status=Attendance.Status.PRESENT)),
        absent=Count("id", filter=Q(status=Attendance.Status.ABSENT)),
        leave=Count("id", filter=Q(status=Attendance.Status.LEAVE)),
    )
    overall_attendance = Attendance.objects.aggregate(
        total=Count("id"),
        present=Count("id", filter=Q(status=Attendance.Status.PRESENT)),
        absent=Count("id", filter=Q(status=Attendance.Status.ABSENT)),
        leave=Count("id", filter=Q(status=Attendance.Status.LEAVE)),
        marked_on=Count("date", distinct=True),
    )
    month_attendance = Attendance.objects.filter(date__gte=month_start).aggregate(
        total=Count("id"),
        present=Count("id", filter=Q(status=Attendance.Status.PRESENT)),
    )

    # ---------------------------------------------------------------- fees
    fee_agg = FeeRecord.objects.exclude(status=FeeRecord.Status.CANCELLED).aggregate(
        total=Coalesce(
            Sum(F("amount") - F("discount")),
            Value(Decimal("0")),
            output_field=DecimalField(max_digits=14, decimal_places=2),
        ),
        pending_records=Count("id", filter=Q(status__in=["PENDING", "PARTIAL", "OVERDUE"])),
        paid_records=Count("id", filter=Q(status=FeeRecord.Status.PAID)),
    )
    paid_total = Payment.objects.aggregate(
        total=Coalesce(
            Sum("amount"), Value(Decimal("0")),
            output_field=DecimalField(max_digits=14, decimal_places=2),
        )
    )["total"]
    total_fee = fee_agg["total"]
    pending_total = max(Decimal("0"), Decimal(total_fee) - Decimal(paid_total))
    overdue_records = FeeRecord.objects.filter(
        status__in=[FeeRecord.Status.PENDING, FeeRecord.Status.PARTIAL],
        due_date__lt=today,
    ).count()
    month_collected = Payment.objects.filter(payment_date__gte=month_start).aggregate(
        total=Coalesce(
            Sum("amount"), Value(Decimal("0")),
            output_field=DecimalField(max_digits=14, decimal_places=2),
        )
    )["total"]

    # ---------------------------------------------------------------- exams
    exam_agg = Exam.objects.aggregate(
        total=Count("id"),
        published=Count("id", filter=Q(is_published=True)),
        upcoming=Count("id", filter=Q(start_date__gte=today)),
    )
    result_agg = Result.objects.aggregate(
        total=Count("id"),
        passed=Count("id", filter=Q(is_pass=True)),
        average=Coalesce(Avg("percentage"), Value(Decimal("0"))),
    )

    overdue_fees = _overdue_fee_rows(limit=5)

    return {
        "generated_at": timezone.localtime(),
        "students": {
            "total": student_agg["total"],
            "male": student_agg["male"],
            "female": student_agg["female"],
            "other": student_agg["other"],
            "active": student_agg["active"],
            "inactive": student_agg["inactive"],
            "graduated": student_agg["graduated"],
            "on_leave": student_agg["on_leave"],
            "this_month": student_agg["this_month"],
        },
        "teachers": {
            "total": teacher_agg["total"],
            "active": teacher_agg["active"],
            "on_leave": teacher_agg["on_leave"],
            "inactive": teacher_agg["inactive"],
            "male": teacher_agg["male"],
            "female": teacher_agg["female"],
            "payroll": _d(teacher_agg["payroll"]),
        },
        "academics": {
            "departments": Department.objects.count(),
            "courses": Course.objects.filter(is_active=True).count(),
            "courses_total": Course.objects.count(),
            "subjects": Subject.objects.filter(is_active=True).count(),
            "subjects_total": Subject.objects.count(),
        },
        "attendance": {
            "today": {
                "total": today_counts["total"],
                "present": today_counts["present"],
                "absent": today_counts["absent"],
                "leave": today_counts["leave"],
                "percentage": percent(today_counts["present"], today_counts["total"]),
            },
            "month": {
                "total": month_attendance["total"],
                "present": month_attendance["present"],
                "percentage": percent(month_attendance["present"], month_attendance["total"]),
            },
            "overall": {
                "total": overall_attendance["total"],
                "present": overall_attendance["present"],
                "absent": overall_attendance["absent"],
                "leave": overall_attendance["leave"],
                "days": overall_attendance["marked_on"],
                "percentage": percent(
                    overall_attendance["present"], overall_attendance["total"]
                ),
            },
        },
        "fees": {
            "total": _d(total_fee),
            "paid": _d(paid_total),
            "pending": _d(pending_total),
            "collection_percentage": percent(paid_total, total_fee),
            "pending_records": fee_agg["pending_records"],
            "paid_records": fee_agg["paid_records"],
            "overdue_records": overdue_records,
            "month_collected": _d(month_collected),
            "overdue": overdue_fees,
        },
        "exams": {
            "total": exam_agg["total"],
            "published": exam_agg["published"],
            "upcoming": exam_agg["upcoming"],
            "results": result_agg["total"],
            "passed": result_agg["passed"],
            "failed": max(0, result_agg["total"] - result_agg["passed"]),
            "pass_percentage": percent(result_agg["passed"], result_agg["total"]),
            "average_percentage": round(_d(result_agg["average"]), 2),
        },
        "notifications": {
            "active": Notification.objects.filter(is_active=True).count(),
        },
    }


def _overdue_fee_rows(limit: int = 5):
    from fees.models import FeeRecord

    today = timezone.localdate()
    rows = []
    qs = (
        FeeRecord.objects.filter(
            status__in=[FeeRecord.Status.PENDING, FeeRecord.Status.PARTIAL],
            due_date__lt=today,
        )
        .select_related("student", "fee_type")
        .order_by("due_date")[:limit]
    )
    for record in qs:
        rows.append(
            {
                "id": record.pk,
                "receipt_no": record.invoice_no,
                "student": record.student.full_name,
                "student_id": record.student.student_id,
                "fee_type": record.fee_type.name,
                "due_date": record.due_date,
                "days_overdue": (today - record.due_date).days,
                "remaining": _d(record.remaining_amount),
            }
        )
    return rows


def dashboard_charts(stats: dict | None = None) -> dict:
    """Data structures consumed by Chart.js."""
    from academics.models import Course, Department
    from attendance.models import Attendance
    from fees.models import FeeRecord, Payment
    from students.models import Student

    stats = stats or dashboard_stats()
    today = timezone.localdate()

    gender_labels, gender_values = [], []
    for label, key in (("Male", "male"), ("Female", "female"), ("Other", "other")):
        gender_labels.append(label)
        gender_values.append(stats["students"][key])

    department_rows = list(
        Department.objects.annotate(
            student_count=Count("students", distinct=True),
            teacher_count=Count("teachers", distinct=True),
        )
        .values("name", "student_count", "teacher_count")[:12]
    )
    course_rows = list(
        Course.objects.annotate(student_count=Count("students", distinct=True))
        .values("name", "student_count")[:10]
    )

    status_map = {
        "Active": stats["students"]["active"],
        "Inactive": stats["students"]["inactive"],
        "On Leave": stats["students"]["on_leave"],
        "Graduated": stats["students"]["graduated"],
    }

    enrollment_rows = list(
        Student.objects.filter(admission_date__isnull=False)
        .values("admission_date__year", "admission_date__month")
        .annotate(total=Count("id"))
        .order_by("admission_date__year", "admission_date__month")[:12]
    )
    month_names = [
        "Jan", "Feb", "Mar", "Apr", "May", "Jun",
        "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
    ]
    enrollment_labels, enrollment_values = [], []
    for row in enrollment_rows:
        enrollment_labels.append(f"{month_names[int(row['admission_date__month']) - 1]}-{row['admission_date__year']}")
        enrollment_values.append(row["total"])

    attendance_rows = (
        Attendance.objects.filter(date__gte=today - dt.timedelta(days=6))
        .values("date")
        .annotate(
            present=Count("id", filter=Q(status=Attendance.Status.PRESENT)),
            absent=Count("id", filter=Q(status=Attendance.Status.ABSENT)),
            leave=Count("id", filter=Q(status=Attendance.Status.LEAVE)),
        )
        .order_by("date")
    )
    attendance_labels, present_values, absent_values, leave_values = [], [], [], []
    for row in attendance_rows:
        attendance_labels.append(
            row["date"].strftime("%d %b")
            if hasattr(row["date"], "strftime")
            else str(row["date"])
        )
        present_values.append(row["present"])
        absent_values.append(row["absent"])
        leave_values.append(row["leave"])

    fee_months = _last_n_months(6)
    fee_start = dt.date(fee_months[0][0], fee_months[0][1], 1)
    collected_rows = {
        (row["payment_date__year"], row["payment_date__month"]): _d(row["total"])
        for row in Payment.objects.filter(payment_date__gte=fee_start)
        .values("payment_date__year", "payment_date__month")
        .annotate(total=Sum("amount"))
    }
    invoiced_rows = {
        (row["created_at__year"], row["created_at__month"]): _d(row["total"])
        for row in FeeRecord.objects.filter(created_at__gte=timezone.now() - dt.timedelta(days=190))
        .values("created_at__year", "created_at__month")
        .annotate(total=Sum(F("amount") - F("discount")))
    }
    fee_labels, collected_values, invoiced_values = [], [], []
    for year, month in fee_months:
        fee_labels.append(f"{month_names[month - 1]}-{str(year)[2:]}")
        collected_values.append(round(collected_rows.get((year, month), 0), 2))
        invoiced_values.append(round(invoiced_rows.get((year, month), 0), 2))

    subject_attendance = list(
        Attendance.objects.values("subject__name")
        .annotate(
            total=Count("id"),
            present=Count("id", filter=Q(status=Attendance.Status.PRESENT)),
        )
        .order_by("-total")[:8]
    )
    subject_labels = [row["subject__name"] or "Unassigned" for row in subject_attendance]
    subject_values = [percent(row["present"], row["total"], 1) for row in subject_attendance]

    return {
        "gender": {"labels": gender_labels, "values": gender_values},
        "departments": {
            "labels": [row["name"] for row in department_rows],
            "students": [row["student_count"] for row in department_rows],
            "teachers": [row["teacher_count"] for row in department_rows],
        },
        "courses": {
            "labels": [row["name"] for row in course_rows],
            "values": [row["student_count"] for row in course_rows],
        },
        "status": {"labels": list(status_map.keys()), "values": list(status_map.values())},
        "enrollment": {"labels": enrollment_labels, "values": enrollment_values},
        "attendance_trend": {
            "labels": attendance_labels,
            "present": present_values,
            "absent": absent_values,
            "leave": leave_values,
        },
        "fees": {
            "labels": fee_labels,
            "collected": collected_values,
            "invoiced": invoiced_values,
        },
        "subject_attendance": {
            "labels": subject_labels,
            "values": subject_values,
        },
        "totals": {
            "collected": stats["fees"]["paid"],
            "pending": stats["fees"]["pending"],
            "attendance_percentage": stats["attendance"]["overall"]["percentage"],
        },
    }


def _last_n_months(count: int):
    today = timezone.localdate()
    year, month = today.year, today.month
    months = []
    for _ in range(count):
        months.append((year, month))
        month -= 1
        if month == 0:
            month = 12
            year -= 1
    return list(reversed(months))
