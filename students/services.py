"""Student related aggregation and promotion logic."""

from __future__ import annotations

from django.db import transaction
from django.db.models import Avg, Count, DecimalField, F, Max, Q, Sum, Value
from django.db.models.functions import Coalesce

from core.utils import percent


def student_attendance_summary(student, queryset=None) -> dict:
    """Attendance totals + percentage for a single student."""
    from attendance.models import Attendance

    queryset = queryset if queryset is not None else Attendance.objects.filter(student=student)
    totals = queryset.aggregate(
        total=Count("id"),
        present=Count("id", filter=Q(status=Attendance.Status.PRESENT)),
        absent=Count("id", filter=Q(status=Attendance.Status.ABSENT)),
        leave=Count("id", filter=Q(status=Attendance.Status.LEAVE)),
    )
    return {
        "total": totals["total"],
        "present": totals["present"],
        "absent": totals["absent"],
        "leave": totals["leave"],
        "percentage": percent(totals["present"], totals["total"]),
    }


def attendance_shortage_list(threshold: float | None = None, limit: int = 20):
    """Students whose attendance is below the configured threshold."""
    from django.conf import settings

    from students.models import Student

    threshold = threshold or float(
        getattr(settings, "SMS", {}).get("ATTENDANCE_SHORTAGE_PERCENTAGE", 75)
    )
    rows = []
    queryset = Student.objects.active().with_details()[:limit]
    for student in queryset:
        summary = student_attendance_summary(student)
        if summary["total"] and summary["percentage"] < threshold:
            rows.append({"student": student, **summary})
    rows.sort(key=lambda item: item["percentage"])
    return rows, threshold


def student_result_summary(student) -> dict:
    from exams.models import Result

    queryset = Result.objects.filter(student=student)
    totals = queryset.aggregate(
        exams=Count("id"),
        passed=Count("id", filter=Q(is_pass=True)),
        average=Avg("percentage"),
        best=Max("percentage"),
    )
    latest = queryset.select_related("exam").order_by("-exam__end_date", "-id").first()
    return {
        "exams": totals["exams"],
        "passed": totals["passed"],
        "failed": max(0, totals["exams"] - totals["passed"]),
        "average": round(float(totals["average"] or 0), 2),
        "best": round(float(totals["best"] or 0), 2),
        "latest": latest,
    }


def student_fee_summary(student) -> dict:
    from fees.models import FeeRecord, Payment

    records = FeeRecord.objects.filter(student=student).exclude(
        status=FeeRecord.Status.CANCELLED
    )
    totals = records.aggregate(
        billed=_net_amount_expr(),
        records=Count("id"),
        pending_records=Count(
            "id",
            filter=Q(
                status__in=[
                    FeeRecord.Status.PENDING,
                    FeeRecord.Status.PARTIAL,
                    FeeRecord.Status.OVERDUE,
                ]
            ),
        ),
    )
    paid = (
        Payment.objects.filter(fee_record__in=records, is_cancelled=False)
        .distinct()
        .aggregate(total=Sum("amount"))["total"]
    )
    billed = float(totals["billed"] or 0)
    paid = float(paid or 0)
    return {
        "billed": billed,
        "paid": paid,
        "pending": round(max(0.0, billed - paid), 2),
        "records": totals["records"],
        "pending_records": totals["pending_records"],
        "payment_percentage": percent(paid, billed),
    }


def _net_amount_expr():
    """``SUM(amount - discount)`` that also works when there are no rows."""
    return Coalesce(
        Sum(F("amount") - F("discount")),
        Value(0),
        output_field=DecimalField(max_digits=14, decimal_places=2),
    )


def student_documents(student):
    return student.documents.select_related("uploaded_by").all()


def student_notifications(student, limit: int = 10):
    """Announcements visible to a student (general + student specific)."""
    from django.utils import timezone

    from notifications.models import Notification

    now = timezone.now()
    return (
        Notification.objects.filter(is_active=True)
        .filter(audience__in=[Notification.Audience.ALL, Notification.Audience.STUDENT])
        .filter(Q(student__isnull=True) | Q(student=student))
        .filter(publish_at__lte=now)
        .filter(Q(expires_at__isnull=True) | Q(expires_at__gte=now))
        .order_by("-created_at")[:limit]
    )


@transaction.atomic
def promote_student(
    student,
    *,
    to_semester=None,
    to_batch=None,
    to_course=None,
    to_department=None,
    promotion_type="SEMESTER",
    reason="",
    remarks="",
    promoted_by=None,
    academic_year_from="",
    academic_year_to="",
):
    """Move a student to the next academic level and keep the old details."""
    from students.models import StudentPromotion

    from_semester = student.semester
    from_batch = student.batch
    from_course = student.course
    from_department = student.department

    new_course = to_course or student.course
    new_department = to_department or new_course.department

    promotion = StudentPromotion.objects.create(
        student=student,
        from_semester=from_semester,
        to_semester=to_semester or from_semester,
        from_batch=from_batch,
        to_batch=to_batch or from_batch,
        from_course=from_course,
        to_course=new_course,
        from_department=from_department,
        to_department=new_department,
        promotion_type=promotion_type,
        reason=reason,
        remarks=remarks,
        promoted_by=promoted_by,
        academic_year_from=academic_year_from,
        academic_year_to=academic_year_to,
    )

    student.semester = to_semester or student.semester
    student.batch = to_batch or student.batch
    student.course = new_course
    student.department = new_department
    student.save(
        update_fields=["semester", "batch", "course", "department", "updated_at"]
    )
    return promotion


def student_profile_context(student) -> dict:
    """Everything the student detail page needs."""
    from attendance.models import Attendance
    from exams.models import MarkEntry, Result
    from fees.models import FeeRecord, Payment

    attendance_summary = student_attendance_summary(student)
    result_summary = student_result_summary(student)
    fee_summary = student_fee_summary(student)

    recent_attendance = (
        Attendance.objects.filter(student=student)
        .select_related("subject", "teacher")
        .order_by("-date", "-id")[:10]
    )
    results = (
        Result.objects.filter(student=student)
        .select_related("exam")
        .order_by("-exam__end_date")[:10]
    )
    subject_attendance = list(
        Attendance.objects.filter(student=student)
        .values("subject__name", "subject__code")
        .annotate(
            total=Count("id"),
            present=Count("id", filter=Q(status=Attendance.Status.PRESENT)),
        )
        .order_by("subject__code")
    )
    for row in subject_attendance:
        row["percentage"] = percent(row["present"], row["total"], 1)
        row["name"] = row["subject__name"] or "Unassigned"
        row["code"] = row["subject__code"] or "-"

    fee_records = FeeRecord.objects.filter(student=student).select_related("fee_type")
    payments = (
        Payment.objects.filter(fee_record__student=student)
        .select_related("fee_record", "received_by")
        .order_by("-payment_date")[:10]
    )
    mark_count = MarkEntry.objects.filter(student=student).count()

    return {
        "attendance_summary": attendance_summary,
        "result_summary": result_summary,
        "fee_summary": fee_summary,
        "recent_attendance": recent_attendance,
        "subject_attendance": subject_attendance,
        "results": results,
        "fee_records": fee_records,
        "payments": payments,
        "mark_count": mark_count,
        "document_count": student.documents.count(),
        "promotion_count": student.promotions.count(),
    }
