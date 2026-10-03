"""Teacher CRUD views."""

from __future__ import annotations

from django.contrib import messages
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse, reverse_lazy
from django.views.decorators.http import require_POST
from django.views.generic import CreateView, DeleteView, DetailView, UpdateView

from academics.models import Department
from core.mixins import FilterableListView, FormSuccessMixin, ProtectedDeleteMixin
from core.models import AuditLog
from core.permissions import (
    AdminRequiredMixin,
    StaffRequiredMixin,
    admin_required,
    log_action,
)
from teachers.forms import TeacherForm
from teachers.models import SubjectAssignment, Teacher


class TeacherListView(StaffRequiredMixin, FilterableListView):
    model = Teacher
    template_name = "teachers/teacher_list.html"
    list_title = "Teachers"
    active_menu = "teachers"
    search_fields = ["employee_id", "first_name", "last_name", "email", "phone", "qualification"]
    filter_fields = ["department", "status", "gender", "designation"]
    ordering_fields = {
        "name": "first_name",
        "-name": "-first_name",
        "employee_id": "employee_id",
        "newest": "-created_at",
        "salary": "-salary",
        "-salary": "salary",
    }
    default_ordering = "first_name"
    paginate_by = 10

    def get_queryset(self):
        queryset = (
            Teacher.objects.select_related("department")
            .annotate(subjects_total=Count("assignments", distinct=True))
            .all()
        )
        return self.filter_queryset(queryset).order_by(self.get_ordering())

    def get_filter_choices(self):
        return {
            "department": [(d.pk, d.name) for d in Department.objects.all()],
            "status": Teacher.Status.choices,
            "gender": Teacher.Gender.choices,
            "designation": sorted(
                {t.designation for t in Teacher.objects.exclude(designation="") if t.designation}
            ),
        }

    def get_table_columns(self):
        return [
            {"label": "Employee ID", "attr": "employee_id", "sort": "employee_id"},
            {"label": "Name", "attr": "full_name", "sort": "name"},
            {"label": "Email", "attr": "email"},
            {"label": "Phone", "attr": "phone"},
            {"label": "Department", "attr": "department.name"},
            {"label": "Designation", "attr": "designation"},
            {"label": "Subjects", "attr": "subjects_total", "align": "center"},
            {"label": "Status", "attr": "status", "badge": "status"},
        ]

    def get_table_actions(self):
        return {
            "detail": "teachers:teacher_detail",
            "edit": "teachers:teacher_edit",
            "delete": "teachers:teacher_delete",
            "extra": [{"url": "teachers:teacher_print", "label": "Print", "icon": "bi-printer"}],
        }

    def get_export_rows(self, queryset=None):
        queryset = queryset if queryset is not None else self.get_queryset()
        headers = [
            "Employee ID", "Name", "Email", "Phone", "Gender", "Department", "Qualification",
            "Designation", "Joining Date", "Salary", "Status", "Subjects",
        ]
        rows = [
            [
                obj.employee_id, obj.full_name, obj.email, obj.phone, obj.get_gender_display(),
                obj.department.name if obj.department else "", obj.qualification, obj.designation,
                obj.joining_date.strftime("%Y-%m-%d") if obj.joining_date else "",
                obj.salary, obj.get_status_display(), obj.subjects_total,
            ]
            for obj in queryset
        ]
        return headers, rows


class TeacherDetailView(StaffRequiredMixin, DetailView):
    model = Teacher
    template_name = "teachers/teacher_detail.html"
    context_object_name = "teacher"

    def get_context_data(self, **kwargs):
        from django.utils import timezone

        from attendance.models import Attendance

        context = super().get_context_data(**kwargs)
        teacher = self.object
        assignments = teacher.assignments.select_related("subject", "subject__semester")
        today = timezone.localdate()
        attendance_stats = Attendance.objects.filter(teacher=teacher).aggregate(
            total=Count("id"),
            present=Count("id", filter=Q(status=Attendance.Status.PRESENT)),
        )
        context.update(
            {
                "page_title": teacher.full_name,
                "breadcrumb_parent": "Teachers",
                "active_menu": "teachers",
                "assignments": assignments,
                "subjects": assignments.values_list("subject", flat=True),
                "attendance_total": attendance_stats["total"],
                "attendance_present": attendance_stats["present"],
                "attendance_marked_today": Attendance.objects.filter(
                    teacher=teacher, date=today
                ).count(),
                "attendance_records": Attendance.objects.filter(teacher=teacher)
                .select_related("subject")
                .order_by("-date", "-created_at")[:10],
                "students_taught": students_taught_count(teacher),
                "assignment_form": build_assignment_form(teacher),
            }
        )
        return context


