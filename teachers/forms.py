from __future__ import annotations

from django import forms

from academics.models import Department, Subject
from core.forms import BootstrapFormMixin
from core.validators import validate_image, validate_phone, validate_pincode
from teachers.models import SubjectAssignment, Teacher


class TeacherForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Teacher
        fields = [
            "employee_id",
            "first_name",
            "last_name",
            "email",
            "phone",
            "gender",
            "date_of_birth",
            "blood_group",
            "qualification",
            "specialization",
            "designation",
            "department",
            "joining_date",
            "salary",
            "address",
            "city",
            "state",
            "pincode",
            "photo",
            "bio",
            "status",
        ]
        widgets = {
            "date_of_birth": forms.DateInput(attrs={"type": "date"}),
            "joining_date": forms.DateInput(attrs={"type": "date"}),
            "salary": forms.NumberInput(attrs={"step": "0.01", "min": 0}),
            "address": forms.Textarea(attrs={"rows": 3}),
            "bio": forms.Textarea(attrs={"rows": 3}),
            "photo": forms.ClearableFileInput(),
            "employee_id": forms.TextInput(
                attrs={"placeholder": "Leave blank to auto-generate (e.g. TCH0001)"}
            ),
        }

    def clean_email(self):
        email = (self.cleaned_data.get("email") or "").strip().lower()
        qs = Teacher.objects.filter(email__iexact=email)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError("A teacher with this email address already exists.")
        return email

    def clean_employee_id(self):
        employee_id = (self.cleaned_data.get("employee_id") or "").strip().upper()
        if employee_id:
            qs = Teacher.objects.filter(employee_id__iexact=employee_id)
            if self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise forms.ValidationError("This employee ID is already in use.")
        return employee_id

    def clean_phone(self):
        phone = self.cleaned_data.get("phone")
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

    def clean_salary(self):
        salary = self.cleaned_data.get("salary")
        if salary is not None and salary < 0:
            raise forms.ValidationError("Salary cannot be negative.")
        return salary

    def clean(self):
        cleaned = super().clean()
        dob = cleaned.get("date_of_birth")
        joining = cleaned.get("joining_date")
        if dob and joining and dob > joining:
            self.add_error("date_of_birth", "Date of birth must be before the joining date.")
        if dob:
            from django.utils import timezone

            age = timezone.localdate().year - dob.year
            if age < 21 or age > 70:
                self.add_error("date_of_birth", "Teacher age must be between 21 and 70 years.")
        return cleaned


class TeacherFilterForm(forms.Form):
    q = forms.CharField(required=False, label="Search")
    department = forms.ModelChoiceField(
        required=False, queryset=Department.objects.all(), empty_label="All departments"
    )
    status = forms.ChoiceField(
        required=False, choices=[("", "All statuses")] + list(Teacher.Status.choices)
    )
