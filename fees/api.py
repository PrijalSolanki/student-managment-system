"""REST API for fees, invoices and payments."""

from __future__ import annotations

from django.db.models import Sum
from rest_framework import serializers, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from core.api_pagination import LargeResultsSetPagination
from core.api_permissions import IsAdminOrStaff
from core.models import AuditLog
from core.permissions import log_action
from fees.models import FeeRecord, FeeStructure, FeeType, Payment
from fees.services import collection_by_method, fee_summary, pay_oldest_first, record_payment


class FeeTypeSerializer(serializers.ModelSerializer):
    record_count = serializers.IntegerField(source="fee_records.count", read_only=True)

    class Meta:
        model = FeeType
        fields = ["id", "name", "code", "description", "is_mandatory", "is_active", "record_count"]


class FeeStructureSerializer(serializers.ModelSerializer):
    fee_type_name = serializers.CharField(source="fee_type.name", read_only=True)
    course_name = serializers.CharField(source="course.name", read_only=True)
    department_name = serializers.CharField(source="department.name", read_only=True)
    semester_name = serializers.CharField(source="semester.name", read_only=True)

    class Meta:
        model = FeeStructure
        fields = [
            "id",
            "fee_type",
            "fee_type_name",
            "department",
            "department_name",
            "course",
            "course_name",
            "semester",
            "semester_name",
            "amount",
            "frequency",
            "academic_year",
            "is_active",
            "description",
        ]


class FeeRecordSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source="student.full_name", read_only=True)
    student_code = serializers.CharField(source="student.student_id", read_only=True)
    fee_type_name = serializers.CharField(source="fee_type.name", read_only=True)
    net_amount = serializers.FloatField(read_only=True)
    paid_amount = serializers.FloatField(read_only=True)
    remaining_amount = serializers.FloatField(read_only=True)

    class Meta:
        model = FeeRecord
        fields = [
            "id",
            "invoice_no",
            "student",
            "student_code",
            "student_name",
            "fee_type",
            "fee_type_name",
            "fee_structure",
            "amount",
            "discount",
            "net_amount",
            "paid_amount",
            "remaining_amount",
            "due_date",
            "status",
            "academic_year",
            "notes",
            "created_at",
        ]
        read_only_fields = ["invoice_no", "status", "created_at"]

    def validate(self, attrs):
        amount = attrs.get("amount")
        discount = attrs.get("discount") or 0
        if amount is not None and discount > amount:
            raise serializers.ValidationError({"discount": "Discount cannot exceed the amount."})
        return attrs


class PaymentSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source="student.full_name", read_only=True)
    student_code = serializers.CharField(source="student.student_id", read_only=True)
    invoice_no = serializers.CharField(source="fee_record.invoice_no", read_only=True)

    class Meta:
        model = Payment
        fields = [
            "id",
            "receipt_no",
            "student",
            "student_code",
            "student_name",
            "fee_record",
            "invoice_no",
            "amount",
            "payment_date",
            "method",
            "reference_no",
            "remarks",
            "is_cancelled",
            "received_by",
            "created_at",
        ]
        read_only_fields = ["receipt_no", "is_cancelled", "created_at"]

    def validate_amount(self, value):
        if value is not None and value <= 0:
            raise serializers.ValidationError("Payment amount must be greater than zero.")
        return value

    def validate(self, attrs):
        amount = attrs.get("amount")
        fee_record = attrs.get("fee_record") or getattr(self.instance, "fee_record", None)
        student = attrs.get("student") or getattr(self.instance, "student", None)
        if fee_record and student and fee_record.student_id != student.pk:
            raise serializers.ValidationError(
                {"fee_record": f"Invoice {fee_record.invoice_no} belongs to another student."}
            )
        if fee_record and amount and amount > fee_record.remaining_amount:
            raise serializers.ValidationError(
                {
                    "amount": (
                        f"Amount exceeds the outstanding balance of "
                        f"{fee_record.remaining_amount} on {fee_record.invoice_no}."
                    )
                }
            )
        return attrs

    def create(self, validated_data):
        request = self.context.get("request")
        fee_record = validated_data.pop("fee_record", None)
        payment = super().create(validated_data)
        if fee_record:
            payment.fee_record = fee_record
            payment.save(update_fields=["fee_record"])
            fee_record.refresh_status()
            fee_record.save(update_fields=["status", "updated_at"])
        log_action(
            request,
            AuditLog.Action.CREATE,
            module="fees",
            obj=payment,
            description=f"Payment {payment.receipt_no} received via API",
        )
        return payment


