from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Count, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.views.generic import CreateView, DeleteView, DetailView, UpdateView

from academics.models import Course, Department, Semester
from core.mixins import FilterableListView, FormSuccessMixin, ProtectedDeleteMixin
from core.models import AuditLog
from core.permissions import AdminRequiredMixin, StaffRequiredMixin, log_action, staff_required
from core.utils import paginate, parse_date
from fees.forms import (
    BulkInvoiceForm,
    FeeRecordFilterForm,
    FeeRecordForm,
    FeeStructureForm,
    FeeTypeForm,
    PaymentFilterForm,
    PaymentForm,
)
from fees.models import FeeRecord, FeeStructure, FeeType, Payment
from fees.services import (
    bulk_generate_invoices,
    collection_by_method,
    default_due_date,
    fee_summary,
    pay_oldest_first,
    record_payment,
    student_ledger,
)
from students.models import Student


# --------------------------------------------------------------------- fee type
class FeeTypeListView(StaffRequiredMixin, FilterableListView):
    model = FeeType
    template_name = "fees/fee_type_list.html"
    context_object_name = "fee_types"
    list_title = "Fee Types"
    active_menu = "fees"
    breadcrumb_parent = "Fees"
    module_name = "fee_types"
    paginate_by = 15
    search_fields = ["name", "code", "description"]
    filter_fields = []
    ordering_fields = {"name": "name", "-name": "-name", "created": "-created_at"}
    default_ordering = "name"

    def get_queryset(self):
        queryset = FeeType.objects.annotate(record_total=Count("fee_records"))
        queryset = self.filter_queryset(queryset)
        active = (self.request.GET.get("is_active") or "").strip()
        if active == "true":
            queryset = queryset.filter(is_active=True)
        elif active == "false":
            queryset = queryset.filter(is_active=False)
        return queryset.order_by(self.get_ordering())

    def get_filter_choices(self):
        return {
            "is_active": [("true", "Active"), ("false", "Inactive")],
        }

    def get_table_columns(self):
        return [
            {"label": "Code", "attr": "code", "sort": "name"},
            {"label": "Name", "attr": "name", "sort": "-name"},
            {"label": "Mandatory", "attr": "is_mandatory", "bool": True},
            {"label": "Active", "attr": "is_active", "bool": True},
            {"label": "Invoices", "attr": "record_total", "align": "center"},
            {"label": "Description", "attr": "description"},
        ]

    def get_table_actions(self):
        return {
            "edit": "fees:fee_type_edit",
            "delete": "fees:fee_type_delete",
        }

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(
            {
                "total_types": FeeType.objects.count(),
                "active_types": FeeType.objects.filter(is_active=True).count(),
            }
        )
        return context

    def get_export_rows(self, queryset=None):
        queryset = queryset if queryset is not None else self.get_queryset()
        headers = ["Code", "Name", "Mandatory", "Active", "Records", "Description"]
        rows = [
            [item.code, item.name, "Yes" if item.is_mandatory else "No",
             "Yes" if item.is_active else "No", item.record_total, item.description]
            for item in queryset
        ]
        return headers, rows


class FeeTypeCreateView(StaffRequiredMixin, FormSuccessMixin, CreateView):
    model = FeeType
    form_class = FeeTypeForm
    template_name = "fees/fee_type_form.html"
    success_url = "/fees/types/"
    created_message = "Fee type '%(object)s' created."


class FeeTypeUpdateView(StaffRequiredMixin, FormSuccessMixin, UpdateView):
    model = FeeType
    form_class = FeeTypeForm
    template_name = "fees/fee_type_form.html"
    success_url = "/fees/types/"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({"page_title": f"Edit {self.object.name}", "active_menu": "fees"})
        return context


class FeeTypeDeleteView(AdminRequiredMixin, ProtectedDeleteMixin, DeleteView):
    model = FeeType
    template_name = "fees/confirm_delete.html"
    success_url = "/fees/types/"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(
            {
                "page_title": f"Delete {self.object.name}",
                "breadcrumb_parent": "Fee Types",
                "blocking_reason": (
                    f"{self.object.fee_records.count()} invoice(s) use this fee type."
                    if self.object.fee_records.exists()
                    else "Fee types used in invoices cannot be removed."
                ),
            }
        )
        return context