def students_taught_count(teacher) -> int:
    from students.models import Student

    return (
        Student.objects.filter(course__subjects__assignments__teacher=teacher)
        .distinct()
        .count()
    )


def build_assignment_form(teacher):
    from academics.forms import SubjectAssignmentForm

    return SubjectAssignmentForm(initial={"teacher": teacher}, teacher=teacher)


class TeacherCreateView(AdminRequiredMixin, FormSuccessMixin, CreateView):
    model = Teacher
    form_class = TeacherForm
    template_name = "teachers/teacher_form.html"
    success_url = reverse_lazy("teachers:teacher_list")
    created_message = "Teacher created successfully."

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(
            {
                "page_title": "Add Teacher",
                "breadcrumb_parent": "Teachers",
                "active_menu": "teachers",
                "form_title": "Add Teacher",
            }
        )
        return context


class TeacherUpdateView(AdminRequiredMixin, FormSuccessMixin, UpdateView):
    model = Teacher
    form_class = TeacherForm
    template_name = "teachers/teacher_form.html"
    success_url = reverse_lazy("teachers:teacher_list")
    success_message = "Teacher updated successfully."

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(
            {
                "page_title": f"Edit {self.object.full_name}",
                "breadcrumb_parent": "Teachers",
                "active_menu": "teachers",
                "form_title": f"Edit Teacher: {self.object.full_name}",
            }
        )
        return context


class TeacherDeleteView(AdminRequiredMixin, ProtectedDeleteMixin, DeleteView):
    model = Teacher
    template_name = "teachers/teacher_confirm_delete.html"
    success_url = reverse_lazy("teachers:teacher_list")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(
            {
                "page_title": "Delete Teacher",
                "breadcrumb_parent": "Teachers",
                "active_menu": "teachers",
                "assignment_count": self.object.assignments.count(),
            }
        )
        return context


class TeacherPrintView(StaffRequiredMixin, DetailView):
    model = Teacher
    template_name = "teachers/teacher_print.html"
    context_object_name = "teacher"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        teacher = self.object
        attendance_stats = Attendance.objects.filter(teacher=teacher).aggregate(
            total=Count("id"),
            present=Count("id", filter=Q(status=Attendance.Status.PRESENT)),
        )
        context.update(
            {
                "page_title": f"Teacher Profile — {teacher.full_name}",
                "breadcrumb_parent": "Teachers",
                "active_menu": "teachers",
                "assignments": teacher.assignments.select_related("subject", "subject__semester"),
                "students_taught": students_taught_count(teacher),
                "attendance_total": attendance_stats["total"],
                "attendance_present": attendance_stats["present"],
            }
        )
        return context

    def get(self, request, *args, **kwargs):
        response = super().get(request, *args, **kwargs)
        log_action(
            request,
            AuditLog.Action.PRINT,
            module="teachers",
            obj=self.object,
            description=f"Printed teacher profile of {self.object.full_name}",
        )
        return response


@staff_required
@require_POST
def teacher_assignment_create(request, pk):
    from academics.forms import SubjectAssignmentForm

    teacher = get_object_or_404(Teacher, pk=pk)
    form = SubjectAssignmentForm(request.POST, teacher=teacher)
    if form.is_valid():
        assignment = form.save(commit=False)
        assignment.teacher = teacher
        assignment.assigned_by = request.user
        assignment.save()
        messages.success(request, f"{assignment.subject.name} assigned to {teacher.full_name}.")
    else:
        from core.utils import form_error_summary

        messages.error(request, "Could not assign subject: " + form_error_summary(form))
    return redirect(reverse("teachers:teacher_detail", args=[teacher.pk]))


@staff_required
@require_POST
def teacher_assignment_delete(request, pk):
    assignment = get_object_or_404(SubjectAssignment, pk=pk)
    teacher = assignment.teacher
    assignment.delete()
    messages.success(request, "Subject removed from the teacher.")
    return redirect(reverse("teachers:teacher_detail", args=[teacher.pk]))


@admin_required
@require_POST
def teacher_toggle_status(request, pk):
    teacher = get_object_or_404(Teacher, pk=pk)
    new_status = (
        Teacher.Status.INACTIVE
        if teacher.status == Teacher.Status.ACTIVE
        else Teacher.Status.ACTIVE
    )
    teacher.status = new_status
    teacher.save(update_fields=["status", "updated_at"])
    messages.success(request, f"{teacher.full_name} marked as {teacher.get_status_display().lower()}.")
    log_action(
        request,
        AuditLog.Action.STATUS_CHANGE,
        module="teachers",
        obj=teacher,
        description=f"Teacher status set to {teacher.get_status_display()}",
    )
    return redirect("teachers:teacher_detail", pk=teacher.pk)