class FeeTypeViewSet(viewsets.ModelViewSet):
    queryset = FeeType.objects.all()
    serializer_class = FeeTypeSerializer
    permission_classes = [IsAdminOrStaff]
    pagination_class = LargeResultsSetPagination
    filterset_fields = ["is_active", "is_mandatory"]
    search_fields = ["name", "code"]


class FeeStructureViewSet(viewsets.ModelViewSet):
    queryset = FeeStructure.objects.select_related("fee_type", "course", "semester", "department")
    serializer_class = FeeStructureSerializer
    permission_classes = [IsAdminOrStaff]
    pagination_class = LargeResultsSetPagination
    filterset_fields = ["fee_type", "course", "semester", "department", "is_active"]
    search_fields = ["fee_type__name", "academic_year"]

    @action(detail=True, methods=["post"])
    def generate_invoices(self, request, pk=None):
        from django.utils import timezone

        from fees.services import bulk_generate_invoices

        structure = self.get_object()
        summary = bulk_generate_invoices(
            structure, due_date=timezone.localdate(), user=request.user
        )
        log_action(
            request,
            AuditLog.Action.CREATE,
            module="fees",
            obj=structure,
            description=f"Invoices generated via API: {summary}",
        )
        return Response(summary)


class FeeRecordViewSet(viewsets.ModelViewSet):
    queryset = FeeRecord.objects.select_related("student", "fee_type")
    serializer_class = FeeRecordSerializer
    permission_classes = [IsAdminOrStaff]
    pagination_class = LargeResultsSetPagination
    filterset_fields = ["student", "fee_type", "status", "due_date", "academic_year"]
    search_fields = ["invoice_no", "student__student_id", "student__first_name"]
    ordering_fields = ["due_date", "amount", "created_at"]

    @action(detail=False, methods=["get"])
    def summary(self, request):
        return Response(fee_summary())

    @action(detail=False, methods=["get"])
    def overdue(self, request):
        from django.utils import timezone

        queryset = self.get_queryset().filter(
            status__in=[FeeRecord.Status.PENDING, FeeRecord.Status.PARTIAL],
            due_date__lt=timezone.localdate(),
        )
        page = self.paginate_queryset(queryset)
        serializer = self.get_serializer(page if page is not None else queryset, many=True)
        return (
            self.get_paginated_response(serializer.data)
            if page is not None
            else Response(serializer.data)
        )


class PaymentViewSet(viewsets.ModelViewSet):
    queryset = Payment.objects.select_related("student", "fee_record")
    serializer_class = PaymentSerializer
    permission_classes = [IsAdminOrStaff]
    pagination_class = LargeResultsSetPagination
    filterset_fields = ["student", "method", "is_cancelled", "payment_date"]
    search_fields = ["receipt_no", "reference_no", "student__student_id"]
    ordering_fields = ["payment_date", "amount"]

    def perform_create(self, serializer):
        serializer.save(received_by=self.request.user)

    @action(detail=False, methods=["get"])
    def by_method(self, request):
        return Response(collection_by_method())

    @action(detail=False, methods=["post"])
    def settle_oldest(self, request):
        """Allocate an amount to a student's oldest unpaid invoices."""
        student_id = request.data.get("student")
        amount = request.data.get("amount")
        if not student_id or not amount:
            return Response({"detail": "'student' and 'amount' are required."}, status=400)
        from students.models import Student

        student = Student.objects.filter(pk=student_id).first()
        if not student:
            return Response({"detail": "Student not found."}, status=404)
        payments = pay_oldest_first(
            student=student,
            amount=amount,
            payment_date=None,
            method=request.data.get("method", "CASH"),
            reference_no=request.data.get("reference_no", ""),
            remarks=request.data.get("remarks", ""),
            received_by=request.user,
        )
        log_action(
            request,
            AuditLog.Action.CREATE,
            module="fees",
            obj=student,
            description=f"{len(payments)} payment(s) allocated via API",
        )
        return Response(
            PaymentSerializer(payments, many=True, context=self.get_serializer_context()).data
        )

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        payment = self.get_object()
        if payment.is_cancelled:
            return Response({"detail": "Already cancelled."})
        payment.cancel()
        log_action(
            request,
            AuditLog.Action.UPDATE,
            module="fees",
            obj=payment,
            description=f"Payment {payment.receipt_no} cancelled via API",
        )
        return Response(self.get_serializer(payment).data)