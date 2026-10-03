"""Attendance views: marking, records and reports."""

from __future__ import annotations

from django.contrib import messages
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST
from django.views.generic import DeleteView

from academics.models import Course, Department, Semester, Subject
from attendance.forms import AttendanceFilterForm, AttendanceMarkForm
from attendance.models import Attendance
from attendance.services import (
    attendance_totals,
    daily_report,
    monthly_report,
    save_bulk_attendance,
    student_report,
    subject_report,
)
from core.mixins import FilterableListView, ProtectedDeleteMixin
from core.models import AuditLog
from core.permissions import StaffRequiredMixin, log_action, staff_required
from core.utils import parse_date, parse_int, percent, querystring_without_page
from students.models import Student
from teachers.models import Teacher


# ---------------------------------------------------------------------------
# Mark attendance
# ---------------------------------------------------------------------------
class MarkAttendanceView(StaffRequiredMixin):
    """Plain view: the marking form is bound to GET (selection) and POST (save)."""

    template_name = "attendance/mark_attendance.html"

    def get_context_data(self, **kwargs):
        context = dict(kwargs)
        params = self.request.GET
        form = context.get("form")
        if form and form.is_valid():
            date = form.cleaned_data["date"]
            course = form.cleaned_data["course"]
            semester = form.cleaned_data["semester"]
            subject = form.cleaned_data["subject"]
            department = form.cleaned_data.get("department")
            students = (
                Student.objects.active()
                .with_details()
                .filter(course=course, semester=semester)
            )
            if department:
                students = students.filter(department=department)
            existing = {
                row["student"]: row["status"]
                for row in Attendance.objects.filter(
                    date=date, subject=subject, student__in=students
                ).values("student", "status")
            }
            rows = [
                {
                    "student": student,
                    "status": existing.get(student.pk, Attendance.Status.PRESENT),
                    "is_existing": student.pk in existing,
                }
                for student in students
            ]
            context.update(
                {
                    "rows": rows,
                    "date": date,
                    "subject": subject,
                    "course": course,
                    "semester": semester,
                    "department": department,
                    "already_marked": len(existing),
                    "subject_teacher": subject.assigned_teachers.first(),
                    "teacher_choices": Teacher.objects.filter(
                        department=subject.course.department
                    ).filter(status=Teacher.Status.ACTIVE),
                }
            )
        else:
            context.update({"rows": [], "already_marked": 0})
        context.update(
            {
                "page_title": "Mark Attendance",
                "breadcrumb_parent": "Attendance",
                "active_menu": "attendance",
                "today": timezone.localdate(),
                "courses": Course.objects.filter(is_active=True),
                "semesters": Semester.objects.all(),
                "subjects": Subject.objects.filter(is_active=True),
                "status_choices": Attendance.Status.choices,
            }
        )
        return context

    def get(self, request, *args, **kwargs):
        form = AttendanceMarkForm(request.GET or None)
        context = self.get_context_data(form=form)
        return render(request, self.template_name, context)

    def post(self, request, *args, **kwargs):
        form = AttendanceMarkForm(request.POST)
        if not form.is_valid():
            messages.error(request, "Please correct the highlighted errors.")
            return render(
                request,
                self.template_name,
                self.get_context_data(form=form),
            )

        date = form.cleaned_data["date"]
        subject = form.cleaned_data["subject"]
        teacher = form.cleaned_data.get("teacher") or subject.assigned_teachers.first()
        remarks = form.cleaned_data.get("remarks", "")

        entries = []
        for key, value in request.POST.items():
            if not key.startswith("status_"):
                continue
            student_id = key.split("_", 1)[1]
            if value in dict(Attendance.Status.choices):
                entries.append((student_id, value, subject.pk, teacher.pk if teacher else None, date, remarks))
        if not entries:
            messages.error(request, "No attendance entries were submitted.")
            return redirect(reverse("attendance:mark"))

        result = save_bulk_attendance(entries, request.user)
        messages.success(
            request,
            f"Attendance saved for {date:%d %b %Y} - {subject.code}: "
            f"{result['created']} new, {result['updated']} updated.",
        )
        log_action(
            request,
            AuditLog.Action.CREATE,
            module="attendance",
            obj=subject,
            description=(
                f"Marked attendance for {len(entries)} students on "
                f"{date:%d %b %Y} ({subject.code})"
            ),
        )
        params = request.POST.dict()
        params.pop("csrfmiddlewaretoken", None)
        return redirect(f"{reverse('attendance:mark')}?{_encode(params)}")


def _encode(params: dict) -> str:
    from django.utils.http import urlencode

    return urlencode({k: v for k, v in params.items() if v})


