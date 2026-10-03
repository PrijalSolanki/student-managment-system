"""CRUD views for departments, semesters, batches, courses and subjects."""

from __future__ import annotations

from django.contrib import messages
from django.db.models import Count, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.views.decorators.http import require_GET, require_POST
from django.views.generic import CreateView, DeleteView, DetailView, UpdateView

from academics.forms import (
    BatchForm,
    CourseForm,
    DepartmentForm,
    SemesterForm,
    SubjectAssignmentForm,
    SubjectForm,
)
from academics.models import Batch, Course, Department, Semester, Subject
from core.mixins import FilterableListView, FormSuccessMixin, ProtectedDeleteMixin
from core.permissions import AdminRequiredMixin, StaffRequiredMixin
from core.utils import form_error_summary


# ---------------------------------------------------------------------------
# Departments
# ---------------------------------------------------------------------------
class DepartmentListView(StaffRequiredMixin, FilterableListView):
    model = Department
    template_name = "academics/department_list.html"
    list_title = "Departments"
    active_menu = "departments"
    search_fields = ["name", "code", "hod", "email"]
    filter_fields = ["is_active", "has_students"]
    filter_lookups = {"is_active": "is_active"}
    ordering_fields = {
        "name": "name",
        "-name": "-name",
        "code": "code",
        "students": "-students_total",
        "-students": "students_total",
        "newest": "-created_at",
    }
    default_ordering = "name"
    paginate_by = 10

    def get_queryset(self):
        queryset = (
            Department.objects.annotate(
                students_total=Count("students", distinct=True),
                teachers_total=Count("teachers", distinct=True),
                courses_total=Count("courses", distinct=True),
            )
            .all()
        )
        if self.request.GET.get("has_students") == "1":
            queryset = queryset.filter(students_total__gt=0)
        elif self.request.GET.get("has_students") == "0":
            queryset = queryset.filter(students_total=0)
        term = self.get_search_term()
        if term:
            queryset = queryset.filter(
                Q(name__icontains=term)
                | Q(code__icontains=term)
                | Q(hod__icontains=term)
                | Q(email__icontains=term)
            )
        status = self.request.GET.get("is_active")
        if status in {"true", "false"}:
            queryset = queryset.filter(is_active=(status == "true"))
        ordering = self.request.GET.get("ordering")
        if ordering in {"students", "-students"}:
            return queryset.order_by(ordering)
        if ordering in {"code", "-code"}:
            return queryset.order_by(ordering)
        if ordering == "newest":
            return queryset.order_by("-created_at")
        return queryset.order_by("name")

    def get_filter_choices(self):
        return {
            "is_active": [("true", "Active"), ("false", "Inactive")],
            "has_students": [("1", "With students"), ("0", "Without students")],
        }

    def get_table_columns(self):
        return [
            {"label": "Code", "attr": "code", "sort": "code"},
            {"label": "Department", "attr": "name", "sort": "name"},
            {"label": "HOD", "attr": "hod"},
            {"label": "Contact", "attr": "email"},
            {"label": "Courses", "attr": "courses_total", "align": "center"},
            {"label": "Teachers", "attr": "teachers_total", "align": "center"},
            {"label": "Students", "attr": "students_total", "align": "center", "sort": "students"},
            {"label": "Status", "attr": "is_active", "bool": True},
        ]

    def get_table_actions(self):
        return {
            "detail": "academics:department_detail",
            "edit": "academics:department_edit",
            "delete": "academics:department_delete",
        }

    def get_export_rows(self, queryset=None):
        queryset = queryset if queryset is not None else self.get_queryset()
        headers = ["Code", "Department", "HOD", "Email", "Phone", "Courses", "Teachers", "Students", "Status", "Created"]
        rows = [
            [
                obj.code,
                obj.name,
                obj.hod,
                obj.email,
                obj.phone,
                obj.courses_total,
                obj.teachers_total,
                obj.students_total,
                "Active" if obj.is_active else "Inactive",
                obj.created_at.strftime("%Y-%m-%d"),
            ]
            for obj in queryset
        ]
        return headers, rows


class DepartmentDetailView(StaffRequiredMixin, DetailView):
    model = Department
    template_name = "academics/department_detail.html"
    context_object_name = "department"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        department = self.object
        context.update(
            {
                "page_title": department.name,
                "breadcrumb_parent": "Departments",
                "active_menu": "departments",
                "courses": department.courses.all()[:20],
                "teachers": department.teachers.all()[:20],
                "students": department.students.select_related("course")[:20],
                "student_count": department.students.count(),
                "teacher_count": department.teachers.count(),
                "course_count": department.courses.count(),
                "subject_count": Subject.objects.filter(course__department=department).count(),
            }
        )
        return context