# -------------------------------------------------------------- fee structure
class FeeStructureListView(StaffRequiredMixin, FilterableListView):
    model = FeeStructure
    template_name = "fees/fee_structure_list.html"
    context_object_name = "structures"
    list_title = "Fee Structures"
    active_menu = "fees"
    breadcrumb_parent = "Fees"
    module_name = "fee_structures"
    search_fields = ["fee_type__name", "academic_year", "description"]
    filter_fields = ["fee_type", "course", "semester", "department"]
    filter_lookups = {
        "fee_type": "fee_type_id",
        "course": "course_id",
        "semester": "semester_id",
        "department": "department_id",
    }
    ordering_fields = {"amount": "-amount", "-amount": "amount", "created": "-created_at"}
    default_ordering = "fee_type__name"

    def get_queryset(self):
        queryset = FeeStructure.objects.select_related(
            "fee_type", "course", "semester", "department"
        ).annotate(billed=Count("billed_records"))
        return self.filter_queryset(queryset).order_by(self.get_ordering(), "id")

    def get_filter_choices(self):
        return {
            "fee_type": [(item.pk, item.name) for item in FeeType.objects.order_by("name")],
            "department": [(item.pk, item.name) for item in Department.objects.order_by("name")],
            "course": [(item.pk, item.name) for item in Course.objects.order_by("name")],
            "semester": [(item.pk, item.name) for item in Semester.objects.order_by("number")],
        }

    def get_table_columns(self):
        return [
            {"label": "Fee type", "attr": "fee_type.name"},
            {"label": "Scope", "attr": "scope_label"},
            {"label": "Amount", "attr": "amount", "money": True, "align": "end", "sort": "amount"},
            {"label": "Frequency", "attr": "get_frequency_display"},
            {"label": "Year", "attr": "academic_year", "align": "center"},
            {"label": "Active", "attr": "is_active", "bool": True},
            {"label": "Invoices", "attr": "billed", "align": "center"},
        ]

    def get_table_actions(self):
        return {
            "edit": "fees:fee_structure_edit",
            "delete": "fees:fee_structure_delete",
        }

    def get_export_rows(self, queryset=None):
        queryset = queryset if queryset is not None else self.get_queryset()
        headers = ["Fee Type", "Department", "Course", "Semester", "Amount", "Frequency", "Year", "Active", "Invoices"]
        rows = [
            [
                item.fee_type.name,
                item.department.name if item.department_id else "-",
                item.course.name if item.course_id else "-",
                item.semester.name if item.semester_id else "-",
                item.amount,
                item.frequency,
                item.academic_year,
                "Yes" if item.is_active else "No",
                item.billed,
            ]
            for item in queryset
        ]
        return headers, rows


class FeeStructureCreateView(StaffRequiredMixin, FormSuccessMixin, CreateView):
    model = FeeStructure
    form_class = FeeStructureForm
    template_name = "fees/fee_structure_form.html"
    success_url = "/fees/structures/"


class FeeStructureUpdateView(StaffRequiredMixin, FormSuccessMixin, UpdateView):
    model = FeeStructure
    form_class = FeeStructureForm
    template_name = "fees/fee_structure_form.html"
    success_url = "/fees/structures/"


class FeeStructureDeleteView(AdminRequiredMixin, ProtectedDeleteMixin, DeleteView):
    model = FeeStructure
    template_name = "fees/confirm_delete.html"
    success_url = "/fees/structures/"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(
            {
                "page_title": "Delete Fee Structure",
                "breadcrumb_parent": "Fee Structures",
                "blocking_reason": (
                    f"{self.object.billed_records.count()} invoice(s) were generated from this structure."
                    if self.object.billed_records.exists()
                    else "This structure will be permanently removed."
                ),
            }
        )
        return context


