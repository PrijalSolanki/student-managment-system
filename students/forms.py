from __future__ import annotations

from django import forms
from django.utils import timezone

from academics.models import Batch, Course, Department, Semester
from core.forms import BootstrapFormMixin
from core.validators import validate_image, validate_phone, validate_pincode
from students.models import Student, StudentDocument, StudentPromotion


class StudentForm(BootstrapFormMixin, forms.ModelForm):
    confirm_email = forms.EmailField(
        required=False,
        label="Confirm email",
        help_text="Optional - helps catch typos on the email address.",
    )

    class Meta:
        model = Student
        fields = [
            "student_id",
            "first_name",
            "last_name",
            "email",
            "confirm_email",
            "phone",
            "date_of_birth",
            "gender",
            "blood_group",
            "nationality",
            "religion",
            "category",
            "address",
            "city",
            "state",
            "pincode",
            "photo",
            "admission_date",
            "department",
            "course",
            "semester",
            "batch",
            "status",
            "guardian_name",
            "guardian_phone",
            "guardian_relation",
            "emergency_contact",
            "previous_qualification",
            "previous_percentage",
            "scholarship",
            "notes",
        ]
        widgets = {
            "date_of_birth": forms.DateInput(attrs={"type": "date"}),
            "admission_date": forms.DateInput(attrs={"type": "date"}),
            "address": forms.Textarea(attrs={"rows": 3}),
            "notes": forms.Textarea(attrs={"rows": 2}),
            "photo": forms.ClearableFileInput(),
            "student_id": forms.TextInput(
                attrs={"placeholder": "Leave blank to auto-generate (e.g. STU00001)"}
            ),
            "previous_percentage": forms.NumberInput(attrs={"step": "0.01", "min": 0, "max": 100}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["department"].queryset = Department.objects.filter(is_active=True)
        self.fields["course"].queryset = Course.objects.filter(is_active=True)
        self.fields["semester"].queryset = Semester.objects.all()
        self.fields["batch"].queryset = Batch.objects.filter(is_active=True)
        if self.instance and self.instance.pk:
            self.fields["confirm_email"].initial = self.instance.email
        else:
            self.fields["admission_date"].initial = timezone.localdate()

    def clean_email(self):
        email = (self.cleaned_data.get("email") or "").strip().lower()
        if not email:
            raise forms.ValidationError("Email address is required.")
        qs = Student.objects.filter(email__iexact=email)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError("A student with this email address already exists.")
        return email

    def clean_confirm_email(self):
        confirm = (self.cleaned_data.get("confirm_email") or "").strip().lower()
        email = (self.data.get("email") or "").strip().lower()
        if confirm and email and confirm != email:
            raise forms.ValidationError("The two email addresses do not match.")
        return confirm

    def clean_student_id(self):
        student_id = (self.cleaned_data.get("student_id") or "").strip().upper()
        if student_id:
            qs = Student.objects.filter(student_id__iexact=student_id)
            if self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise forms.ValidationError("This enrolment number is already in use.")
        return student_id

    def clean_phone(self):
        phone = self.cleaned_data.get("phone")
        validate_phone(phone)
        return phone

    def clean_guardian_phone(self):
        phone = self.cleaned_data.get("guardian_phone")
        validate_phone(phone)
        return phone

    def clean_emergency_contact(self):
        phone = self.cleaned_data.get("emergency_contact")
        validate_phone(phone)
        return phone

    def clean_pincode(self):
        pincode = self.cleaned_data.get("pincode")
        validate_pincode(pincode)
        return pincode

    def clean_photo(self):
        photo = self.cleaned_data.get("photo")
        if photo:
            validate_image(photo)
        return photo

    def clean(self):
        cleaned = super().clean()
        dob = cleaned.get("date_of_birth")
        admission = cleaned.get("admission_date")
        if dob and admission and dob >= admission:
            self.add_error("date_of_birth", "Date of birth must be before the admission date.")
        elif dob and admission:
            age = admission.year - dob.year - (
                (admission.month, admission.day) < (dob.month, dob.day)
            )
            if age < 15:
                self.add_error("date_of_birth", "Student must be at least 15 years old.")
        course = cleaned.get("course")
        department = cleaned.get("department")
        semester = cleaned.get("semester")
        if course and department and course.department_id != department.pk:
            self.add_error("course", "This course does not belong to the selected department.")
        if course and semester and semester.number > course.total_semesters:
            self.add_error(
                "semester", f"This course only runs up to semester {course.total_semesters}."
            )
        return cleaned


class StudentFilterForm(forms.Form):
    """Renders the advanced filter panel."""

    q = forms.CharField(required=False, label="Keyword")
    department = forms.ModelChoiceField(
        required=False, queryset=Department.objects.all(), empty_label="All departments"
    )
    course = forms.ModelChoiceField(
        required=False, queryset=Course.objects.all(), empty_label="All courses"
    )
    semester = forms.ModelChoiceField(
        required=False, queryset=Semester.objects.all(), empty_label="All semesters"
    )
    batch = forms.ModelChoiceField(
        required=False, queryset=Batch.objects.all(), empty_label="All batches"
    )
    gender = forms.ChoiceField(required=False, choices=[("", "Any gender")] + list(Student.Gender.choices))
    status = forms.ChoiceField(required=False, choices=[("", "Any status")] + list(Student.Status.choices))
    date_from = forms.DateField(required=False, widget=forms.DateInput(attrs={"type": "date"}))
    date_to = forms.DateField(required=False, widget=forms.DateInput(attrs={"type": "date"}))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            field.widget.attrs["class"] = "form-select form-select-sm"


class StudentPromotionForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = StudentPromotion
        fields = [
            "promotion_type",
            "to_semester",
            "to_batch",
            "to_course",
            "to_department",
            "academic_year_from",
            "academic_year_to",
            "reason",
            "remarks",
        ]
        widgets = {
            "promotion_type": forms.Select(attrs={"class": "form-select"}),
            "remarks": forms.Textarea(attrs={"rows": 2}),
            "reason": forms.TextInput(attrs={"placeholder": "e.g. Passed all semester subjects"}),
        }

    def __init__(self, *args, student=None, **kwargs):
        self.student = student
        super().__init__(*args, **kwargs)
        self.fields["to_semester"].queryset = Semester.objects.all()
        self.fields["to_batch"].queryset = Batch.objects.filter(is_active=True)
        self.fields["to_course"].queryset = Course.objects.filter(is_active=True)
        self.fields["to_department"].queryset = Department.objects.filter(is_active=True)
        self.fields["academic_year_from"].widget.attrs["placeholder"] = "e.g. 2024-2025"
        self.fields["academic_year_to"].widget.attrs["placeholder"] = "e.g. 2025-2026"
        if student:
            self.fields["to_semester"].initial = _next_semester(student.semester)
            self.fields["to_batch"].initial = student.batch_id
            self.fields["to_course"].initial = student.course_id
            self.fields["to_department"].initial = student.department_id
            self.fields["promotion_type"].initial = "SEMESTER"

    def clean(self):
        cleaned = super().clean()
        student = self.student
        if not student:
            return cleaned
        to_semester = cleaned.get("to_semester")
        course = cleaned.get("to_course") or student.course
        if to_semester and course and to_semester.number > course.total_semesters:
            self.add_error(
                "to_semester", f"The target course only runs up to semester {course.total_semesters}."
            )
        to_course = cleaned.get("to_course")
        to_department = cleaned.get("to_department")
        if to_course and to_department and to_course.department_id != to_department.pk:
            self.add_error("to_course", "The chosen course does not belong to the department.")
        return cleaned


def _next_semester(current):
    if not current:
        return None
    return Semester.objects.filter(number=current.number + 1).first() or current


class StudentDocumentForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = StudentDocument
        fields = ["document_type", "title", "file", "description", "expiry_date"]
        widgets = {
            "file": forms.ClearableFileInput(),
            "expiry_date": forms.DateInput(attrs={"type": "date"}),
            "description": forms.TextInput(attrs={"placeholder": "Optional note"}),
        }

    def __init__(self, *args, student=None, **kwargs):
        self.student = student
        super().__init__(*args, **kwargs)
        self.fields["title"].widget.attrs["placeholder"] = "e.g. Aadhaar Card"

    def clean_title(self):
        title = (self.cleaned_data.get("title") or "").strip()
        if self.student:
            duplicate = StudentDocument.objects.filter(
                student=self.student, title__iexact=title
            )
            if self.instance.pk:
                duplicate = duplicate.exclude(pk=self.instance.pk)
            if duplicate.exists():
                raise forms.ValidationError("A document with this title already exists.")
        return title

    def clean_expiry_date(self):
        expiry = self.cleaned_data.get("expiry_date")
        if expiry and expiry < timezone.localdate():
            raise forms.ValidationError("The expiry date cannot be in the past.")
        return expiry


class StudentBulkForm(forms.Form):
    """Bulk actions available from the student list."""

    ACTION_CHOICES = [
        ("delete", "Delete selected students"),
        ("activate", "Mark as Active"),
        ("deactivate", "Mark as Inactive"),
        ("graduate", "Mark as Graduated"),
    ]
    student_ids = forms.CharField(required=False)
    action = forms.ChoiceField(choices=ACTION_CHOICES)
