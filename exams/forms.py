from django import forms

from academics.models import Course, Department, Semester, Subject
from core.forms import BootstrapFormMixin
from exams.models import Exam, ExamSubject, MarkEntry
from students.models import Student
from teachers.models import Teacher


class ExamForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Exam
        fields = [
            "name",
            "code",
            "exam_type",
            "course",
            "semester",
            "academic_year",
            "start_date",
            "end_date",
            "passing_percentage",
            "is_published",
            "allow_marks_entry",
            "description",
        ]
        widgets = {
            "name": forms.TextInput(attrs={"placeholder": "e.g. Mid Term Examination 2026"}),
            "code": forms.TextInput(attrs={"placeholder": "e.g. MID-2026-S1"}),
            "academic_year": forms.TextInput(attrs={"placeholder": "e.g. 2025-2026"}),
            "start_date": forms.DateInput(attrs={"type": "date"}),
            "end_date": forms.DateInput(attrs={"type": "date"}),
            "passing_percentage": forms.NumberInput(attrs={"step": "0.01", "min": "0", "max": "100"}),
            "description": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["course"].queryset = Course.objects.order_by("department__name", "name")
        self.fields["semester"].queryset = Semester.objects.select_related("department").order_by(
            "department__name", "number"
        )
        self.fields["is_published"].help_text = "Visible to students on their profile."
        self.fields["allow_marks_entry"].help_text = "Turn off to lock mark entry for this exam."

    def clean(self):
        cleaned = super().clean()
        start = cleaned.get("start_date")
        end = cleaned.get("end_date")
        if start and end and end < start:
            self.add_error("end_date", "End date cannot be before the start date.")
        course = cleaned.get("course")
        semester = cleaned.get("semester")
        if course and semester and semester.department_id != course.department_id:
            self.add_error("semester", "Selected semester does not belong to the course department.")
        return cleaned


class ExamSubjectForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = ExamSubject
        fields = ["subject", "max_marks", "exam_date", "exam_time", "venue", "instructions"]
        widgets = {
            "max_marks": forms.NumberInput(attrs={"step": "0.25", "min": "0"}),
            "exam_date": forms.DateInput(attrs={"type": "date"}),
            "exam_time": forms.TextInput(attrs={"placeholder": "e.g. 10:00 AM - 12:00 PM"}),
            "instructions": forms.TextInput(attrs={"placeholder": "Optional instructions"}),
        }

    def __init__(self, *args, **kwargs):
        self.exam = kwargs.pop("exam", None)
        super().__init__(*args, **kwargs)
        queryset = Subject.objects.select_related("semester").order_by("code")
        if self.exam:
            used = self.exam.exam_subjects.values_list("subject_id", flat=True)
            if self.instance.pk:
                used = used.exclude(pk=self.instance.pk)
            queryset = queryset.exclude(pk__in=list(used))
        self.fields["subject"].queryset = queryset
        self.fields["subject"].empty_label = "Select subject"


class MarkEntryForm(BootstrapFormMixin, forms.ModelForm):
    marks_obtained = forms.DecimalField(
        max_digits=7,
        decimal_places=2,
        required=False,
        widget=forms.NumberInput(attrs={"step": "0.01", "min": "0", "class": "form-control mark-input"}),
    )

    class Meta:
        model = MarkEntry
        fields = ["marks_obtained", "is_absent", "remarks"]
        widgets = {
            "remarks": forms.TextInput(attrs={"placeholder": "Optional remark"}),
        }

    def __init__(self, *args, **kwargs):
        self.max_marks = kwargs.pop("max_marks", None)
        super().__init__(*args, **kwargs)
        self.fields["is_absent"].widget.attrs.update({"class": "form-check-input"})

    def clean(self):
        cleaned = super().clean()
        marks = cleaned.get("marks_obtained")
        is_absent = cleaned.get("is_absent")
        if is_absent:
            cleaned["marks_obtained"] = None
            return cleaned
        if self.max_marks is not None and marks is not None and marks > self.max_marks:
            self.add_error("marks_obtained", f"Marks cannot be greater than {self.max_marks}.")
        return cleaned


class ExamFilterForm(BootstrapFormMixin, forms.Form):
    q = forms.CharField(required=False, widget=forms.TextInput(attrs={"placeholder": "Name or code"}))
    course = forms.ModelChoiceField(required=False, queryset=Course.objects.all())
    semester = forms.ModelChoiceField(required=False, queryset=Semester.objects.all())
    exam_type = forms.ChoiceField(required=False, choices=[("", "All types")] + list(Exam.ExamType.choices))
    status = forms.ChoiceField(
        required=False,
        choices=[
            ("", "All"),
            ("upcoming", "Upcoming"),
            ("running", "Running"),
            ("completed", "Completed"),
            ("published", "Published"),
            ("unpublished", "Unpublished"),
        ],
    )
    date_from = forms.DateField(required=False, widget=forms.DateInput(attrs={"type": "date"}))
    date_to = forms.DateField(required=False, widget=forms.DateInput(attrs={"type": "date"}))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["course"].queryset = Course.objects.order_by("name")
        self.fields["semester"].queryset = Semester.objects.order_by("number")
        self.fields["course"].empty_label = "All courses"
        self.fields["semester"].empty_label = "All semesters"


class ResultFilterForm(BootstrapFormMixin, forms.Form):
    q = forms.CharField(
        required=False, widget=forms.TextInput(attrs={"placeholder": "Student name or code"})
    )
    exam = forms.ModelChoiceField(required=False, queryset=Exam.objects.all())
    grade = forms.ChoiceField(
        required=False,
        choices=[("", "All grades")] + [("A+", "A+"), ("A", "A"), ("B+", "B+"), ("B", "B"), ("C", "C"), ("D", "D"), ("F", "F")],
    )
    is_pass = forms.ChoiceField(
        required=False, choices=[("", "All"), ("yes", "Passed"), ("no", "Failed")]
    )
    department = forms.ModelChoiceField(required=False, queryset=Department.objects.all())
    course = forms.ModelChoiceField(required=False, queryset=Course.objects.all())

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["department"].queryset = Department.objects.order_by("name")
        self.fields["department"].empty_label = "All departments"
        self.fields["course"].queryset = Course.objects.order_by("name")
        self.fields["course"].empty_label = "All courses"
        self.fields["exam"].queryset = Exam.objects.select_related("course").order_by("-start_date")
        self.fields["exam"].empty_label = "All exams"


class MarkEntryFilterForm(BootstrapFormMixin, forms.Form):
    exam = forms.ModelChoiceField(queryset=Exam.objects.all(), label="Exam")
    exam_subject = forms.ModelChoiceField(queryset=ExamSubject.objects.all(), required=False)
    q = forms.CharField(required=False, widget=forms.TextInput(attrs={"placeholder": "Student name or code"}))
    teacher = forms.ModelChoiceField(queryset=Teacher.objects.all(), required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["exam"].empty_label = "Select exam"
        self.fields["exam_subject"].empty_label = "All subjects"
        self.fields["teacher"].empty_label = "All teachers"
        self.fields["exam"].queryset = Exam.objects.select_related("course", "semester").order_by("-start_date")

    def clean(self):
        cleaned = super().clean()
        exam = cleaned.get("exam")
        exam_subject = cleaned.get("exam_subject")
        if exam_subject and exam and exam_subject.exam_id != exam.pk:
            self.add_error("exam_subject", "Selected subject does not belong to the selected exam.")
        return cleaned


class StudentExamFilterForm(BootstrapFormMixin, forms.Form):
    student = forms.ModelChoiceField(queryset=Student.objects.all(), label="Student")
    exam = forms.ModelChoiceField(queryset=Exam.objects.all(), required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["student"].queryset = Student.objects.select_related("course", "department").order_by("student_id")
        self.fields["student"].empty_label = "Select student"
        self.fields["exam"].empty_label = "All exams"


__all__ = [
    "ExamForm",
    "ExamSubjectForm",
    "MarkEntryForm",
    "ExamFilterForm",
    "ResultFilterForm",
    "MarkEntryFilterForm",
    "StudentExamFilterForm",
]