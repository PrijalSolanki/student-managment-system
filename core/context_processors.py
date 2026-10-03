"""Template context available on every page."""

from __future__ import annotations

from django.conf import settings


def application_context(request):
    """Expose institute branding, navigation badges and helper flags."""
    from core.models import SiteSetting

    sms = getattr(settings, "SMS", {})
    context = {
        "SITE_SETTINGS": SiteSetting.load(),
        "INSTITUTE_NAME": sms.get("INSTITUTE_NAME"),
        "INSTITUTE_CODE": sms.get("INSTITUTE_CODE"),
        "CURRENCY_SYMBOL": sms.get("CURRENCY_SYMBOL", "₹"),
        "ACADEMIC_YEAR": sms.get("ACADEMIC_YEAR", ""),
        "CURRENT_SEMESTER": sms.get("CURRENT_SEMESTER", 1),
        "PASS_PERCENTAGE": sms.get("PASS_PERCENTAGE", 40),
        "SIDEBAR_COUNTS": {},
        "UNREAD_NOTIFICATIONS": 0,
        "APP_VERSION": "1.0.0",
    }

    user = getattr(request, "user", None)
    if user is None or not user.is_authenticated or not getattr(
        user, "is_internal_user", False
    ):
        return context

    context["UNREAD_NOTIFICATIONS"] = _unread_count(user)
    context["SIDEBAR_COUNTS"] = _sidebar_counts(user)
    return context


def _unread_count(user) -> int:
    try:
        from notifications.models import Notification, NotificationRead

        visible = Notification.objects.visible_to(user)
        read_ids = NotificationRead.objects.filter(user=user).values_list(
            "notification_id", flat=True
        )
        return visible.exclude(id__in=list(read_ids)).count()
    except Exception:  # pragma: no cover - DB not ready
        return 0


def _sidebar_counts(user) -> dict:
    try:
        from django.db.models import Sum
        from django.utils import timezone

        from academics.models import Course, Department, Subject
        from attendance.models import Attendance
        from exams.models import Exam
        from fees.models import FeeRecord, Payment
        from students.models import Student
        from teachers.models import Teacher

        today = timezone.now().date()
        fee_summary = FeeRecord.objects.filter(status__in=["PENDING", "PARTIAL", "OVERDUE"])
        counts = {
            "students": Student.objects.count(),
            "active_students": Student.objects.filter(status=Student.Status.ACTIVE).count(),
            "teachers": Teacher.objects.filter(status=Teacher.Status.ACTIVE).count(),
            "departments": Department.objects.count(),
            "courses": Course.objects.filter(is_active=True).count(),
            "subjects": Subject.objects.filter(is_active=True).count(),
            "attendance_today": Attendance.objects.filter(date=today).count(),
            "exams": Exam.objects.count(),
            "pending_fees": fee_summary.count(),
            "pending_fees_amount": float(
                fee_summary.aggregate(total=Sum("amount"))["total"] or 0
            ),
            "payments_month": Payment.objects.filter(
                payment_date__year=today.year, payment_date__month=today.month
            ).count(),
        }
        return counts
    except Exception:  # pragma: no cover - DB not ready / missing tables
        return {}