class DepartmentCreateView(AdminRequiredMixin, FormSuccessMixin, CreateView):
    model = Department
    form_class = DepartmentForm
    template_name = "academics/department_form.html"
    success_url = reverse_lazy("academics:department_list")
    created_message = "Department created successfully."

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(
            {
                "page_title": "Add Department",
                "breadcrumb_parent": "Departments",
                "active_menu": "departments",
                "form_title": "Add Department",
            }
        )
        return context


class DepartmentUpdateView(AdminRequiredMixin, FormSuccessMixin, UpdateView):
    model = Department
    form_class = DepartmentForm
    template_name = "academics/department_form.html"
    success_url = reverse_lazy("academics:department_list")
    success_message = "Department updated successfully."

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(
            {
                "page_title": f"Edit {self.object.name}",
                "breadcrumb_parent": "Departments",
                "active_menu": "departments",
                "form_title": f"Edit Department: {self.object.name}",
            }
        )
        return context


class DepartmentDeleteView(AdminRequiredMixin, ProtectedDeleteMixin, DeleteView):
    model = Department
    template_name = "academics/department_confirm_delete.html"
    success_url = reverse_lazy("academics:department_list")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(
            {
                "page_title": "Delete Department",
                "breadcrumb_parent": "Departments",
                "active_menu": "departments",
                "student_count": self.object.students.count(),
                "teacher_count": self.object.teachers.count(),
                "course_count": self.object.courses.count(),
            }
        )
        return context


# ---------------------------------------------------------------------------
# Semesters
# ---------------------------------------------------------------------------
def semester_list(request):
    semesters = Semester.objects.annotate(
        subject_count=Count("subjects"), student_count=Count("students")
    )
    return render(
        request,
        "academics/semester_list.html",
        {
            "semesters": semesters,
            "page_title": "Semesters",
            "breadcrumb_parent": "Semesters",
            "active_menu": "semesters",
        },
    )


class SemesterCreateView(AdminRequiredMixin, FormSuccessMixin, CreateView):
    model = Semester
    form_class = SemesterForm
    template_name = "academics/semester_form.html"
    success_url = reverse_lazy("academics:semester_list")
    created_message = "Semester created successfully."

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(
            {
                "page_title": "Add Semester",
                "breadcrumb_parent": "Semesters",
                "active_menu": "semesters",
                "form_title": "Add Semester",
            }
        )
        return context


class SemesterUpdateView(AdminRequiredMixin, FormSuccessMixin, UpdateView):
    model = Semester
    form_class = SemesterForm
    template_name = "academics/semester_form.html"
    success_url = reverse_lazy("academics:semester_list")
    success_message = "Semester updated successfully."

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(
            {
                "page_title": f"Edit {self.object}",
                "breadcrumb_parent": "Semesters",
                "active_menu": "semesters",
                "form_title": f"Edit {self.object}",
            }
        )
        return context


class SemesterDeleteView(AdminRequiredMixin, ProtectedDeleteMixin, DeleteView):
    model = Semester
    template_name = "academics/semester_confirm_delete.html"
    success_url = reverse_lazy("academics:semester_list")


# ---------------------------------------------------------------------------
# Batches
# ---------------------------------------------------------------------------
class BatchListView(StaffRequiredMixin, FilterableListView):
    model = Batch
    template_name = "academics/batch_list.html"
    list_title = "Batches"
    active_menu = "batches"
    search_fields = ["name", "department__name"]
    filter_fields = ["department", "is_active", "start_year"]
    ordering_fields = {
        "name": "name",
        "-start_year": "-start_year",
        "start_year": "start_year",
        "newest": "-created_at",
    }
    default_ordering = "-start_year"

    def get_queryset(self):
        queryset = (
            Batch.objects.select_related("department")
            .annotate(students_total=Count("students", distinct=True))
            .all()
        )
        return self.filter_queryset(queryset).order_by(self.get_ordering())

    def get_filter_choices(self):
        return {
            "department": [(d.pk, d.name) for d in Department.objects.all()],
            "is_active": [("true", "Active"), ("false", "Inactive")],
        }

    def filter_queryset(self, queryset):
        queryset = super().filter_queryset(queryset)
        status = self.request.GET.get("is_active")
        if status in {"true", "false"}:
            queryset = queryset.filter(is_active=(status == "true"))
        return queryset

    def get_table_columns(self):
        return [
            {"label": "Batch", "attr": "name"},
            {"label": "Start", "attr": "start_year", "align": "center", "sort": "start_year"},
            {"label": "End", "attr": "end_year", "align": "center"},
            {"label": "Department", "attr": "department.name"},
            {"label": "Students", "attr": "students_total", "align": "center"},
            {"label": "Status", "attr": "is_active", "bool": True},
        ]

    def get_table_actions(self):
        return {
            "edit": "academics:batch_edit",
            "delete": "academics:batch_delete",
        }

    def get_export_rows(self, queryset=None):
        queryset = queryset if queryset is not None else self.get_queryset()
        headers = ["Batch", "Start Year", "End Year", "Department", "Students", "Status"]
        rows = [
            [obj.name, obj.start_year, obj.end_year, obj.department.name if obj.department else "",
             obj.students_total, "Active" if obj.is_active else "Inactive"]
            for obj in queryset
        ]
        return headers, rows