@staff_required
def bulk_invoice_generate(request):
    """Create invoices for every student in the selected scope."""
    requested = request.GET.get("structure") or request.POST.get("fee_structure")
    if requested:
        structure = get_object_or_404(
            FeeStructure.objects.select_related("fee_type"), pk=requested
        )
    else:
        structure = (
            FeeStructure.objects.filter(is_active=True)
            .select_related("fee_type")
            .order_by("fee_type__name")
            .first()
        )
    initial = {"due_date": parse_date(request.GET.get("due_date"))}
    if structure:
        initial["fee_structure"] = structure.pk
    form = BulkInvoiceForm(request.POST or None, initial=initial)

    if request.method == "POST" and form.is_valid():
        chosen = form.cleaned_data["fee_structure"]
        students = list(form.resolve_students())
        if not students:
            messages.warning(request, "No students matched the selected scope.")
        else:
            with transaction.atomic():
                created = 0
                skipped = 0
                amount = form.cleaned_data.get("amount") or chosen.amount
                discount = form.cleaned_data.get("discount") or 0
                year = form.cleaned_data.get("academic_year") or chosen.academic_year
                for student in students:
                    exists = FeeRecord.objects.filter(
                        student=student,
                        fee_type=chosen.fee_type,
                        academic_year=year,
                        due_date=form.cleaned_data["due_date"],
                    ).exists()
                    if exists:
                        skipped += 1
                        continue
                    FeeRecord.objects.create(
                        student=student,
                        fee_type=chosen.fee_type,
                        fee_structure=chosen,
                        amount=amount,
                        discount=discount,
                        due_date=form.cleaned_data["due_date"],
                        academic_year=year,
                        created_by=request.user,
                    )
                    created += 1
            log_action(
                request,
                AuditLog.Action.CREATE,
                module="fees",
                obj=chosen,
                description=f"Generated {created} invoice(s) for {chosen} ({skipped} skipped)",
            )
            messages.success(
                request,
                f"Generated {created} invoice(s); {skipped} duplicate(s) skipped.",
            )
            return redirect(reverse("fees:fee_record_list"))

    preview_count = 0
    if request.method == "POST" and form.is_valid():
        preview_count = form.resolve_students().count()
    elif structure:
        preview_count = structure.students_queryset().count()

    return render(
        request,
        "fees/bulk_invoice.html",
        {
            "form": form,
            "structure": structure,
            "page_title": "Generate Invoices",
            "active_menu": "fees",
            "breadcrumb_parent": "Fees",
            "preview_count": preview_count,
        },
    )


@staff_required
@require_POST
def bulk_invoice_generate_structure(request, pk):
    structure = get_object_or_404(FeeStructure, pk=pk)
    summary = bulk_generate_invoices(
        structure,
        due_date=timezone.localdate(),
        user=request.user,
    )
    log_action(
        request,
        AuditLog.Action.CREATE,
        module="fees",
        obj=structure,
        description=f"Bulk invoices generated: {summary}",
    )
    messages.success(
        request,
        f"Generated {summary['created']} invoice(s); {summary['skipped']} already existed.",
    )
    return redirect(reverse("fees:fee_record_list"))


# ----------------------------------------------------------------- fee record
class FeeRecordListView(StaffRequiredMixin, FilterableListView):
    model = FeeRecord
    template_name = "fees/fee_record_list.html"
    context_object_name = "records"
    list_title = "Fee Records"
    active_menu = "fees"
    breadcrumb_parent = "Fees"
    module_name = "fee_records"
    search_fields = ["invoice_no", "student__first_name", "student__last_name", "student__student_id"]
    filter_fields = ["status", "fee_type", "student", "department", "course"]
    filter_lookups = {
        "status": "status",
        "fee_type": "fee_type_id",
        "student": "student_id",
        "department": "student__department_id",
        "course": "student__course_id",
    }
    date_range_fields = ["due_date"]
    ordering_fields = {
        "amount": "-amount",
        "-amount": "amount",
        "student": "student__student_id",
        "due_date": "due_date",
        "created": "-created_at",
    }
    default_ordering = "-due_date"

    def get_queryset(self):
        queryset = FeeRecord.objects.select_related("student", "fee_type", "fee_structure")
        queryset = self.filter_queryset(queryset)
        if (self.request.GET.get("overdue_only") or "").lower() in {"on", "1", "true"}:
            queryset = queryset.filter(
                status__in=[FeeRecord.Status.PENDING, FeeRecord.Status.PARTIAL],
                due_date__lt=timezone.localdate(),
            )
        return queryset.order_by(self.get_ordering())

    def get_filter_choices(self):
        return {
            "status": list(FeeRecord.Status.choices),
            "fee_type": [(item.pk, item.name) for item in FeeType.objects.order_by("name")],
            "department": [(item.pk, item.name) for item in Department.objects.order_by("name")],
            "course": [(item.pk, item.name) for item in Course.objects.order_by("name")],
        }

    def get_table_columns(self):
        return [
            {"label": "Invoice", "attr": "invoice_no"},
            {"label": "Student", "attr": "student.full_name", "sort": "student"},
            {"label": "Code", "attr": "student.student_id"},
            {"label": "Fee type", "attr": "fee_type.name"},
            {"label": "Net", "attr": "net_amount", "money": True, "align": "end", "sort": "amount"},
            {"label": "Paid", "attr": "paid_amount", "money": True, "align": "end"},
            {"label": "Balance", "attr": "remaining_amount", "money": True, "align": "end"},
            {"label": "Status", "attr": "status", "badge": "status_badge"},
            {"label": "Due", "attr": "due_date", "date": "d M Y", "sort": "due_date"},
        ]

    def get_table_actions(self):
        return {
            "detail": "fees:fee_record_detail",
            "edit": "fees:fee_record_edit",
            "delete": "fees:fee_record_delete",
            "extra": [{"url": "fees:fee_record_invoice", "label": "Invoice", "icon": "bi-printer"}],
        }

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({"filter_form": FeeRecordFilterForm(self.request.GET or None), **fee_summary()})
        return context

    def get_export_rows(self, queryset=None):
        queryset = queryset if queryset is not None else self.get_queryset()
        headers = [
            "Invoice",
            "Student",
            "Code",
            "Fee Type",
            "Amount",
            "Discount",
            "Net",
            "Paid",
            "Remaining",
            "Status",
            "Due Date",
            "Year",
        ]
        rows = [
            [
                record.invoice_no,
                record.student.full_name,
                record.student.student_id,
                record.fee_type.name,
                record.amount,
                record.discount,
                record.net_amount,
                record.paid_amount,
                record.remaining_amount,
                record.get_status_display(),
                record.due_date,
                record.academic_year,
            ]
            for record in queryset
        ]
        return headers, rows


