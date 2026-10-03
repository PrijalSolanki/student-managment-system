"""Tests for invoice balances, payment recording and fee services."""

from datetime import date, timedelta
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from fees.models import FeeRecord, FeeType, Payment
from fees.services import bulk_generate_invoices, pay_oldest_first, record_payment


class FeeTestBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        from accounts.models import User
        from academics.models import Batch, Course, Department, Semester
        from students.models import Student

        cls.user = User.objects.create_superuser(username="fee_admin", password="x")
        department = Department.objects.create(code="CSE", name="Computer Science")
        course = Course.objects.create(
            code="BTCS", name="B.Tech CS", department=department, total_semesters=8
        )
        batch = Batch.objects.create(
            name="2023-2027", start_year=2023, end_year=2027, department=department
        )
        semester = Semester.objects.create(number=1, name="Semester 1")

        cls.student = Student.objects.create(
            first_name="Diya",
            email="diya@example.com",
            phone="9812300020",
            date_of_birth=date(2004, 2, 2),
            admission_date=date(2023, 7, 1),
            department=department,
            course=course,
            batch=batch,
            semester=semester,
            created_by=cls.user,
        )
        cls.fee_type = FeeType.objects.create(name="Tuition Fee", code="TUI")


class InvoiceNumberTests(FeeTestBase):
    def test_invoice_number_is_generated(self):
        record = FeeRecord.objects.create(
            student=self.student,
            fee_type=self.fee_type,
            amount=Decimal("1000"),
            due_date=timezone.localdate() + timedelta(days=30),
        )
        self.assertTrue(record.invoice_no.startswith("INV"))
        self.assertEqual(len(record.invoice_no), 9)

    def test_discount_reduces_net_amount(self):
        record = FeeRecord.objects.create(
            student=self.student,
            fee_type=self.fee_type,
            amount=Decimal("1000"),
            discount=Decimal("250"),
            due_date=timezone.localdate() + timedelta(days=30),
        )
        self.assertEqual(record.net_amount, 750.0)
        self.assertEqual(record.remaining_amount, 750.0)

    def test_discount_cannot_exceed_amount(self):
        from django.core.exceptions import ValidationError

        record = FeeRecord(
            student=self.student,
            fee_type=self.fee_type,
            amount=Decimal("100"),
            discount=Decimal("500"),
            due_date=timezone.localdate(),
        )
        with self.assertRaises(ValidationError):
            record.full_clean()


class InvoiceStatusTests(FeeTestBase):
    def _invoice(self, amount="1000", due_in_days=30):
        return FeeRecord.objects.create(
            student=self.student,
            fee_type=self.fee_type,
            amount=Decimal(amount),
            due_date=timezone.localdate() + timedelta(days=due_in_days),
        )

    def test_future_invoice_starts_pending(self):
        self.assertEqual(self._invoice().status, FeeRecord.Status.PENDING)

    def test_past_invoice_starts_overdue(self):
        self.assertEqual(self._invoice(due_in_days=-5).status, FeeRecord.Status.OVERDUE)

    def test_partial_payment(self):
        record = self._invoice()
        record_payment(self.student, Decimal("400"), fee_record=record)
        record.refresh_from_db()
        self.assertEqual(record.status, FeeRecord.Status.PARTIAL)
        self.assertEqual(record.paid_amount, 400.0)
        self.assertEqual(record.remaining_amount, 600.0)
        self.assertEqual(record.payment_percentage, 40.0)

    def test_full_payment_marks_paid(self):
        record = self._invoice()
        record_payment(self.student, Decimal("1000"), fee_record=record)
        record.refresh_from_db()
        self.assertEqual(record.status, FeeRecord.Status.PAID)
        self.assertEqual(record.remaining_amount, 0.0)

    def test_cancelled_payment_is_ignored(self):
        record = self._invoice()
        payment, _ = record_payment(self.student, Decimal("1000"), fee_record=record)
        Payment.objects.filter(pk=payment.pk).update(is_cancelled=True)
        record.refresh_from_db()
        record.refresh_status()
        self.assertEqual(record.paid_amount, 0.0)
        self.assertEqual(record.remaining_amount, 1000.0)

    def test_overdue_helpers(self):
        record = self._invoice(due_in_days=-3)
        self.assertTrue(record.is_overdue)
        self.assertEqual(record.days_overdue, 3)

    def test_invoice_with_payments_cannot_be_deleted(self):
        from django.core.exceptions import ValidationError

        record = self._invoice()
        record_payment(self.student, Decimal("100"), fee_record=record)
        with self.assertRaises(ValidationError):
            record.delete()


class ReceiptNumberTests(FeeTestBase):
    def test_receipt_numbers_are_sequential_and_unique(self):
        record = FeeRecord.objects.create(
            student=self.student,
            fee_type=self.fee_type,
            amount=Decimal("500"),
            due_date=timezone.localdate() + timedelta(days=10),
        )
        first, _ = record_payment(self.student, Decimal("100"), fee_record=record)
        second, _ = record_payment(self.student, Decimal("100"), fee_record=record)
        year = timezone.localdate().year
        self.assertEqual(first.receipt_no, f"RCPT-{year}-00001")
        self.assertEqual(second.receipt_no, f"RCPT-{year}-00002")


class PayOldestFirstTests(FeeTestBase):
    def _invoice(self, amount, due_in_days):
        return FeeRecord.objects.create(
            student=self.student,
            fee_type=self.fee_type,
            amount=Decimal(amount),
            due_date=timezone.localdate() + timedelta(days=due_in_days),
        )

    def test_payment_is_split_across_invoices_in_due_date_order(self):
        older = self._invoice("1000", 10)
        newer = self._invoice("1000", 20)
        applied = pay_oldest_first(self.student, Decimal("1500"), method="CASH")
        self.assertEqual(len(applied), 2)
        older.refresh_from_db()
        newer.refresh_from_db()
        self.assertEqual(older.status, FeeRecord.Status.PAID)
        self.assertEqual(newer.status, FeeRecord.Status.PARTIAL)

    def test_excess_payment_is_ignored(self):
        self._invoice("1000", 10)
        applied = pay_oldest_first(self.student, Decimal("5000"))
        self.assertEqual(len(applied), 1)
        self.assertEqual(applied[0].amount, Decimal("1000.00"))

    def test_no_invoices_creates_no_payments(self):
        self.assertEqual(pay_oldest_first(self.student, Decimal("500")), [])


class BulkInvoiceTests(FeeTestBase):
    def test_generation_skips_existing_invoices(self):
        from fees.models import FeeStructure

        department = self.student.department
        course = self.student.course
        semester = self.student.semester
        structure = FeeStructure.objects.create(
            fee_type=self.fee_type,
            course=course,
            semester=semester,
            department=department,
            amount=Decimal("2500"),
            academic_year="2024-2025",
        )
        first = bulk_generate_invoices(
            structure, due_date=timezone.localdate(), academic_year="2024-2025"
        )
        second = bulk_generate_invoices(
            structure, due_date=timezone.localdate(), academic_year="2024-2025"
        )
        self.assertEqual(first["created"], 1)
        self.assertEqual(second["created"], 0)
        self.assertEqual(second["skipped"], 1)
        self.assertEqual(
            FeeRecord.objects.filter(student=self.student, fee_structure=structure).count(), 1
        )