class BatchCreateView(AdminRequiredMixin, FormSuccessMixin, CreateView):
    model = Batch
    form_class = BatchForm
    template_name = "academics/batch_form.html"
    success_url = reverse_lazy("academics:batch_list")
    created_message = "Batch created successfully."

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(
            {
                "page_title": "Add Batch",
                "breadcrumb_parent": "Batches",
                "active_menu": "batches",
                "form_title": "Add Batch",
            }
        )
        return context


class BatchUpdateView(AdminRequiredMixin, FormSuccessMixin, UpdateView):
    model = Batch
    form_class = BatchForm
    template_name = "academics/batch_form.html"
    success_url = reverse_lazy("academics:batch_list")
    success_message = "Batch updated successfully."

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(
            {
                "page_title": f"Edit {self.object.name}",
                "breadcrumb_parent": "Batches",
                "active_menu": "batches",
                "form_title": f"Edit Batch: {self.object.name}",
            }
        )
        return context


class BatchDeleteView(AdminRequiredMixin, ProtectedDeleteMixin, DeleteView):
    model = Batch
    template_name = "academics/batch_confirm_delete.html"
    success_url = reverse_lazy("academics:batch_list")


# ---------------------------------------------------------------------------
# Courses
# ---------------------------------------------------------------------------
class CourseListView(StaffRequiredMixin, FilterableListView):
    model = Course
    template_name = "academics/course_list.html"
    list_title = "Courses"
    active_menu = "courses"
    search_fields = ["name", "code", "department__name"]
    filter_fields = ["department", "level", "is_active", "duration_years"]
    ordering_fields = {
        "name": "name",
        "-name": "-name",
        "code": "code",
        "fee": "-annual_fee",
        "enrolled": "-students_total",
        "newest": "-created_at",
    }
    default_ordering = "name"

    def get_queryset(self):
        queryset = (
            Course.objects.select_related("department")
            .annotate(
                students_total=Count("students", distinct=True),
                subjects_total=Count("subjects", distinct=True),
            )
            .all()
        )
        return self.filter_queryset(queryset).order_by(self.get_ordering())

    def get_filter_choices(self):
        return {
            "department": [(d.pk, d.name) for d in Department.objects.all()],
            "level": Course._meta.get_field("level").choices,
            "is_active": [("true", "Active"), ("false", "Inactive")],
        }

    def filter_queryset(self, queryset):
        queryset = super().filter_queryset(queryset)
        status = self.request.GET.get("is_active")
        if status in {"true", "false"}:
            queryset = queryset.filter(is_active=(status == "true"))
        return queryset

    def get_table_columns(self):
        return [
            {"label": "Code", "attr": "code", "sort": "code"},
            {"label": "Course", "attr": "name", "sort": "name"},
            {"label": "Department", "attr": "department.name"},
            {"label": "Level", "attr": "get_level_display"},
            {"label": "Duration", "attr": "duration_years", "align": "center"},
            {"label": "Semesters", "attr": "total_semesters", "align": "center"},
            {"label": "Annual fee", "attr": "annual_fee", "money": True, "align": "end"},
            {"label": "Students", "attr": "students_total", "align": "center", "sort": "enrolled"},
            {"label": "Subjects", "attr": "subjects_total", "align": "center"},
            {"label": "Status", "attr": "is_active", "bool": True},
        ]

    def get_table_actions(self):
        return {
            "detail": "academics:course_detail",
            "edit": "academics:course_edit",
            "delete": "academics:course_delete",
        }

    def get_export_rows(self, queryset=None):
        queryset = queryset if queryset is not None else self.get_queryset()
        headers = ["Code", "Course", "Department", "Level", "Duration (yrs)", "Semesters", "Annual Fee", "Students", "Subjects", "Status"]
        rows = [
            [obj.code, obj.name, obj.department.name, obj.get_level_display(), obj.duration_years,
             obj.total_semesters, obj.annual_fee, obj.students_total, obj.subjects_total,
             "Active" if obj.is_active else "Inactive"]
            for obj in queryset
        ]
        return headers, rows


