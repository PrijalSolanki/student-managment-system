"""Attendance aggregation helpers."""

from __future__ import annotations

from django.db.models import Count, Q
from django.utils import timezone

from core.utils import full_name, percent


def attendance_totals(queryset) -> dict:
    from attendance.models import Attendance

    totals = queryset.aggregate(
        total=Count("id"),
        present=Count("id", filter=Q(status=Attendance.Status.PRESENT)),
        absent=Count("id", filter=Q(status=Attendance.Status.ABSENT)),
        leave=Count("id", filter=Q(status=Attendance.Status.LEAVE)),
    )
    return {
        **totals,
        "percentage": percent(totals["present"], totals["total"]),
    }


def daily_report(date=None):
    """Present / absent / leave counts grouped by subject for one day."""
    from attendance.models import Attendance

    date = date or timezone.localdate()
    rows = (
        Attendance.objects.filter(date=date)
        .values(
            "subject__id",
            "subject__code",
            "subject__name",
            "teacher__first_name",
            "teacher__last_name",
        )
        .annotate(
            total=Count("id"),
            present=Count("id", filter=Q(status=Attendance.Status.PRESENT)),
            absent=Count("id", filter=Q(status=Attendance.Status.ABSENT)),
            leave=Count("id", filter=Q(status=Attendance.Status.LEAVE)),
        )
        .order_by("subject__code")
    )
    data = []
    for row in rows:
        data.append(
            {
                "subject_id": row["subject__id"],
                "subject_code": row["subject__code"],
                "subject": row["subject__name"],
                "teacher": full_name(row["teacher__first_name"], row["teacher__last_name"]) or "-",
                "total": row["total"],
                "present": row["present"],
                "absent": row["absent"],
                "leave": row["leave"],
                "percentage": percent(row["present"], row["total"], 1),
            }
        )
    return {"date": date, "rows": data, "totals": attendance_totals(
        Attendance.objects.filter(date=date)
    )}


def monthly_report(year=None, month=None):
    from attendance.models import Attendance

    today = timezone.localdate()
    year = year or today.year
    month = month or today.month
    queryset = Attendance.objects.filter(date__year=year, date__month=month)
    per_day = (
        queryset.values("date")
        .annotate(
            total=Count("id"),
            present=Count("id", filter=Q(status=Attendance.Status.PRESENT)),
            absent=Count("id", filter=Q(status=Attendance.Status.ABSENT)),
            leave=Count("id", filter=Q(status=Attendance.Status.LEAVE)),
        )
        .order_by("date")
    )
    rows = []
    for row in per_day:
        rows.append(
            {
                "date": row["date"],
                "total": row["total"],
                "present": row["present"],
                "absent": row["absent"],
                "leave": row["leave"],
                "percentage": percent(row["present"], row["total"], 1),
            }
        )
    per_subject = (
        queryset.values("subject__code", "subject__name")
        .annotate(
            total=Count("id"),
            present=Count("id", filter=Q(status=Attendance.Status.PRESENT)),
            absent=Count("id", filter=Q(status=Attendance.Status.ABSENT)),
            leave=Count("id", filter=Q(status=Attendance.Status.LEAVE)),
        )
        .order_by("subject__code")
    )
    return {
        "year": year,
        "month": month,
        "days": rows,
        "subjects": [
            {
                "subject_code": row["subject__code"],
                "subject": row["subject__name"],
                "total": row["total"],
                "present": row["present"],
                "absent": row["absent"],
                "leave": row["leave"],
                "percentage": percent(row["present"], row["total"], 1),
            }
            for row in per_subject
        ],
        "totals": attendance_totals(queryset),
    }