class FeeRecordCreateView(StaffRequiredMixin, FormSuccessMixin, CreateView):
    model = FeeRecord
    form_class = FeeRecordForm
    template_name = "fees/fee_record_form.html"
    success_url = "/fees/records/"

    def get_initial(self):
        initial = super().get_initial()
        initial.setdefault("due_date", default_due_date())
        initial.setdefault("academic_year", f"{timezone.localdate().year}-{timezone.localdate().year + 1}")
        return initial

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        response = super().form_valid(form)
        log_action(
            self.request,
            AuditLog.Action.CREATE,
            module="fees",
            obj=self.object,
            description=f"Invoice {self.object.invoice_no} raised for {self.object.student.full_name}",
        )
        return response


class FeeRecordUpdateView(StaffRequiredMixin, FormSuccessMixin, UpdateView):
    model = FeeRecord
    form_class = FeeRecordForm
    template_name = "fees/fee_record_form.html"
    success_url = "/fees/records/"


class FeeRecordDetailView(StaffRequiredMixin, DetailView):
    model = FeeRecord
    template_name = "fees/fee_record_detail.html"
    context_object_name = "record"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        record = self.object
        context.update(
            {
                "page_title": record.invoice_no,
                "active_menu": "fees",
                "breadcrumb_parent": "Fee Records",
                "payments": record.payments.select_related("received_by").order_by("-payment_date"),
                "ledger": student_ledger(record.student),
            }
        )
        return context


class FeeRecordDeleteView(AdminRequiredMixin, ProtectedDeleteMixin, DeleteView):
    model = FeeRecord
    template_name = "fees/confirm_delete.html"
    success_url = "/fees/records/"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(
            {
                "page_title": f"Delete {self.object.invoice_no}",
                "breadcrumb_parent": "Fee Records",
                "blocking_reason": (
                    f"{self.object.payments.count()} payment(s) are recorded against this invoice."
                    if self.object.payments.exists()
                    else "Deleting an invoice cannot be undone."
                ),
            }
        )
        return context


@staff_required
@require_POST
def fee_record_cancel(request, pk):
    record = get_object_or_404(FeeRecord, pk=pk)
    if record.status == FeeRecord.Status.CANCELLED:
        messages.info(request, "Invoice is already cancelled.")
        return redirect(record.get_absolute_url())
    if record.payments.exists():
        messages.error(
            request,
            "Cancel the recorded payments first, then cancel the invoice.",
        )
        return redirect(record.get_absolute_url())
    record.status = FeeRecord.Status.CANCELLED
    record.save(update_fields=["status", "updated_at"])
    log_action(
        request,
        AuditLog.Action.UPDATE,
        module="fees",
        obj=record,
        description=f"Invoice {record.invoice_no} cancelled",
    )
    messages.success(request, f"Invoice {record.invoice_no} cancelled.")
    return redirect(record.get_absolute_url())