class CourseDetailView(StaffRequiredMixin, DetailView):
    model = Course
    template_name = "academics/course_detail.html"
    context_object_name = "course"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        course = self.object
        subjects = course.subjects.select_related("semester").order_by("semester__number", "name")
        context.update(
            {
                "page_title": course.name,
                "breadcrumb_parent": "Courses",
                "active_menu": "courses",
                "subjects": subjects,
                "students": course.students.select_related("department")[:20],
                "semesters": Semester.objects.all(),
                "student_count": course.students.count(),
                "subject_count": subjects.count(),
                "departments": Department.objects.all(),
            }
        )
        return context


class CourseCreateView(AdminRequiredMixin, FormSuccessMixin, CreateView):
    model = Course
    form_class = CourseForm
    template_name = "academics/course_form.html"
    success_url = reverse_lazy("academics:course_list")
    created_message = "Course created successfully."

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(
            {
                "page_title": "Add Course",
                "breadcrumb_parent": "Courses",
                "active_menu": "courses",
                "form_title": "Add Course",
            }
        )
        return context


class CourseUpdateView(AdminRequiredMixin, FormSuccessMixin, UpdateView):
    model = Course
    form_class = CourseForm
    template_name = "academics/course_form.html"
    success_url = reverse_lazy("academics:course_list")
    success_message = "Course updated successfully."

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(
            {
                "page_title": f"Edit {self.object.name}",
                "breadcrumb_parent": "Courses",
                "active_menu": "courses",
                "form_title": f"Edit Course: {self.object.name}",
            }
        )
        return context


class CourseDeleteView(AdminRequiredMixin, ProtectedDeleteMixin, DeleteView):
    model = Course
    template_name = "academics/course_confirm_delete.html"
    success_url = reverse_lazy("academics:course_list")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(
            {
                "page_title": "Delete Course",
                "breadcrumb_parent": "Courses",
                "active_menu": "courses",
                "student_count": self.object.students.count(),
                "subject_count": self.object.subjects.count(),
            }
        )
        return context


# ---------------------------------------------------------------------------
# Subjects
# ---------------------------------------------------------------------------
class SubjectListView(StaffRequiredMixin, FilterableListView):
    model = Subject
    template_name = "academics/subject_list.html"
    list_title = "Subjects"
    active_menu = "subjects"
    search_fields = ["name", "code", "course__name", "course__code"]
    filter_fields = ["course", "semester", "subject_type", "is_active"]
    filter_lookups = {"course": "course_id", "semester": "semester_id"}
    ordering_fields = {
        "name": "name",
        "-name": "-name",
        "code": "code",
        "credits": "-credits",
        "semester": "semester__number",
        "newest": "-created_at",
    }
    default_ordering = "code"

    def get_queryset(self):
        queryset = (
            Subject.objects.select_related("course", "course__department", "semester")
            .prefetch_related("assignments__teacher")
            .all()
        )
        return self.filter_queryset(queryset).order_by(self.get_ordering())

    def get_filter_choices(self):
        from teachers.models import Teacher

        return {
            "course": [(c.pk, c.name) for c in Course.objects.select_related("department").all()],
            "semester": [(s.pk, str(s)) for s in Semester.objects.all()],
            "subject_type": Subject._meta.get_field("subject_type").choices,
            "is_active": [("true", "Active"), ("false", "Inactive")],
            "teacher": [(t.pk, t.full_name) for t in Teacher.objects.all()[:100]],
        }

    def filter_queryset(self, queryset):
        queryset = super().filter_queryset(queryset)
        status = self.request.GET.get("is_active")
        if status in {"true", "false"}:
            queryset = queryset.filter(is_active=(status == "true"))
        teacher = self.request.GET.get("teacher")
        if teacher:
            queryset = queryset.filter(assignments__teacher_id=teacher).distinct()
        return queryset

    def get_table_columns(self):
        return [
            {"label": "Code", "attr": "code", "sort": "code"},
            {"label": "Subject", "attr": "name", "sort": "name"},
            {"label": "Course", "attr": "course.code"},
            {"label": "Semester", "attr": "semester.number", "align": "center", "sort": "semester"},
            {"label": "Credits", "attr": "credits", "align": "center", "sort": "credits"},
            {"label": "Type", "attr": "get_subject_type_display"},
            {"label": "Teachers", "attr": "teacher_names"},
            {"label": "Status", "attr": "is_active", "bool": True},
        ]

    def get_table_actions(self):
        return {
            "detail": "academics:subject_detail",
            "edit": "academics:subject_edit",
            "delete": "academics:subject_delete",
        }

    def get_export_rows(self, queryset=None):
        queryset = queryset if queryset is not None else self.get_queryset()
        headers = ["Code", "Subject", "Course", "Semester", "Credits", "Type", "Teachers", "Status"]
        rows = [
            [
                obj.code,
                obj.name,
                obj.course.name,
                str(obj.semester),
                obj.credits,
                obj.get_subject_type_display(),
                obj.teacher_names,
                "Active" if obj.is_active else "Inactive",
            ]
            for obj in queryset
        ]
        return headers, rows


