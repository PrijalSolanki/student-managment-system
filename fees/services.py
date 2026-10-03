"""Invoice generation, payment allocation and fee reporting."""

from __future__ import annotations

from decimal import Decimal

from django.db import transaction
from django.db.models import Count, DecimalField, F, Q, Sum, Value
from django.db.models.functions import Coalesce
from django.utils import timezone


def net_amount_expr():
    """``SUM(amount - discount)`` that also works when there are no rows."""
    return Coalesce(
        Sum(F("amount") - F("discount")),
        Value(Decimal("0")),
        output_field=DecimalField(max_digits=14, decimal_places=2),
    )


def fee_summary() -> dict:
    from fees.models import FeeRecord, Payment

    today = timezone.localdate()
    records = FeeRecord.objects.exclude(status=FeeRecord.Status.CANCELLED)
    totals = records.aggregate(
        billed=net_amount_expr(),
        records=Count("id"),
        pending_records=Count("id", filter=Q(status__in=["PENDING", "PARTIAL", "OVERDUE"])),
        paid_records=Count("id", filter=Q(status=FeeRecord.Status.PAID)),
    )
    cancelled_records = FeeRecord.objects.filter(
        status=FeeRecord.Status.CANCELLED
    ).count()
    paid = Payment.objects.filter(is_cancelled=False).aggregate(
        total=Coalesce(
            Sum("amount"),
            Value(Decimal("0")),
            output_field=DecimalField(max_digits=14, decimal_places=2),
        )
    )["total"]
    billed = totals["billed"]
    overdue = records.filter(
        status__in=[FeeRecord.Status.PENDING, FeeRecord.Status.PARTIAL], due_date__lt=today
    )
    overdue_total = sum(record.remaining_amount for record in overdue.select_related("student"))
    month_collected = Payment.objects.filter(
        is_cancelled=False, payment_date__month=today.month, payment_date__year=today.year
    ).aggregate(
        total=Coalesce(
            Sum("amount"),
            Value(Decimal("0")),
            output_field=DecimalField(max_digits=14, decimal_places=2),
        )
    )["total"]
    return {
        "billed": float(billed or 0),
        "collected": float(paid or 0),
        "pending": round(max(0.0, float(billed or 0) - float(paid or 0)), 2),
        "records": totals["records"],
        "pending_records": totals["pending_records"],
        "paid_records": totals["paid_records"],
        "cancelled_records": cancelled_records,
        "overdue_records": overdue.count(),
        "overdue_amount": round(overdue_total, 2),
        "month_collected": float(month_collected or 0),
        "collection_percentage": round(
            (float(paid or 0) / float(billed)) * 100, 2
        )
        if billed
        else 0.0,
    }


def collection_by_method(start=None, end=None) -> list[dict]:
    from fees.models import Payment

    queryset = Payment.objects.filter(is_cancelled=False)
    if start:
        queryset = queryset.filter(payment_date__gte=start)
    if end:
        queryset = queryset.filter(payment_date__lte=end)
    rows = (
        queryset.values("method")
        .annotate(
            total=Coalesce(
                Sum("amount"),
                Value(Decimal("0")),
                output_field=DecimalField(max_digits=14, decimal_places=2),
            ),
            count=Count("id"),
        )
        .order_by("-total")
    )
    return [
        {
            "method": row["method"],
            "method_display": dict(Payment.Method.choices).get(row["method"], row["method"]),
            "total": float(row["total"] or 0),
            "count": row["count"],
        }
        for row in rows
    ]


def student_ledger(student) -> list[dict]:
    """Chronological ledger: invoices and payments as signed amounts."""
    from fees.models import FeeRecord, Payment

    entries = []
    for record in FeeRecord.objects.filter(student=student).exclude(
        status=FeeRecord.Status.CANCELLED
    ):
        entries.append(
            {
                "date": record.due_date,
                "type": "Invoice",
                "reference": record.invoice_no,
                "description": f"{record.fee_type.name}",
                "debit": record.net_amount,
                "credit": 0,
                "status": record.get_status_display(),
            }
        )
    for payment in Payment.objects.filter(student=student, is_cancelled=False):
        entries.append(
            {
                "date": payment.payment_date,
                "type": "Payment",
                "reference": payment.receipt_no,
                "description": payment.get_method_display(),
                "debit": 0,
                "credit": float(payment.amount),
                "status": "Received",
            }
        )
    entries.sort(key=lambda item: (item["date"], item["type"]))
    running = 0.0
    for entry in entries:
        running += entry["debit"] - entry["credit"]
        entry["balance"] = round(running, 2)
    return entries


@transaction.atomic
def record_payment(
    student,
    amount,
    payment_date=None,
    method="CASH",
    reference_no="",
    remarks="",
    received_by=None,
    fee_record=None,
) -> tuple:
    """Record one payment and refresh every affected invoice status."""
    from fees.models import Payment

    payment = Payment.objects.create(
        student=student,
        fee_record=fee_record,
        amount=Decimal(str(amount)),
        payment_date=payment_date or timezone.localdate(),
        method=method,
        reference_no=reference_no,
        remarks=remarks,
        received_by=received_by,
    )
    touched = []
    if fee_record is not None:
        fee_record.refresh_status()
        fee_record.save(update_fields=["status", "updated_at"])
        touched.append(fee_record)
    return payment, touched


@transaction.atomic
def pay_oldest_first(student, amount, **kwargs) -> list:
    """Spread a payment over the oldest unpaid invoices."""
    from fees.models import FeeRecord

    remaining = Decimal(str(amount))
    applied = []
    queryset = (
        FeeRecord.objects.filter(student=student)
        .exclude(status__in=[FeeRecord.Status.PAID, FeeRecord.Status.CANCELLED])
        .order_by("due_date")
    )
    for record in queryset:
        if remaining <= 0:
            break
        outstanding = Decimal(str(record.remaining_amount))
        if outstanding <= 0:
            continue
        share = min(outstanding, remaining)
        payment, _ = record_payment(
            student, share, fee_record=record, **kwargs
        )
        applied.append(payment)
        remaining -= share
    return applied


@transaction.atomic
def bulk_generate_invoices(
    fee_structure, students=None, due_date=None, academic_year="", user=None
) -> dict:
    """Create one invoice per student for a fee structure."""
    from fees.models import FeeRecord

    students = students if students is not None else fee_structure.students_queryset()
    created = 0
    skipped = 0
    for student in students:
        exists = FeeRecord.objects.filter(
            student=student,
            fee_type=fee_structure.fee_type,
            fee_structure=fee_structure,
            academic_year=academic_year or fee_structure.academic_year,
        ).exists()
        if exists:
            skipped += 1
            continue
        FeeRecord.objects.create(
            student=student,
            fee_type=fee_structure.fee_type,
            fee_structure=fee_structure,
            amount=fee_structure.amount,
            due_date=due_date or timezone.localdate(),
            academic_year=academic_year or fee_structure.academic_year,
            created_by=user,
        )
        created += 1
    return {"created": created, "skipped": skipped}


def default_due_date() -> str:
    """Due date one month from today (returned as ISO string for form widgets)."""
    today = timezone.localdate()
    year = today.year + (1 if today.month == 12 else 0)
    month = 1 if today.month == 12 else today.month + 1
    return today.replace(year=year, month=month, day=min(today.day, 28)).isoformat()


__all__ = [
    "fee_summary",
    "collection_by_method",
    "student_ledger",
    "record_payment",
    "pay_oldest_first",
    "bulk_generate_invoices",
    "net_amount_expr",
    "default_due_date",
]