@staff_required
def fee_record_invoice(request, pk):
    """Printable invoice (HTML) or PDF."""
    record = get_object_or_404(
        FeeRecord.objects.select_related("student", "fee_type", "fee_structure"), pk=pk
    )
    if request.GET.get("format") == "pdf":
        from core.exports import export_pdf

        headers = ["Description", "Amount", "Discount", "Net", "Paid", "Balance"]
        rows = [
            [
                record.fee_type.name,
                record.amount,
                record.discount,
                record.net_amount,
                record.paid_amount,
                record.remaining_amount,
            ]
        ]
        log_action(
            request,
            AuditLog.Action.EXPORT,
            module="fees",
            obj=record,
            description=f"Invoice PDF generated for {record.invoice_no}",
        )
        return export_pdf(
            f"invoice_{record.invoice_no}",
            headers,
            rows,
            title=f"Fee Invoice {record.invoice_no}",
            meta=[
                ("Student", record.student.full_name),
                ("Student ID", record.student.student_id),
                ("Due", str(record.due_date)),
                ("Status", record.get_status_display()),
            ],
            landscape_mode=False,
        )
    return render(
        request,
        "fees/invoice_print.html",
        {
            "record": record,
            "student": record.student,
            "page_title": f"Invoice {record.invoice_no}",
        },
    )


# --------------------------------------------------------------------- payment
class PaymentListView(StaffRequiredMixin, FilterableListView):
    model = Payment
    template_name = "fees/payment_list.html"
    context_object_name = "payments"
    list_title = "Payments"
    active_menu = "payments"
    breadcrumb_parent = "Fees"
    module_name = "payments"
    search_fields = ["receipt_no", "reference_no", "student__first_name", "student__last_name", "student__student_id"]
    filter_fields = ["method", "student"]
    filter_lookups = {"method": "method", "student": "student_id"}
    date_range_fields = ["payment_date"]
    ordering_fields = {
        "amount": "-amount",
        "-amount": "amount",
        "date": "-payment_date",
        "student": "student__student_id",
    }
    default_ordering = "-payment_date"

    def get_queryset(self):
        queryset = Payment.objects.select_related("student", "fee_record", "received_by")
        queryset = self.filter_queryset(queryset)
        if (self.request.GET.get("only_cancelled") or "").lower() in {"on", "1", "true"}:
            queryset = queryset.filter(is_cancelled=True)
        return queryset.order_by(self.get_ordering())

    def get_filter_choices(self):
        return {
            "method": list(Payment.Method.choices),
        }

    def get_table_columns(self):
        return [
            {"label": "Receipt", "attr": "receipt_no"},
            {"label": "Date", "attr": "payment_date", "date": "d M Y", "sort": "date"},
            {"label": "Student", "attr": "student.full_name", "sort": "student"},
            {"label": "Code", "attr": "student.student_id"},
            {"label": "Invoice", "attr": "applied"},
            {"label": "Amount", "attr": "amount", "money": True, "align": "end", "sort": "amount"},
            {"label": "Method", "attr": "get_method_display"},
            {"label": "Received by", "attr": "received_by.username"},
            {"label": "Status", "attr": "is_cancelled", "bool": True},
        ]

    def get_table_actions(self):
        return {
            "detail": "fees:payment_detail",
            "extra": [{"url": "fees:payment_receipt", "label": "Receipt", "icon": "bi-receipt"}],
        }

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        today = timezone.localdate()
        context.update(
            {
                "filter_form": PaymentFilterForm(self.request.GET or None),
                "today_total": Payment.objects.filter(
                    payment_date=today, is_cancelled=False
                ).aggregate(total=Sum("amount"))["total"]
                or 0,
                "month_total": Payment.objects.filter(
                    payment_date__month=today.month,
                    payment_date__year=today.year,
                    is_cancelled=False,
                ).aggregate(total=Sum("amount"))["total"]
                or 0,
                "year_total": Payment.objects.filter(
                    payment_date__year=today.year, is_cancelled=False
                ).aggregate(total=Sum("amount"))["total"]
                or 0,
            }
        )
        return context

    def get_export_rows(self, queryset=None):
        queryset = queryset if queryset is not None else self.get_queryset()
        headers = ["Receipt", "Date", "Student", "Code", "Invoice", "Amount", "Method", "Reference", "Received By", "Status"]
        rows = [
            [
                payment.receipt_no,
                payment.payment_date,
                payment.student.full_name,
                payment.student.student_id,
                payment.applied,
                payment.amount,
                payment.get_method_display(),
                payment.reference_no,
                payment.received_by.username if payment.received_by else "-",
                "Cancelled" if payment.is_cancelled else "Active",
            ]
            for payment in queryset
        ]
        return headers, rows


