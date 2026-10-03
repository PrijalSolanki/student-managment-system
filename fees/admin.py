from django.contrib import admin

from fees.models import FeeRecord, FeeStructure, FeeType, Payment


@admin.register(FeeType)
class FeeTypeAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "is_mandatory", "is_active")
    list_filter = ("is_active", "is_mandatory")
    search_fields = ("name", "code")


@admin.register(FeeStructure)
class FeeStructureAdmin(admin.ModelAdmin):
    list_display = ("fee_type", "department", "course", "semester", "amount", "frequency", "academic_year", "is_active")
    list_filter = ("fee_type", "frequency", "is_active")
    search_fields = ("fee_type__name", "academic_year")


@admin.register(FeeRecord)
class FeeRecordAdmin(admin.ModelAdmin):
    list_display = ("invoice_no", "student", "fee_type", "amount", "discount", "due_date", "status")
    list_filter = ("status", "fee_type", "due_date")
    search_fields = ("invoice_no", "student__student_id", "student__first_name", "student__last_name")
    date_hierarchy = "due_date"


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ("receipt_no", "student", "fee_record", "amount", "payment_date", "method", "is_cancelled")
    list_filter = ("method", "is_cancelled", "payment_date")
    search_fields = ("receipt_no", "reference_no", "student__student_id")
    date_hierarchy = "payment_date"