class SubjectDetailView(StaffRequiredMixin, DetailView):
    model = Subject
    template_name = "academics/subject_detail.html"
    context_object_name = "subject"

    def get_context_data(self, **kwargs):
        from teachers.models import SubjectAssignment

        context = super().get_context_data(**kwargs)
        subject = self.object
        assignments = SubjectAssignment.objects.filter(subject=subject).select_related("teacher")
        context.update(
            {
                "page_title": subject.name,
                "breadcrumb_parent": "Subjects",
                "active_menu": "subjects",
                "assignments": assignments,
                "assignment_form": SubjectAssignmentForm(
                    initial={"subject": subject}, subject=subject
                ),
                "students": subject.course.students.select_related("department")[:20],
                "student_count": subject.course.students.count(),
                "teachers": assignments.values_list("teacher", flat=True),
            }
        )
        return context


class SubjectCreateView(AdminRequiredMixin, FormSuccessMixin, CreateView):
    model = Subject
    form_class = SubjectForm
    template_name = "academics/subject_form.html"
    success_url = reverse_lazy("academics:subject_list")
    created_message = "Subject created successfully."

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(
            {
                "page_title": "Add Subject",
                "breadcrumb_parent": "Subjects",
                "active_menu": "subjects",
                "form_title": "Add Subject",
            }
        )
        return context


class SubjectUpdateView(AdminRequiredMixin, FormSuccessMixin, UpdateView):
    model = Subject
    form_class = SubjectForm
    template_name = "academics/subject_form.html"
    success_url = reverse_lazy("academics:subject_list")
    success_message = "Subject updated successfully."

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(
            {
                "page_title": f"Edit {self.object.name}",
                "breadcrumb_parent": "Subjects",
                "active_menu": "subjects",
                "form_title": f"Edit Subject: {self.object.name}",
            }
        )
        return context


class SubjectDeleteView(AdminRequiredMixin, ProtectedDeleteMixin, DeleteView):
    model = Subject
    template_name = "academics/subject_confirm_delete.html"
    success_url = reverse_lazy("academics:subject_list")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(
            {
                "page_title": "Delete Subject",
                "breadcrumb_parent": "Subjects",
                "active_menu": "subjects",
                "assignment_count": self.object.assignments.count(),
            }
        )
        return context


@staff_required
@require_POST
def subject_assignment_create(request, pk):
    subject = get_object_or_404(Subject, pk=pk)
    form = SubjectAssignmentForm(request.POST, subject=subject)
    if form.is_valid():
        assignment = form.save(commit=False)
        assignment.subject = subject
        assignment.save()
        messages.success(request, f"{assignment.teacher.full_name} assigned to {subject.name}.")
    else:
        messages.error(
            request,
            "Could not assign the teacher: " + form_error_summary(form),
        )
    return redirect(reverse("academics:subject_detail", args=[subject.pk]))


@staff_required
@require_POST
def subject_assignment_delete(request, pk):
    from teachers.models import SubjectAssignment

    assignment = get_object_or_404(SubjectAssignment, pk=pk)
    subject = assignment.subject
    assignment.delete()
    messages.success(request, "Teacher removed from the subject.")
    return redirect(reverse("academics:subject_detail", args=[subject.pk]))


# ---------------------------------------------------------------------------
# Helpers used by dependent forms (AJAX dependent dropdowns)
# ---------------------------------------------------------------------------
@staff_required
@require_GET
def course_options(request):
    """Return courses (optionally filtered by department) as JSON."""
    courses = Course.objects.select_related("department").filter(is_active=True)
    department_id = request.GET.get("department")
    if department_id:
        courses = courses.filter(department_id=department_id)
    data = [
        {
            "id": course.pk,
            "name": course.name,
            "code": course.code,
            "department": course.department.name,
            "total_semesters": course.total_semesters,
        }
        for course in courses
    ]
    return JsonResponse({"results": data, "count": len(data)})