class PaymentCreateView(StaffRequiredMixin, CreateView):
    model = Payment
    form_class = PaymentForm
    template_name = "fees/payment_form.html"
    success_url = "/fees/payments/"

    def get_initial(self):
        initial = super().get_initial()
        initial.setdefault("payment_date", timezone.localdate())
        return initial

    def form_valid(self, form):
        self.object = form.save(commit=False)
        self.object.received_by = self.request.user
        payment = form.cleaned_data.get("fee_record")
        if payment is None:
            self.object.save()
            messages.success(
                self.request,
                f"Payment {self.object.receipt_no} recorded. No invoice selected, so it stays unallocated.",
            )
        else:
            created, touched = record_payment(
                student=self.object.student,
                amount=self.object.amount,
                payment_date=self.object.payment_date,
                method=self.object.method,
                reference_no=self.object.reference_no,
                remarks=self.object.remarks,
                received_by=self.request.user,
                fee_record=payment,
            )
            self.object = created
            messages.success(
                self.request,
                f"Payment {created.receipt_no} applied to invoice {payment.invoice_no}.",
            )
        log_action(
            self.request,
            AuditLog.Action.CREATE,
            module="fees",
            obj=self.object,
            description=f"Payment {self.object.receipt_no} of {self.object.amount} received from {self.object.student.full_name}",
        )
        return redirect(self.success_url)


@staff_required
def collect_payment(request, student_pk):
    """Collect a payment against a student, optionally settling several invoices."""
    student = get_object_or_404(Student.objects.select_related("course", "department"), pk=student_pk)
    pending = (
        FeeRecord.objects.filter(student=student)
        .exclude(status__in=[FeeRecord.Status.PAID, FeeRecord.Status.CANCELLED])
        .order_by("due_date")
    )
    total_due = round(sum(record.remaining_amount for record in pending), 2)

    if request.method == "POST":
        amount = request.POST.get("amount")
        try:
            amount = float(amount)
        except (TypeError, ValueError):
            messages.error(request, "Enter a valid payment amount.")
            return redirect("fees:collect_payment", student_pk=student.pk)

        invoice_id = request.POST.get("fee_record")
        method = request.POST.get("method", "CASH")
        allocate = request.POST.get("allocation", "oldest") == "oldest"
        kwargs = {
            "payment_date": parse_date(request.POST.get("payment_date")) or timezone.localdate(),
            "method": method,
            "reference_no": request.POST.get("reference_no", ""),
            "remarks": request.POST.get("remarks", ""),
            "received_by": request.user,
        }
        if invoice_id:
            invoice = get_object_or_404(FeeRecord, pk=invoice_id, student=student)
            if amount > invoice.remaining_amount:
                messages.error(
                    request,
                    f"Amount exceeds the outstanding balance on {invoice.invoice_no} "
                    f"({invoice.remaining_amount}).",
                )
                return redirect("fees:collect_payment", student_pk=student.pk)
            payments, _ = record_payment(
                student=student, amount=amount, fee_record=invoice, **kwargs
            )
            message = f"Payment {payments.receipt_no} applied to {invoice.invoice_no}."
        elif allocate:
            payments = pay_oldest_first(student=student, amount=amount, **kwargs)
            if not payments:
                messages.warning(request, "This student has no outstanding invoices.")
                return redirect("fees:collect_payment", student_pk=student.pk)
            message = (
                f"Collected {len(payments)} payment(s): "
                + ", ".join(payment.receipt_no for payment in payments)
            )
        else:
            payments, _ = record_payment(student=student, amount=amount, **kwargs)
            message = f"Payment {payments.receipt_no} recorded as unallocated credit."

        log_action(
            request,
            AuditLog.Action.CREATE,
            module="fees",
            obj=student,
            description=message,
        )
        messages.success(request, message)
        return redirect(reverse("fees:student_ledger", args=[student.pk]))

    return render(
        request,
        "fees/collect_payment.html",
        {
            "student": student,
            "pending": pending,
            "total_due": total_due,
            "methods": Payment.Method.choices,
            "page_title": "Collect Payment",
            "breadcrumb_parent": "Payments",
            "active_menu": "payments",
        },
    )


class PaymentDetailView(StaffRequiredMixin, DetailView):
    model = Payment
    template_name = "fees/payment_detail.html"
    context_object_name = "payment"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(
            {
                "page_title": self.object.receipt_no,
                "breadcrumb_parent": "Payments",
                "active_menu": "payments",
            }
        )
        return context