# ---------------------------------------------------------------------------
# Records
# ---------------------------------------------------------------------------
class AttendanceListView(StaffRequiredMixin, FilterableListView):
    model = Attendance
    template_name = "attendance/attendance_list.html"
    list_title = "Attendance Records"
    active_menu = "attendance"
    paginate_by = 15
    search_fields = ["student__student_id", "student__first_name", "student__last_name", "subject__name"]
    filter_fields = ["subject", "teacher", "course", "semester", "department", "status", "student", "date"]
    filter_lookups = {
        "subject": "subject_id",
        "teacher": "teacher_id",
        "course": "student__course_id",
        "semester": "student__semester_id",
        "department": "student__department_id",
        "status": "status",
        "student": "student_id",
        "date": "date",
    }
    date_range_fields = ["date"]
    ordering_fields = {
        "date": "date",
        "-date": "-date",
        "student": "student__student_id",
        "subject": "subject__code",
        "status": "status",
    }
    default_ordering = "-date"

    def get_queryset(self):
        queryset = Attendance.objects.select_related("student", "subject", "teacher", "marked_by")
        return self.filter_queryset(queryset).order_by(self.get_ordering())

    def get_filter_choices(self):
        return {
            "subject": [(s.pk, f"{s.code} {s.name}") for s in Subject.objects.all()[:200]],
            "teacher": [(t.pk, t.full_name) for t in Teacher.objects.all()[:200]],
            "course": [(c.pk, c.name) for c in Course.objects.all()],
            "semester": [(s.pk, str(s)) for s in Semester.objects.all()],
            "department": [(d.pk, d.name) for d in Department.objects.all()],
            "status": Attendance.Status.choices,
        }

    def get_table_columns(self):
        return [
            {"label": "Date", "attr": "date", "date": "d M Y", "sort": "date"},
            {"label": "Student", "attr": "student.student_id", "sort": "student"},
            {"label": "Name", "attr": "student.full_name"},
            {"label": "Subject", "attr": "subject.code", "sort": "subject"},
            {"label": "Teacher", "attr": "teacher.full_name"},
            {"label": "Status", "attr": "status", "badge": "status", "sort": "status"},
            {"label": "Marked by", "attr": "marked_by.username"},
        ]

    def get_table_actions(self):
        return {"delete": "attendance:attendance_delete"}

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        queryset = self.get_queryset()
        context.update(
            {
                "filter_form": AttendanceFilterForm(self.request.GET or None),
                "totals": attendance_totals(queryset),
                "today_count": Attendance.objects.filter(date=timezone.localdate()).count(),
                "preserve_query": querystring_without_page(self.request),
            }
        )
        return context

    def get_export_rows(self, queryset=None):
        queryset = queryset if queryset is not None else self.get_queryset()
        headers = ["Date", "Student ID", "Student", "Subject", "Teacher", "Status", "Remarks", "Marked By"]
        rows = [
            [
                item.date.strftime("%Y-%m-%d"),
                item.student.student_id,
                item.student.full_name,
                item.subject.code,
                item.teacher.full_name if item.teacher else "",
                item.get_status_display(),
                item.remarks,
                item.marked_by.username if item.marked_by else "",
            ]
            for item in queryset
        ]
        return headers, rows


class AttendanceDeleteView(StaffRequiredMixin, ProtectedDeleteMixin, DeleteView):
    model = Attendance
    template_name = "attendance/attendance_confirm_delete.html"
    success_url = "/attendance/records/"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(
            {
                "page_title": "Delete Attendance",
                "breadcrumb_parent": "Attendance",
                "active_menu": "attendance",
            }
        )
        return context


# ---------------------------------------------------------------------------
# Reports
# ---------------------------------------------------------------------------
@staff_required
@require_GET
def report_daily(request):
    date = parse_date(request.GET.get("date")) or timezone.localdate()
    data = daily_report(date)
    headers = ["Subject Code", "Subject", "Teacher", "Total", "Present", "Absent", "Leave", "%"]
    rows = [
        [row["subject_code"], row["subject"], row["teacher"], row["total"], row["present"],
         row["absent"], row["leave"], row["percentage"]]
        for row in data["rows"]
    ]
    if request.GET.get("export"):
        from core.exports import export_data

        return export_data(
            request,
            "daily_attendance",
            headers,
            rows,
            title=f"Daily Attendance - {date:%d %B %Y}",
            meta=[("Date", date.strftime("%d-%m-%Y")), ("Total Records", data["totals"]["total"])],
        )
    return render(
        request,
        "attendance/report_daily.html",
        {
            "data": data,
            "date": date,
            "page_title": "Daily Attendance Report",
            "breadcrumb_parent": "Reports",
            "active_menu": "attendance",
        },
    )


