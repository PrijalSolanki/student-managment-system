from __future__ import annotations

from django import forms

from academics.models import Batch, Course, Department, Semester, Subject
from core.forms import BootstrapFormMixin
from core.validators import validate_code, validate_phone
from teachers.models import SubjectAssignment


class DepartmentForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Department
        fields = [
            "name",
            "code",
            "hod",
            "email",
            "phone",
            "established_year",
            "description",
            "is_active",
        ]
        widgets = {"description": forms.Textarea(attrs={"rows": 4})}

    def clean_code(self):
        code = (self.cleaned_data.get("code") or "").strip()
        validate_code(code)
        qs = Department.objects.filter(code__iexact=code)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError("A department with this code already exists.")
        return code.upper()

    def clean_phone(self):
        phone = self.cleaned_data.get("phone")
        validate_phone(phone)
        return phone


class SemesterForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Semester
        fields = ["number", "name", "is_current"]
        widgets = {"number": forms.NumberInput(attrs={"min": 1, "max": 12})}

    def clean_number(self):
        number = self.cleaned_data.get("number")
        if number and not 1 <= number <= 12:
            raise forms.ValidationError("Semester must be between 1 and 12.")
        qs = Semester.objects.filter(number=number)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError("This semester already exists.")
        return number

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("is_current"):
            Semester.objects.exclude(pk=self.instance.pk).update(is_current=False)
        return cleaned


class BatchForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Batch
        fields = ["name", "start_year", "end_year", "department", "is_active"]
        widgets = {
            "start_year": forms.NumberInput(attrs={"min": 1990, "max": 2200}),
            "end_year": forms.NumberInput(attrs={"min": 1990, "max": 2200}),
        }

    def clean(self):
        cleaned = super().clean()
        start_year, end_year = cleaned.get("start_year"), cleaned.get("end_year")
        if start_year and end_year and end_year <= start_year:
            self.add_error("end_year", "End year must be greater than the start year.")
        name = (cleaned.get("name") or "").strip()
        if not name and start_year and end_year:
            name = f"{start_year}-{end_year}"
        qs = Batch.objects.filter(name__iexact=name)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if name and qs.exists():
            self.add_error("name", "A batch with this name already exists.")
        cleaned["name"] = name
        return cleaned


class CourseForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Course
        fields = [
            "name",
            "code",
            "department",
            "level",
            "duration_years",
            "total_semesters",
            "annual_fee",
            "eligibility",
            "description",
            "is_active",
        ]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 4}),
            "annual_fee": forms.NumberInput(attrs={"step": "0.01", "min": 0}),
            "duration_years": forms.NumberInput(attrs={"min": 1, "max": 10}),
            "total_semesters": forms.NumberInput(attrs={"min": 1, "max": 12}),
        }

    def clean_code(self):
        code = (self.cleaned_data.get("code") or "").strip()
        validate_code(code)
        qs = Course.objects.filter(code__iexact=code)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError("A course with this code already exists.")
        return code.upper()

    def clean(self):
        cleaned = super().clean()
        duration = cleaned.get("duration_years")
        semesters = cleaned.get("total_semesters")
        if duration and semesters and semesters > duration * 4:
            self.add_error(
                "total_semesters", "Semesters look too high for the course duration."
            )
        return cleaned


class SubjectForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Subject
        fields = [
            "name",
            "code",
            "course",
            "semester",
            "credits",
            "subject_type",
            "lecture_hours",
            "description",
            "is_active",
        ]
        widgets = {"description": forms.Textarea(attrs={"rows": 3})}

    def clean_code(self):
        code = (self.cleaned_data.get("code") or "").strip()
        validate_code(code)
        qs = Subject.objects.filter(code__iexact=code)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError("A subject with this code already exists.")
        return code.upper()

    def clean(self):
        cleaned = super().clean()
        course = cleaned.get("course")
        semester = cleaned.get("semester")
        if course and semester:
            if semester.number > course.total_semesters:
                self.add_error(
                    "semester",
                    f"This course only runs up to semester {course.total_semesters}.",
                )
            duplicate = Subject.objects.filter(
                course=course, semester=semester, name__iexact=cleaned.get("name", "")
            )
            if self.instance.pk:
                duplicate = duplicate.exclude(pk=self.instance.pk)
            if duplicate.exists():
                self.add_error(
                    "name", "This subject already exists for the selected course & semester."
                )
        return cleaned


class SubjectAssignmentForm(BootstrapFormMixin, forms.ModelForm):
    """Assign a teacher to a subject (many-to-many with extra metadata)."""

    class Meta:
        model = SubjectAssignment
        fields = ["subject", "teacher", "academic_year", "is_primary", "remarks"]
        widgets = {"remarks": forms.Textarea(attrs={"rows": 2})}

    def clean(self):
        cleaned = super().clean()
        subject, teacher = cleaned.get("subject"), cleaned.get("teacher")
        if subject and teacher:
            duplicate = SubjectAssignment.objects.filter(subject=subject, teacher=teacher)
            if self.instance.pk:
                duplicate = duplicate.exclude(pk=self.instance.pk)
            if duplicate.exists():
                self.add_error(
                    "teacher", "This teacher is already assigned to the selected subject."
                )
            if teacher.department_id and subject.course_id:
                if teacher.department_id != subject.course.department_id:
                    self.add_error(
                        "teacher",
                        "Teacher belongs to a different department than the subject.",
                    )
        return cleaned