@staff_required
@require_POST
def payment_cancel(request, pk):
    payment = get_object_or_404(Payment, pk=pk)
    if payment.is_cancelled:
        messages.info(request, "Payment is already cancelled.")
        return redirect(payment.get_absolute_url())
    try:
        with transaction.atomic():
            payment.cancel()
    except ValidationError as exc:
        messages.error(request, exc.messages[0])
        return redirect(payment.get_absolute_url())
    log_action(
        request,
        AuditLog.Action.UPDATE,
        module="fees",
        obj=payment,
        description=f"Payment {payment.receipt_no} cancelled",
    )
    messages.success(request, f"Payment {payment.receipt_no} cancelled and invoice balance restored.")
    return redirect(payment.get_absolute_url())


@staff_required
def payment_receipt(request, pk):
    """Printable / PDF receipt."""
    payment = get_object_or_404(
        Payment.objects.select_related("student", "fee_record", "received_by"), pk=pk
    )
    if request.GET.get("format") == "pdf":
        from core.exports import export_pdf

        log_action(
            request,
            AuditLog.Action.EXPORT,
            module="fees",
            obj=payment,
            description=f"Receipt PDF generated for {payment.receipt_no}",
        )
        return export_pdf(
            f"receipt_{payment.receipt_no}",
            ["Receipt No", "Date", "Student", "Amount", "Method", "Invoice", "Collected By"],
            [[
                payment.receipt_no,
                payment.payment_date,
                payment.student.full_name,
                payment.amount,
                payment.get_method_display(),
                payment.applied,
                payment.received_by.username if payment.received_by else "-",
            ]],
            title=f"Payment Receipt {payment.receipt_no}",
            meta=[("Student ID", payment.student.student_id)],
            landscape_mode=False,
        )
    return render(
        request,
        "fees/receipt_print.html",
        {"payment": payment, "student": payment.student, "page_title": payment.receipt_no},
    )


@staff_required
def student_ledger_view(request, student_pk):
    """Full invoice + payment history for one student."""
    student = get_object_or_404(Student.objects.select_related("course", "department"), pk=student_pk)
    entries = student_ledger(student)
    billed = round(sum(entry["debit"] for entry in entries), 2)
    received = round(sum(entry["credit"] for entry in entries), 2)
    headers = ["Date", "Type", "Reference", "Description", "Debit", "Credit", "Balance", "Status"]
    rows = [
        [item["date"], item["type"], item["reference"], item["description"],
         item["debit"], item["credit"], item["balance"], item["status"]]
        for item in entries
    ]
    if request.GET.get("format"):
        from core.exports import ExportError, export_data

        try:
            response = export_data(
                request,
                f"ledger_{student.student_id}",
                headers,
                rows,
                title=f"Fee Ledger - {student.full_name}",
                meta=[("Student ID", student.student_id)],
            )
        except ExportError as exc:
            messages.error(request, str(exc))
            return redirect("fees:student_ledger", student_pk=student.pk)
        return response

    return render(
        request,
        "fees/student_ledger.html",
        {
            "student": student,
            "entries": entries,
            "headers": headers,
            "billed": billed,
            "received": received,
            "balance": round(billed - received, 2),
            "pending_invoices": FeeRecord.objects.filter(student=student)
            .exclude(status__in=[FeeRecord.Status.PAID, FeeRecord.Status.CANCELLED])
            .select_related("fee_type")
            .order_by("due_date"),
            "page_title": f"Ledger - {student.full_name}",
            "active_menu": "fees",
            "breadcrumb_parent": "Fees",
        },
    )


