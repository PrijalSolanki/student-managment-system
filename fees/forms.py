from django import forms

from academics.models import Course, Department, Semester
from core.forms import BootstrapFormMixin
from fees.models import FeeRecord, FeeStructure, FeeType, Payment
from students.models import Student


class FeeTypeForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = FeeType
        fields = ["name", "code", "description", "is_mandatory", "is_active"]
        widgets = {
            "name": forms.TextInput(attrs={"placeholder": "e.g. Tuition Fee"}),
            "code": forms.TextInput(attrs={"placeholder": "Leave blank to auto-generate"}),
            "description": forms.Textarea(attrs={"rows": 2}),
        }


class FeeStructureForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = FeeStructure
        fields = [
            "fee_type",
            "amount",
            "department",
            "course",
            "semester",
            "frequency",
            "academic_year",
            "is_active",
            "description",
        ]
        widgets = {
            "amount": forms.NumberInput(attrs={"step": "0.01", "min": "0"}),
            "frequency": forms.Select(choices=[("SEMESTER", "Per Semester"), ("MONTHLY", "Monthly"), ("YEARLY", "Yearly"), ("ONE_TIME", "One Time")]),
            "academic_year": forms.TextInput(attrs={"placeholder": "e.g. 2025-2026"}),
            "description": forms.TextInput(attrs={"placeholder": "Optional note"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["fee_type"].queryset = FeeType.objects.filter(is_active=True).order_by("name")
        self.fields["fee_type"].empty_label = "Select fee type"
        self.fields["department"].queryset = Department.objects.order_by("name")
        self.fields["department"].empty_label = "All departments"
        self.fields["course"].queryset = Course.objects.order_by("name")
        self.fields["course"].empty_label = "All courses"
        self.fields["semester"].queryset = Semester.objects.order_by("number")
        self.fields["semester"].empty_label = "All semesters"

    def clean(self):
        cleaned = super().clean()
        department = cleaned.get("department")
        course = cleaned.get("course")
        if course and department and course.department_id != department.id:
            self.add_error("course", "Selected course does not belong to the chosen department.")
        if not department and not course:
            self.add_error("department", "Choose a department or a course to define the scope.")
        return cleaned


class FeeRecordForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = FeeRecord
        fields = ["student", "fee_type", "amount", "discount", "due_date", "academic_year", "notes"]
        widgets = {
            "amount": forms.NumberInput(attrs={"step": "0.01", "min": "0"}),
            "discount": forms.NumberInput(attrs={"step": "0.01", "min": "0", "value": "0"}),
            "due_date": forms.DateInput(attrs={"type": "date"}),
            "academic_year": forms.TextInput(attrs={"placeholder": "e.g. 2025-2026"}),
            "notes": forms.TextInput(attrs={"placeholder": "Optional note"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["student"].queryset = (
            Student.objects.filter(status__in=[Student.Status.ACTIVE, Student.Status.GRADUATED])
            .select_related("course", "semester")
            .order_by("student_id")
        )
        self.fields["student"].empty_label = "Select student"
        self.fields["fee_type"].queryset = FeeType.objects.filter(is_active=True).order_by("name")
        self.fields["fee_type"].empty_label = "Select fee type"

    def clean(self):
        cleaned = super().clean()
        amount = cleaned.get("amount")
        discount = cleaned.get("discount") or 0
        if amount is not None and discount > amount:
            self.add_error("discount", "Discount cannot exceed the fee amount.")
        return cleaned


class BulkInvoiceForm(BootstrapFormMixin, forms.Form):
    """Generate invoices for many students from a fee structure."""

    fee_structure = forms.ModelChoiceField(queryset=FeeStructure.objects.none())
    department = forms.ModelChoiceField(required=False, queryset=Department.objects.all())
    course = forms.ModelChoiceField(required=False, queryset=Course.objects.all())
    semester = forms.ModelChoiceField(required=False, queryset=Semester.objects.all())
    amount = forms.DecimalField(required=False, max_digits=12, decimal_places=2)
    discount = forms.DecimalField(required=False, initial=0, max_digits=12, decimal_places=2)
    due_date = forms.DateField(widget=forms.DateInput(attrs={"type": "date"}))
    academic_year = forms.CharField(required=False, max_length=20)
    only_active = forms.BooleanField(required=False, initial=True)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["fee_structure"].queryset = FeeStructure.objects.select_related("fee_type").filter(is_active=True)
        self.fields["fee_structure"].empty_label = "Select fee structure"
        self.fields["department"].queryset = Department.objects.order_by("name")
        self.fields["department"].empty_label = "All departments"
        self.fields["course"].queryset = Course.objects.order_by("name")
        self.fields["course"].empty_label = "All courses"
        self.fields["semester"].queryset = Semester.objects.order_by("number")
        self.fields["semester"].empty_label = "All semesters"
        self.fields["amount"].widget.attrs["placeholder"] = "Defaults to the structure amount"

    def resolve_students(self):
        department = self.cleaned_data.get("department")
        course = self.cleaned_data.get("course")
        semester = self.cleaned_data.get("semester")
        structure = self.cleaned_data["fee_structure"]
        queryset = Student.objects.all()
        if self.cleaned_data.get("only_active"):
            queryset = queryset.filter(status=Student.Status.ACTIVE)
        if course:
            queryset = queryset.filter(course=course)
        elif department:
            queryset = queryset.filter(department=department)
        if semester:
            queryset = queryset.filter(semester=semester)
        elif structure.semester_id:
            queryset = queryset.filter(semester=structure.semester)
        return queryset.select_related("course", "semester", "department").order_by("student_id")


class PaymentForm(BootstrapFormMixin, forms.ModelForm):
    fee_record = forms.ModelChoiceField(
        queryset=FeeRecord.objects.none(), required=False, label="Apply to invoice"
    )

    class Meta:
        model = Payment
        fields = ["student", "fee_record", "amount", "payment_date", "method", "reference_no", "remarks"]
        widgets = {
            "amount": forms.NumberInput(attrs={"step": "0.01", "min": "0.01"}),
            "payment_date": forms.DateInput(attrs={"type": "date"}),
            "reference_no": forms.TextInput(attrs={"placeholder": "Transaction / cheque number"}),
            "remarks": forms.TextInput(attrs={"placeholder": "Optional note"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["student"].queryset = (
            Student.objects.select_related("course", "department").order_by("student_id")
        )
        self.fields["student"].empty_label = "Select student"
        self.fields["fee_record"].empty_label = "Settle oldest invoices first"

    def clean(self):
        cleaned = super().clean()
        student = cleaned.get("student")
        fee_record = cleaned.get("fee_record")
        amount = cleaned.get("amount")
        if fee_record and student and fee_record.student_id != student.id:
            self.add_error("fee_record", "Selected invoice belongs to another student.")
        if fee_record and amount and amount > fee_record.remaining_amount:
            self.add_error(
                "amount",
                f"Amount exceeds the outstanding balance ({fee_record.remaining_amount}) on {fee_record.invoice_no}.",
            )
        return cleaned


class PaymentFilterForm(BootstrapFormMixin, forms.Form):
    q = forms.CharField(required=False, widget=forms.TextInput(attrs={"placeholder": "Receipt no or student"}))
    method = forms.ChoiceField(required=False, choices=[("", "All methods")] + list(Payment.Method.choices))
    student = forms.ModelChoiceField(required=False, queryset=Student.objects.all())
    date_from = forms.DateField(required=False, widget=forms.DateInput(attrs={"type": "date"}))
    date_to = forms.DateField(required=False, widget=forms.DateInput(attrs={"type": "date"}))
    only_cancelled = forms.BooleanField(required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["student"].queryset = Student.objects.order_by("student_id")
        self.fields["student"].empty_label = "All students"


class FeeRecordFilterForm(BootstrapFormMixin, forms.Form):
    q = forms.CharField(required=False, widget=forms.TextInput(attrs={"placeholder": "Invoice no or student"}))
    status = forms.ChoiceField(required=False, choices=[("", "All statuses")] + list(FeeRecord.Status.choices))
    fee_type = forms.ModelChoiceField(required=False, queryset=FeeType.objects.all())
    student = forms.ModelChoiceField(required=False, queryset=Student.objects.all())
    department = forms.ModelChoiceField(required=False, queryset=Department.objects.all())
    course = forms.ModelChoiceField(required=False, queryset=Course.objects.all())
    date_from = forms.DateField(required=False, widget=forms.DateInput(attrs={"type": "date"}))
    date_to = forms.DateField(required=False, widget=forms.DateInput(attrs={"type": "date"}))
    overdue_only = forms.BooleanField(required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["fee_type"].empty_label = "All fee types"
        self.fields["student"].queryset = Student.objects.order_by("student_id")
        self.fields["student"].empty_label = "All students"
        self.fields["department"].queryset = Department.objects.order_by("name")
        self.fields["department"].empty_label = "All departments"
        self.fields["course"].queryset = Course.objects.order_by("name")
        self.fields["course"].empty_label = "All courses"


__all__ = [
    "FeeTypeForm",
    "FeeStructureForm",
    "FeeRecordForm",
    "BulkInvoiceForm",
    "PaymentForm",
    "PaymentFilterForm",
    "FeeRecordFilterForm",
]