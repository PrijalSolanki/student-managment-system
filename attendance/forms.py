from __future__ import annotations

from django import forms

from academics.models import Course, Department, Semester, Subject
from attendance.models import Attendance
from core.forms import BootstrapFormMixin
from core.validators import validate_phone
from students.models import Student
from teachers.models import Teacher


class AttendanceMarkForm(BootstrapFormMixin, forms.Form):
    """Header of the 'mark attendance' screen."""

    date = forms.DateField(widget=forms.DateInput(attrs={"type": "date"}))
    course = forms.ModelChoiceField(
        queryset=Course.objects.filter(is_active=True), empty_label="Select course"
    )
    semester = forms.ModelChoiceField(
        queryset=Semester.objects.all(), empty_label="Select semester"
    )
    subject = forms.ModelChoiceField(
        queryset=Subject.objects.filter(is_active=True), empty_label="Select subject"
    )
    department = forms.ModelChoiceField(
        queryset=Department.objects.filter(is_active=True),
        empty_label="All departments",
        required=False,
    )
    teacher = forms.ModelChoiceField(
        queryset=Teacher.objects.filter(status=Teacher.Status.ACTIVE),
        empty_label="Auto (subject teacher)",
        required=False,
    )
    remarks = forms.CharField(required=False, max_length=200)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from django.utils import timezone

        self.fields["date"].initial = timezone.localdate()

    def clean(self):
        cleaned = super().clean()
        date = cleaned.get("date")
        if date:
            from django.utils import timezone

            if date > timezone.localdate():
                self.add_error("date", "Attendance cannot be marked for a future date.")
        course = cleaned.get("course")
        semester = cleaned.get("semester")
        subject = cleaned.get("subject")
        if course and subject and subject.course_id != course.pk:
            self.add_error("subject", "The chosen subject does not belong to this course.")
        if course and semester and semester.number > course.total_semesters:
            self.add_error("semester", "Invalid semester for the selected course.")
        return cleaned


class AttendanceFilterForm(forms.Form):
    q = forms.CharField(required=False, label="Search student")
    date = forms.DateField(required=False, widget=forms.DateInput(attrs={"type": "date"}))
    date_from = forms.DateField(required=False, widget=forms.DateInput(attrs={"type": "date"}))
    date_to = forms.DateField(required=False, widget=forms.DateInput(attrs={"type": "date"}))
    subject = forms.ModelChoiceField(
        required=False, queryset=Subject.objects.all(), empty_label="All subjects"
    )
    teacher = forms.ModelChoiceField(
        required=False, queryset=Teacher.objects.all(), empty_label="All teachers"
    )
    course = forms.ModelChoiceField(
        required=False, queryset=Course.objects.all(), empty_label="All courses"
    )
    semester = forms.ModelChoiceField(
        required=False, queryset=Semester.objects.all(), empty_label="All semesters"
    )
    department = forms.ModelChoiceField(
        required=False, queryset=Department.objects.all(), empty_label="All departments"
    )
    status = forms.ChoiceField(
        required=False, choices=[("", "Any status")] + list(Attendance.Status.choices)
    )


class StudentAttendanceFilterForm(forms.Form):
    student = forms.ModelChoiceField(
        required=False, queryset=Student.objects.all(), empty_label="All students"
    )
    date_from = forms.DateField(required=False, widget=forms.DateInput(attrs={"type": "date"}))
    date_to = forms.DateField(required=False, widget=forms.DateInput(attrs={"type": "date"}))
    subject = forms.ModelChoiceField(
        required=False, queryset=Subject.objects.all(), empty_label="All subjects"
    )