def student_report(student, date_from=None, date_to=None):
    """Subject-wise and overall attendance for one student."""
    from attendance.models import Attendance

    queryset = Attendance.objects.filter(student=student)
    if date_from:
        queryset = queryset.filter(date__gte=date_from)
    if date_to:
        queryset = queryset.filter(date__lte=date_to)
    per_subject = (
        queryset.values("subject__id", "subject__code", "subject__name")
        .annotate(
            total=Count("id"),
            present=Count("id", filter=Q(status=Attendance.Status.PRESENT)),
            absent=Count("id", filter=Q(status=Attendance.Status.ABSENT)),
            leave=Count("id", filter=Q(status=Attendance.Status.LEAVE)),
        )
        .order_by("subject__code")
    )
    subjects = [
        {
            "subject_id": row["subject__id"],
            "subject_code": row["subject__code"],
            "subject": row["subject__name"],
            "total": row["total"],
            "present": row["present"],
            "absent": row["absent"],
            "leave": row["leave"],
            "percentage": percent(row["present"], row["total"], 1),
        }
        for row in per_subject
    ]
    totals = attendance_totals(queryset)
    recent = queryset.select_related("subject", "teacher").order_by("-date")[:15]
    return {
        "student": student,
        "subjects": subjects,
        "totals": totals,
        "recent": recent,
        "date_from": date_from,
        "date_to": date_to,
    }


def subject_report(subject, date_from=None, date_to=None, course=None, semester=None):
    from attendance.models import Attendance

    queryset = Attendance.objects.filter(subject=subject)
    if course:
        queryset = queryset.filter(student__course=course)
    if semester:
        queryset = queryset.filter(student__semester=semester)
    if date_from:
        queryset = queryset.filter(date__gte=date_from)
    if date_to:
        queryset = queryset.filter(date__lte=date_to)

    per_student = (
        queryset.values(
            "student__id", "student__student_id", "student__first_name", "student__last_name"
        )
        .annotate(
            total=Count("id"),
            present=Count("id", filter=Q(status=Attendance.Status.PRESENT)),
            absent=Count("id", filter=Q(status=Attendance.Status.ABSENT)),
            leave=Count("id", filter=Q(status=Attendance.Status.LEAVE)),
        )
        .order_by("student__student_id")
    )
    rows = []
    for row in per_student:
        student_percentage = percent(row["present"], row["total"], 1)
        rows.append(
            {
                "student_id": row["student__id"],
                "student_code": row["student__student_id"],
                "student_name": f"{row['student__first_name']} {row['student__last_name']}".strip(),
                "total": row["total"],
                "present": row["present"],
                "absent": row["absent"],
                "leave": row["leave"],
                "percentage": student_percentage,
                "badge": "success"
                if student_percentage >= 75
                else ("warning" if student_percentage >= 60 else "danger"),
            }
        )
    rows.sort(key=lambda item: item["percentage"])
    return {
        "subject": subject,
        "rows": rows,
        "totals": attendance_totals(queryset),
        "date_from": date_from,
        "date_to": date_to,
        "course": course,
        "semester": semester,
    }


def department_attendance_summary(departments=None):
    """Attendance percentage per department (used on the dashboard/reports)."""
    from academics.models import Department
    from attendance.models import Attendance

    queryset = departments if departments is not None else Department.objects.all()
    rows = []
    for dept in queryset:
        records = Attendance.objects.filter(student__department=dept)
        rows.append({"department": dept, **attendance_totals(records)})
    return rows


def save_bulk_attendance(entries, user):
    """Create / update attendance rows from ``[(student_id, status), ...]``."""
    from attendance.models import Attendance

    created, updated = 0, 0
    for student_id, status, subject_id, teacher_id, date, remarks in entries:
        if not status:
            continue
        _, was_created = Attendance.objects.update_or_create(
            student_id=student_id,
            subject_id=subject_id,
            date=date,
            defaults={
                "status": status,
                "teacher_id": teacher_id,
                "remarks": remarks or "",
                "marked_by": user,
            },
        )
        if was_created:
            created += 1
        else:
            updated += 1
    return {"created": created, "updated": updated}