@staff_required
def overdue_report(request):
    """Overdue invoices with ageing buckets."""
    today = timezone.localdate()
    records = (
        FeeRecord.objects.filter(
            status__in=[FeeRecord.Status.PENDING, FeeRecord.Status.PARTIAL],
            due_date__lt=today,
        )
        .select_related("student", "fee_type")
        .order_by("due_date")
    )
    rows = []
    buckets = {"1-30": 0, "31-60": 0, "61-90": 0, "90+": 0}
    total = 0.0
    for record in records:
        days = record.days_overdue
        if days <= 30:
            buckets["1-30"] += record.remaining_amount
        elif days <= 60:
            buckets["31-60"] += record.remaining_amount
        elif days <= 90:
            buckets["61-90"] += record.remaining_amount
        else:
            buckets["90+"] += record.remaining_amount
        total += record.remaining_amount
        rows.append(
            {
                "record": record,
                "student": record.student,
                "days": days,
                "remaining": record.remaining_amount,
            }
        )

    headers = ["Invoice", "Student", "Code", "Fee Type", "Due Date", "Days Overdue", "Remaining", "Status"]
    export_rows = [
        [row["record"].invoice_no, row["student"].full_name, row["student"].student_id,
         row["record"].fee_type.name, row["record"].due_date, row["days"], row["remaining"],
         row["record"].get_status_display()]
        for row in rows
    ]

    if request.GET.get("format"):
        from core.exports import ExportError, export_data

        try:
            response = export_data(
                request,
                "overdue_fees",
                headers,
                export_rows,
                title="Overdue Fee Report",
                meta=[("Generated", timezone.localtime().strftime("%Y-%m-%d %H:%M"))],
            )
        except ExportError as exc:
            messages.error(request, str(exc))
            return redirect("fees:overdue_report")
        log_action(
            request,
            AuditLog.Action.EXPORT,
            module="fees",
            description=f"Overdue report exported ({len(export_rows)} rows)",
        )
        return response

    page = paginate(request, rows, per_page=20)
    return render(
        request,
        "fees/overdue_report.html",
        {
            "rows": page.object_list,
            "page_obj": page,
            "paginator": page.paginator,
            "is_paginated": page.has_other_pages(),
            "page_number": page.number,
            "total_rows": len(rows),
            "total_amount": round(total, 2),
            "buckets": {key: round(value, 2) for key, value in buckets.items()},
            "chart_labels": list(buckets.keys()),
            "chart_values": [round(value, 2) for value in buckets.values()],
            "page_title": "Overdue Fees",
            "active_menu": "reports",
        },
    )


@staff_required
def fee_collection_report(request):
    """Collection performance: totals, methods and top defaulters."""
    start = parse_date(request.GET.get("date_from"))
    end = parse_date(request.GET.get("date_to"))
    if not start:
        start = timezone.localdate().replace(day=1)
    if not end:
        end = timezone.localdate()

    summary = fee_summary()
    methods = collection_by_method(start, end)

    defaulters = (
        FeeRecord.objects.exclude(status__in=[FeeRecord.Status.PAID, FeeRecord.Status.CANCELLED])
        .values("student__id", "student__student_id", "student__first_name", "student__last_name")
        .annotate(due=Sum("amount") - Sum("discount"), invoices=Count("id"))
        .order_by("-due")
    )
    top_rows = []
    for row in list(defaulters)[:20]:
        outstanding = sum(
            record.remaining_amount
            for record in FeeRecord.objects.filter(
                student__student_id=row["student__student_id"]
            ).exclude(status__in=[FeeRecord.Status.PAID, FeeRecord.Status.CANCELLED])
        )
        top_rows.append(
            {
                "pk": row["student__id"],
                "student_id": row["student__student_id"],
                "name": f"{row['student__first_name']} {row['student__last_name']}".strip(),
                "invoices": row["invoices"],
                "outstanding": round(outstanding, 2),
            }
        )

    headers = ["Student ID", "Name", "Invoices", "Outstanding"]
    export_rows = [[row["student_id"], row["name"], row["invoices"], row["outstanding"]] for row in top_rows]

    if request.GET.get("format"):
        from core.exports import ExportError, export_data

        try:
            response = export_data(
                request,
                "fee_collection",
                headers,
                export_rows,
                title="Fee Collection Report",
                meta=[("Period", f"{start} to {end}")],
            )
        except ExportError as exc:
            messages.error(request, str(exc))
            return redirect("fees:fee_report")
        return response

    return render(
        request,
        "fees/fee_report.html",
        {
            "summary": summary,
            "methods": methods,
            "top_rows": top_rows,
            "period_start": start,
            "period_end": end,
            "chart_labels": [item["method_display"] for item in methods],
            "chart_values": [item["total"] for item in methods],
            "page_title": "Fee Collection Report",
            "active_menu": "reports",
        },
    )


__all__ = [
    "FeeTypeListView",
    "FeeTypeCreateView",
    "FeeTypeUpdateView",
    "FeeTypeDeleteView",
    "FeeStructureListView",
    "FeeStructureCreateView",
    "FeeStructureUpdateView",
    "FeeStructureDeleteView",
    "bulk_invoice_generate",
    "bulk_invoice_generate_structure",
    "FeeRecordListView",
    "FeeRecordCreateView",
    "FeeRecordUpdateView",
    "FeeRecordDetailView",
    "FeeRecordDeleteView",
    "fee_record_cancel",
    "fee_record_invoice",
    "PaymentListView",
    "PaymentCreateView",
    "collect_payment",
    "PaymentDetailView",
    "payment_cancel",
    "payment_receipt",
    "student_ledger_view",
    "overdue_report",
    "fee_collection_report",
]