@staff_required
@require_GET
def report_monthly(request):
    today = timezone.localdate()
    year = parse_int(request.GET.get("year"), today.year)
    month = parse_int(request.GET.get("month"), today.month)
    if not 1 <= month <= 12:
        month = today.month
    data = monthly_report(year, month)
    headers = ["Date", "Total", "Present", "Absent", "Leave", "%"]
    rows = [
        [row["date"].strftime("%Y-%m-%d"), row["total"], row["present"], row["absent"],
         row["leave"], row["percentage"]]
        for row in data["days"]
    ]
    if request.GET.get("export"):
        from core.exports import export_data

        return export_data(
            request,
            "monthly_attendance",
            headers,
            rows,
            title=f"Monthly Attendance - {month:02d}/{year}",
            meta=[("Month", f"{month:02d}/{year}"), ("Records", data["totals"]["total"])],
        )
    years = list(range(today.year - 5, today.year + 1))
    return render(
        request,
        "attendance/report_monthly.html",
        {
            "data": data,
            "year": year,
            "month": month,
            "years": years,
            "months": [
                (index, name)
                for index, name in enumerate(
                    [
                        "January", "February", "March", "April", "May", "June",
                        "July", "August", "September", "October", "November", "December",
                    ],
                    start=1,
                )
            ],
            "page_title": "Monthly Attendance Report",
            "breadcrumb_parent": "Reports",
            "active_menu": "attendance",
        },
    )


@staff_required
@require_GET
def report_student(request):
    """Student-wise attendance report (optionally for a single student)."""
    student_id = request.GET.get("student")
    date_from = parse_date(request.GET.get("date_from"))
    date_to = parse_date(request.GET.get("date_to"))
    subject_id = request.GET.get("subject")

    data = None
    student = None
    if student_id:
        student = get_object_or_404(Student, pk=student_id)
        data = student_report(student, date_from, date_to)

    overview_queryset = Attendance.objects.select_related("student")
    if subject_id:
        overview_queryset = overview_queryset.filter(subject_id=subject_id)
    if date_from:
        overview_queryset = overview_queryset.filter(date__gte=date_from)
    if date_to:
        overview_queryset = overview_queryset.filter(date__lte=date_to)

    per_student = (
        overview_queryset.values(
            "student__id", "student__student_id", "student__first_name", "student__last_name"
        )
        .annotate(
            total=Count("id"),
            present=Count("id", filter=Q(status=Attendance.Status.PRESENT)),
            absent=Count("id", filter=Q(status=Attendance.Status.ABSENT)),
            leave=Count("id", filter=Q(status=Attendance.Status.LEAVE)),
        )
        .order_by("student__student_id")
    )
    rows = []
    for row in per_student:
        student_percentage = percent(row["present"], row["total"], 1)
        rows.append(
            {
                "student_id": row["student__id"],
                "student_code": row["student__student_id"],
                "student_name": f"{row['student__first_name']} {row['student__last_name']}".strip(),
                "total": row["total"],
                "present": row["present"],
                "absent": row["absent"],
                "leave": row["leave"],
                "percentage": student_percentage,
                "badge": "success" if student_percentage >= 75 else ("warning" if student_percentage >= 60 else "danger"),
            }
        )
    rows.sort(key=lambda item: item["percentage"])

    if request.GET.get("export"):
        from core.exports import export_data

        return export_data(
            request,
            "student_attendance",
            ["Student ID", "Student", "Total", "Present", "Absent", "Leave", "Percentage"],
            [[r["student_code"], r["student_name"], r["total"], r["present"], r["absent"], r["leave"], r["percentage"]] for r in rows],
            title="Student-wise Attendance Report",
        )
    return render(
        request,
        "attendance/report_student.html",
        {
            "data": data,
            "student": student,
            "rows": rows,
            "students": Student.objects.with_details()[:500],
            "subjects": Subject.objects.all(),
            "date_from": date_from,
            "date_to": date_to,
            "page_title": "Student-wise Attendance Report",
            "breadcrumb_parent": "Reports",
            "active_menu": "attendance",
        },
    )


@staff_required
@require_GET
def report_subject(request):
    subject_id = request.GET.get("subject")
    date_from = parse_date(request.GET.get("date_from"))
    date_to = parse_date(request.GET.get("date_to"))
    course_id = request.GET.get("course")
    semester_id = request.GET.get("semester")

    data = None
    subject = None
    if subject_id:
        subject = get_object_or_404(Subject, pk=subject_id)
        data = subject_report(
            subject,
            date_from,
            date_to,
            course=get_object_or_404(Course, pk=course_id) if course_id else None,
            semester=get_object_or_404(Semester, pk=semester_id) if semester_id else None,
        )

    if data and request.GET.get("export"):
        from core.exports import export_data

        return export_data(
            request,
            "subject_attendance",
            ["Student ID", "Student", "Total", "Present", "Absent", "Leave", "Percentage"],
            [
                [r["student_code"], r["student_name"], r["total"], r["present"], r["absent"], r["leave"], r["percentage"]]
                for r in data["rows"]
            ],
            title=f"Subject Attendance - {subject.code}",
        )
    return render(
        request,
        "attendance/report_subject.html",
        {
            "data": data,
            "subject": subject,
            "subjects": Subject.objects.select_related("course", "semester"),
            "courses": Course.objects.all(),
            "semesters": Semester.objects.all(),
            "date_from": date_from,
            "date_to": date_to,
            "page_title": "Subject-wise Attendance Report",
            "breadcrumb_parent": "Reports",
            "active_menu": "attendance",
        },
    )
