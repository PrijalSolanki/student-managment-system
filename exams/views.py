from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Avg, Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.views.generic import CreateView, DeleteView, DetailView, UpdateView

from academics.models import Subject
from core.mixins import FilterableListView, FormSuccessMixin, ProtectedDeleteMixin
from core.models import AuditLog
from core.permissions import StaffRequiredMixin, log_action, staff_required
from core.utils import paginate, parse_int
from exams.forms import (
    ExamFilterForm,
    ExamForm,
    ExamSubjectForm,
    MarkEntryFilterForm,
    MarkEntryForm,
    ResultFilterForm,
    StudentExamFilterForm,
)
from exams.models import Exam, ExamSubject, MarkEntry, Result
from exams.services import (
    GRADE_SCALE,
    calculate_grade,
    exam_progress,
    exam_students,
    grade_description,
    overall_percentage,
    rank_of_student,
    recalculate_exam_results,
    result_sheet,
)
from students.models import Student


class ExamListView(StaffRequiredMixin, FilterableListView):
    model = Exam
    template_name = "exams/exam_list.html"
    context_object_name = "exams"
    list_title = "Examinations"
    active_menu = "exams"
    breadcrumb_parent = "Examinations"
    module_name = "exams"
    paginate_by = 12
    search_fields = ["name", "code"]
    filter_fields = ["course", "semester", "exam_type"]
    filter_lookups = {
        "course": "course_id",
        "semester": "semester_id",
        "exam_type": "exam_type",
    }
    date_range_fields = ["start_date"]
    ordering_fields = {
        "name": "name",
        "code": "code",
        "start_date": "-start_date",
        "-start_date": "-start_date",
        "created": "-created_at",
    }
    default_ordering = "-start_date"

    def get_queryset(self):
        queryset = Exam.objects.select_related("course", "semester", "created_by").annotate(
            subject_total=Count("exam_subjects", distinct=True),
            result_total=Count("results", distinct=True),
        )
        queryset = self.filter_queryset(queryset)
        status = (self.request.GET.get("status") or "").strip()
        today = timezone.localdate()
        if status == "upcoming":
            queryset = queryset.filter(start_date__gt=today)
        elif status == "running":
            queryset = queryset.filter(start_date__lte=today, end_date__gte=today)
        elif status == "completed":
            queryset = queryset.filter(end_date__lt=today)
        elif status == "published":
            queryset = queryset.filter(is_published=True)
        elif status == "unpublished":
            queryset = queryset.filter(is_published=False)
        return queryset.order_by(self.get_ordering())

    def get_table_columns(self):
        return [
            {"label": "Code", "attr": "code", "sort": "code"},
            {"label": "Exam", "attr": "name", "sort": "name"},
            {"label": "Type", "attr": "get_exam_type_display"},
            {"label": "Course", "attr": "course.name"},
            {"label": "Semester", "attr": "semester.number", "align": "center"},
            {"label": "Year", "attr": "academic_year", "align": "center"},
            {"label": "Starts", "attr": "start_date", "date": "d M Y", "sort": "start_date"},
            {"label": "Ends", "attr": "end_date", "date": "d M Y"},
            {"label": "Subjects", "attr": "subject_total", "align": "center"},
            {"label": "Results", "attr": "result_total", "align": "center"},
            {"label": "Status", "attr": "is_published", "bool": True},
        ]

    def get_table_actions(self):
        return {
            "detail": "exams:exam_detail",
            "edit": "exams:exam_edit",
            "delete": "exams:exam_delete",
            "extra": [{"url": "exams:mark_entry", "label": "Mark entry", "icon": "bi-pencil-square"}],
        }

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(
            {
                "filter_form": ExamFilterForm(self.request.GET or None),
                "total_exams": Exam.objects.count(),
                "published_exams": Exam.objects.filter(is_published=True).count(),
                "running_exams": Exam.objects.filter(
                    start_date__lte=timezone.localdate(), end_date__gte=timezone.localdate()
                ).count(),
                "pending_results": Exam.objects.filter(results_published=False).count(),
            }
        )
        return context

    def get_export_rows(self, queryset=None):
        queryset = queryset if queryset is not None else self.get_queryset()
        headers = [
            "Code",
            "Name",
            "Type",
            "Course",
            "Semester",
            "Academic Year",
            "Start",
            "End",
            "Subjects",
            "Published",
            "Results Published",
        ]
        rows = [
            [
                exam.code,
                exam.name,
                exam.get_exam_type_display(),
                exam.course.name,
                exam.semester.name,
                exam.academic_year,
                exam.start_date,
                exam.end_date,
                exam.subject_total,
                "Yes" if exam.is_published else "No",
                "Yes" if exam.results_published else "No",
            ]
            for exam in queryset
        ]
        return headers, rows


class ExamCreateView(StaffRequiredMixin, FormSuccessMixin, CreateView):
    model = Exam
    form_class = ExamForm
    template_name = "exams/exam_form.html"
    success_url = "/exams/"

    def get_initial(self):
        initial = super().get_initial()
        initial.setdefault("academic_year", timezone.localdate().strftime("%Y-%Y"))
        return initial

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(
            {
                "page_title": "Add Exam",
                "active_menu": "exams",
                "breadcrumb_parent": "Examinations",
                "form_title": "Add Exam",
                "exam_subjects": [],
                "subject_choices": Subject.objects.select_related("semester").order_by("code"),
            }
        )
        return context

    def form_valid(self, form):
        with transaction.atomic():
            self.object = form.save(commit=False)
            self.object.created_by = self.request.user
            self.object.save()
            subjects = self.request.POST.getlist("subject_code")
            created = 0
            for code in subjects:
                code = (code or "").strip()
                if not code:
                    continue
                try:
                    subject = Subject.objects.get(code=code)
                except Subject.DoesNotExist:
                    continue
                ExamSubject.objects.get_or_create(
                    exam=self.object,
                    subject=subject,
                    defaults={
                        "max_marks": self.request.POST.get(f"max_marks_{code}") or 100,
                        "exam_date": self.request.POST.get(f"exam_date_{code}") or self.object.start_date,
                        "exam_time": self.request.POST.get(f"exam_time_{code}", ""),
                        "venue": self.request.POST.get(f"venue_{code}", ""),
                    },
                )
                created += 1
        log_action(
            self.request,
            AuditLog.Action.CREATE,
            module="exams",
            obj=self.object,
            description=f"Exam '{self.object}' created with {created} subject(s)",
        )
        messages.success(self.request, f"Exam created with {created} subject(s).")
        self.success_url = self.object.get_absolute_url()
        return redirect(self.success_url)


class ExamUpdateView(StaffRequiredMixin, FormSuccessMixin, UpdateView):
    model = Exam
    form_class = ExamForm
    template_name = "exams/exam_form.html"

    def get_success_url(self):
        return self.object.get_absolute_url()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(
            {
                "page_title": f"Edit {self.object.code}",
                "active_menu": "exams",
                "breadcrumb_parent": self.object.name,
                "exam_subjects": self.object.exam_subjects.select_related("subject"),
                "subject_choices": Subject.objects.select_related("semester").order_by("code"),
                "eligible_students": exam_students(self.object).count(),
            }
        )
        return context

    def form_valid(self, form):
        with transaction.atomic():
            self.object = form.save()
            for exam_subject in self.object.exam_subjects.select_related("subject"):
                code = exam_subject.subject.code
                exam_subject.max_marks = self.request.POST.get(
                    f"max_marks_{code}", exam_subject.max_marks
                )
                exam_subject.exam_date = self.request.POST.get(
                    f"exam_date_{code}", exam_subject.exam_date
                )
                exam_subject.exam_time = self.request.POST.get(
                    f"exam_time_{code}", exam_subject.exam_time
                )
                exam_subject.venue = self.request.POST.get(f"venue_{code}", exam_subject.venue)
                exam_subject.save()
            for code in self.request.POST.getlist("subject_code"):
                code = (code or "").strip()
                if not code:
                    continue
                if self.object.exam_subjects.filter(subject__code=code).exists():
                    continue
                subject = Subject.objects.filter(code=code).first()
                if not subject:
                    continue
                ExamSubject.objects.create(
                    exam=self.object,
                    subject=subject,
                    max_marks=self.request.POST.get(f"max_marks_{code}") or 100,
                    exam_date=self.request.POST.get(f"exam_date_{code}") or self.object.start_date,
                    exam_time=self.request.POST.get(f"exam_time_{code}", ""),
                    venue=self.request.POST.get(f"venue_{code}", ""),
                )
        return super().form_valid(form)


class ExamDetailView(StaffRequiredMixin, DetailView):
    model = Exam
    template_name = "exams/exam_detail.html"
    context_object_name = "exam"

    def get_queryset(self):
        return Exam.objects.select_related("course", "semester", "created_by")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        exam = self.object
        results = exam.results.select_related("student").order_by("-percentage")
        grade_rows = (
            results.values("grade")
            .annotate(count=Count("id"))
            .order_by("grade")
        )
        context.update(
            {
                "page_title": exam.name,
                "active_menu": "exams",
                "breadcrumb_parent": "Examinations",
                "exam_subjects": exam.exam_subjects.select_related("subject"),
                "result_total": exam.results.count(),
                "pass_total": exam.results.filter(is_pass=True).count(),
                "fail_total": exam.results.filter(is_pass=False).count(),
                "top_results": results[:10],
                "grade_distribution": sorted(
                    list(grade_rows), key=lambda row: row["grade"]
                ),
                "progress": exam_progress(exam),
                "recent_marks": MarkEntry.objects.filter(exam=exam)
                .select_related("student", "exam_subject__subject")
                .order_by("-updated_at")[:10],
            }
        )
        return context


class ExamDeleteView(StaffRequiredMixin, ProtectedDeleteMixin, DeleteView):
    model = Exam
    template_name = "exams/exam_confirm_delete.html"
    success_url = "/exams/"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(
            {
                "page_title": f"Delete {self.object.code}",
                "breadcrumb_parent": self.object.name,
                "active_menu": "exams",
                "blocking_reason": (
                    f"{self.object.results.count()} result(s) already exist for this exam."
                    if self.object.results.exists()
                    else "Deleting this exam removes its subjects and mark entries."
                ),
            }
        )
        return context


@staff_required
@require_POST
def exam_publish_toggle(request, pk):
    exam = get_object_or_404(Exam, pk=pk)
    exam.is_published = not exam.is_published
    if not exam.is_published:
        exam.results_published = False
    exam.save(update_fields=["is_published", "results_published", "updated_at"])
    log_action(
        request,
        AuditLog.Action.UPDATE,
        module="exams",
        obj=exam,
        description=f"Exam '{exam.code}' {'published' if exam.is_published else 'unpublished'}",
    )
    messages.success(
        request,
        f"Exam '{exam.code}' is now {'visible to students' if exam.is_published else 'hidden from students'}.",
    )
    return redirect(exam.get_absolute_url())


@staff_required
@require_POST
def exam_recalculate(request, pk):
    exam = get_object_or_404(Exam, pk=pk)
    if exam.results_published:
        messages.warning(request, "Unpublish the results before recalculating.")
        return redirect(exam.get_absolute_url())
    summary = recalculate_exam_results(exam)
    log_action(
        request,
        AuditLog.Action.UPDATE,
        module="exams",
        obj=exam,
        description=f"Recalculated {summary['created'] + summary['updated']} result(s) for {exam.code}",
    )
    messages.success(
        request,
        f"Recalculated {summary['created'] + summary['updated']} result(s) for {exam.code}.",
    )
    return redirect(reverse("exams:result_list") + f"?exam={exam.pk}")


@staff_required
@require_POST
def exam_results_publish(request, pk):
    exam = get_object_or_404(Exam, pk=pk)
    action_type = request.POST.get("action", "publish")
    if action_type == "unpublish":
        exam.results_published = False
        exam.results.update(published=False)
        message = "Results hidden from students."
    else:
        exam.results_published = True
        exam.results.update(published=True)
        message = "Results published to students."
        if not exam.is_published:
            exam.is_published = True
    exam.save(update_fields=["results_published", "is_published", "updated_at"])
    log_action(
        request,
        AuditLog.Action.UPDATE,
        module="exams",
        obj=exam,
        description=f"Exam '{exam.code}' results {action_type}ed",
    )
    messages.success(request, message)
    return redirect(exam.get_absolute_url())


class ExamSubjectDeleteView(StaffRequiredMixin, DeleteView):
    model = ExamSubject
    template_name = "exams/exam_subject_confirm_delete.html"

    def get_success_url(self):
        return self.object.exam.get_absolute_url()

    def form_valid(self, form):
        if self.object.mark_entries.exists():
            messages.error(
                self.request,
                f"Cannot remove '{self.object.subject.code}' because marks have already been entered.",
            )
            return redirect(self.get_success_url())
        log_action(
            self.request,
            AuditLog.Action.DELETE,
            module="exams",
            obj=self.object.exam,
            description=f"Subject '{self.object.subject.code}' removed from exam '{self.object.exam.code}'",
        )
        self.object.delete()
        messages.success(self.request, "Subject removed from the exam.")
        return redirect(self.get_success_url())

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(
            {
                "page_title": "Remove Subject",
                "active_menu": "exams",
                "breadcrumb_parent": str(self.object.exam),
                "blocking_reason": (
                    f"{self.object.mark_entries.count()} mark entry/entries exist."
                    if self.object.mark_entries.exists()
                    else "The subject will be removed from this exam only."
                ),
            }
        )
        return context


class MarksEntryView(StaffRequiredMixin, FormSuccessMixin, DetailView):
    """Grid based mark entry for one exam subject."""

    model = Exam
    template_name = "exams/mark_entry.html"
    context_object_name = "exam"

    def get_exam(self):
        if not hasattr(self, "exam"):
            self.exam = get_object_or_404(Exam.objects.select_related("course", "semester"), pk=self.kwargs["pk"])
        return self.exam

    def get_object(self, queryset=None):
        return self.get_exam()

    @transaction.atomic
    def post(self, request, *args, **kwargs):
        exam = self.get_exam()
        exam_subject = get_object_or_404(
            ExamSubject.objects.select_related("subject", "exam"), pk=parse_int(request.POST.get("exam_subject"))
        )
        if exam_subject.exam_id != exam.pk:
            messages.error(request, "Selected subject does not belong to this exam.")
            return redirect(reverse("exams:mark_entry", args=[exam.pk]))
        if not exam.allow_marks_entry:
            messages.warning(request, "Mark entry is locked for this exam.")
            return redirect(exam.get_absolute_url())

        students = list(exam_students(exam))
        existing = {
            entry.student_id: entry
            for entry in MarkEntry.objects.filter(exam_subject=exam_subject, exam=exam)
        }
        saved = 0
        skipped = 0
        for student in students:
            raw = request.POST.get(f"marks_{student.pk}")
            absent = request.POST.get(f"absent_{student.pk}") in {"on", "1", "true", "True"}
            remark = request.POST.get(f"remark_{student.pk}", "")
            if raw in (None, "") and not absent:
                skipped += 1
                continue
            entry = existing.get(student.pk)
            if entry is None:
                entry = MarkEntry(exam=exam, exam_subject=exam_subject, student=student)
            entry.marks_obtained = None if absent or raw in (None, "") else raw
            entry.is_absent = absent
            entry.remarks = remark
            entry.entered_by = request.user
            try:
                entry.full_clean(exclude=["exam", "exam_subject", "student"])
                entry.save()
                saved += 1
            except ValidationError as exc:
                skipped += 1
                messages.error(
                    request,
                    f"{student.full_name}: {' '.join(exc.messages)}",
                )
        log_action(
            request,
            AuditLog.Action.UPDATE,
            module="exams",
            obj=exam,
            description=f"{saved} mark(s) saved for {exam.code} - {exam_subject.subject.code}",
        )
        recalculate_exam_results(exam, students=students)
        messages.success(
            request,
            f"Saved {saved} mark(s) for {exam_subject.subject.code}"
            + (f"; {skipped} row(s) skipped." if skipped else "."),
        )
        return redirect(f"{reverse('exams:mark_entry', args=[exam.pk])}?exam_subject={exam_subject.pk}")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        exam = self.exam
        subjects = list(exam.exam_subjects.select_related("subject"))
        selected_id = parse_int(self.request.GET.get("exam_subject"))
        exam_subject = next((item for item in subjects if item.pk == selected_id), subjects[0] if subjects else None)

        rows = []
        if exam_subject:
            entries = {
                entry.student_id: entry
                for entry in MarkEntry.objects.filter(exam=exam, exam_subject=exam_subject)
            }
            for student in exam_students(exam):
                entry = entries.get(student.pk)
                rows.append(
                    {
                        "student": student,
                        "entry": entry,
                        "marks": "" if not entry or entry.is_absent else (entry.marks_obtained or ""),
                        "is_absent": bool(entry and entry.is_absent),
                        "remark": entry.remarks if entry else "",
                    }
                )
        context.update(
            {
                "page_title": f"Mark Entry - {exam.code}",
                "active_menu": "exams",
                "breadcrumb_parent": exam.name,
                "exam_subjects": subjects,
                "exam_subject": exam_subject,
                "rows": rows,
                "entry_forms": {
                    row["student"].pk: MarkEntryForm(
                        instance=row["entry"],
                        max_marks=exam_subject.max_marks if exam_subject else None,
                        prefix=f"row_{row['student'].pk}",
                    )
                    for row in rows
                },
                "entered_count": sum(1 for row in rows if row["marks"] != "" or row["is_absent"]),
            }
        )
        return context


class MarkEntryListView(StaffRequiredMixin, FilterableListView):
    model = MarkEntry
    template_name = "exams/mark_entry_list.html"
    context_object_name = "entries"
    list_title = "Mark Entries"
    active_menu = "exams"
    breadcrumb_parent = "Examinations"
    module_name = "marks"
    search_fields = ["student__first_name", "student__last_name", "student__student_id", "exam_subject__subject__code"]
    filter_fields = ["exam", "exam_subject", "teacher"]
    filter_lookups = {
        "exam": "exam_id",
        "exam_subject": "exam_subject_id",
        "teacher": "exam_subject__subject__assignments__teacher_id",
    }
    ordering_fields = {
        "exam": "exam__code",
        "student": "student__student_id",
        "marks": "-marks_obtained",
        "-marks": "-marks_obtained",
        "updated": "-updated_at",
    }
    default_ordering = "-updated_at"

    def get_queryset(self):
        queryset = MarkEntry.objects.select_related(
            "exam", "exam_subject__subject", "student", "entered_by"
        ).distinct()
        return self.filter_queryset(queryset).order_by(self.get_ordering())

    def get_table_columns(self):
        return [
            {"label": "Exam", "attr": "exam.code", "sort": "exam"},
            {"label": "Subject", "attr": "exam_subject.subject.code"},
            {"label": "Student", "attr": "student.student_id", "sort": "student"},
            {"label": "Name", "attr": "student.full_name"},
            {"label": "Marks", "attr": "display_marks", "align": "end", "sort": "marks"},
            {"label": "Max", "attr": "exam_subject.max_marks", "align": "end"},
            {"label": "Absent", "attr": "is_absent", "bool": True},
            {"label": "Entered by", "attr": "entered_by.username"},
            {"label": "Updated", "attr": "updated_at", "datetime": "d M Y H:i", "sort": "updated"},
        ]

    def get_table_actions(self):
        return {}

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({"filter_form": MarkEntryFilterForm(self.request.GET or None)})
        return context

    def get_export_rows(self, queryset=None):
        queryset = queryset if queryset is not None else self.get_queryset()
        headers = ["Exam", "Subject", "Student", "Name", "Marks", "Max", "Absent", "Entered By", "Updated"]
        rows = [
            [
                entry.exam.code,
                entry.exam_subject.subject.code,
                entry.student.student_id,
                entry.student.full_name,
                entry.display_marks,
                entry.exam_subject.max_marks,
                "Yes" if entry.is_absent else "No",
                entry.entered_by.username if entry.entered_by else "-",
                entry.updated_at,
            ]
            for entry in queryset
        ]
        return headers, rows


class ResultListView(StaffRequiredMixin, FilterableListView):
    model = Result
    template_name = "exams/result_list.html"
    context_object_name = "results"
    list_title = "Results"
    active_menu = "results"
    breadcrumb_parent = "Examinations"
    module_name = "results"
    search_fields = ["student__first_name", "student__last_name", "student__student_id"]
    filter_fields = ["exam", "grade", "department", "course"]
    filter_lookups = {
        "exam": "exam_id",
        "grade": "grade",
        "department": "student__department_id",
        "course": "student__course_id",
    }
    ordering_fields = {
        "percentage": "-percentage",
        "-percentage": "-percentage",
        "student": "student__student_id",
        "grade": "grade",
        "exam": "exam__code",
    }
    default_ordering = "-percentage"

    def get_queryset(self):
        queryset = Result.objects.select_related(
            "exam", "student", "student__department", "student__course"
        )
        queryset = self.filter_queryset(queryset)
        passed = (self.request.GET.get("is_pass") or "").strip()
        if passed == "yes":
            queryset = queryset.filter(is_pass=True)
        elif passed == "no":
            queryset = queryset.filter(is_pass=False)
        return queryset.order_by(self.get_ordering())

    def get_table_columns(self):
        return [
            {"label": "Student", "attr": "student.student_id", "sort": "student"},
            {"label": "Name", "attr": "student.full_name"},
            {"label": "Exam", "attr": "exam.code", "sort": "exam"},
            {"label": "Department", "attr": "student.department.name"},
            {"label": "Total", "attr": "total_marks", "align": "end"},
            {"label": "Max", "attr": "max_marks", "align": "end"},
            {"label": "Percentage", "attr": "percentage", "pct": True, "sort": "percentage"},
            {"label": "Grade", "attr": "grade", "align": "center", "sort": "grade"},
            {"label": "Result", "attr": "is_pass", "bool": True},
        ]

    def get_table_actions(self):
        return {
            "detail": "exams:result_detail",
            "extra": [
                {"url": "exams:result_marksheet", "label": "Marksheet", "icon": "bi-printer"},
            ],
        }

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        base = Result.objects.all()
        aggregate = base.aggregate(average=Avg("percentage"))
        context.update(
            {
                "filter_form": ResultFilterForm(self.request.GET or None),
                "total_results": base.count(),
                "passed_total": base.filter(is_pass=True).count(),
                "failed_total": base.filter(is_pass=False).count(),
                "average_percentage": round(float(aggregate["average"] or 0), 2),
                "grade_scale": GRADE_SCALE,
            }
        )
        return context

    def get_export_rows(self, queryset=None):
        queryset = queryset if queryset is not None else self.get_queryset()
        headers = [
            "Exam",
            "Student",
            "Name",
            "Department",
            "Total",
            "Max",
            "Percentage",
            "Grade",
            "Grade Point",
            "Result",
            "Failed Subjects",
        ]
        rows = [
            [
                result.exam.code,
                result.student.student_id,
                result.student.full_name,
                result.student.department.name if result.student.department_id else "-",
                result.total_marks,
                result.max_marks,
                result.percentage,
                result.grade,
                result.grade_point,
                "PASS" if result.is_pass else "FAIL",
                result.failed_subjects,
            ]
            for result in queryset
        ]
        return headers, rows


class ResultDetailView(StaffRequiredMixin, DetailView):
    model = Result
    template_name = "exams/result_detail.html"
    context_object_name = "result"

    def get_queryset(self):
        return Result.objects.select_related("exam", "student", "student__department", "student__course")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        result = self.object
        context.update(
            {
                "page_title": f"Result - {result.student.full_name}",
                "active_menu": "results",
                "breadcrumb_parent": result.exam.code,
                "rows": result_sheet(result.exam, result.student),
                "rank": rank_of_student(result.exam, result.student),
                "overall_percentage": overall_percentage(result.student),
                "grade_description": grade_description(result.grade),
                "institution": None,
            }
        )
        return context


@staff_required
def result_marksheet(request, pk):
    """Printable marksheet (HTML) and PDF for one result."""
    result = get_object_or_404(
        Result.objects.select_related("exam__course", "exam__semester", "student"), pk=pk
    )
    rows = result_sheet(result.exam, result.student)
    context = {
        "result": result,
        "rows": rows,
        "rank": rank_of_student(result.exam, result.student),
        "grade_scale": GRADE_SCALE,
        "page_title": f"Marksheet - {result.student.full_name}",
    }
    if request.GET.get("format") == "pdf":
        from core.exports import export_pdf

        headers = ["Code", "Subject", "Max", "Pass", "Obtained", "%", "Grade", "Result"]
        body = [
            [
                row["subject"].code,
                row["subject"].name,
                row["max_marks"],
                row["pass_marks"],
                "Absent" if row["is_absent"] else (row["obtained"] if row["obtained"] is not None else "-"),
                row["percentage"],
                row["grade"],
                "PASS" if row["is_pass"] else "FAIL",
            ]
            for row in rows
        ]
        body.append(
            [
                "TOTAL",
                f"{len(rows)} subject(s)",
                result.max_marks,
                "-",
                result.total_marks,
                result.percentage,
                result.grade,
                "PASS" if result.is_pass else "FAIL",
            ]
        )
        log_action(
            request,
            AuditLog.Action.EXPORT,
            module="exams",
            obj=result,
            description=f"Marksheet PDF generated for {result.student.full_name}",
        )
        return export_pdf(
            "marksheet",
            headers,
            body,
            title=f"Marksheet - {result.student.full_name} ({result.exam.code})",
            meta=[
                ("Student", result.student.full_name),
                ("Code", result.student.student_id),
                ("Exam", result.exam.code),
                ("Total", f"{result.total_marks}/{result.max_marks}"),
                ("Percentage", f"{result.percentage}%"),
                ("Grade", result.grade),
            ],
        )
    return render(request, "exams/marksheet_print.html", context)


@staff_required
def grade_scale(request):
    """Reference page describing the grading policy."""
    return render(
        request,
        "exams/grade_scale.html",
        {
            "grade_scale": GRADE_SCALE,
            "page_title": "Grading Policy",
            "active_menu": "results",
        },
    )


class StudentResultListView(StaffRequiredMixin, FilterableListView):
    """All results of a single student."""

    model = Result
    template_name = "exams/student_result_list.html"
    context_object_name = "results"
    list_title = "Student Results"
    active_menu = "results"
    breadcrumb_parent = "Results"
    module_name = "student_results"
    search_fields = ["exam__name", "exam__code"]
    filter_fields = ["exam"]
    filter_lookups = {"exam": "exam_id"}
    ordering_fields = {"percentage": "-percentage", "exam": "-exam__start_date"}
    default_ordering = "-exam__start_date"

    def setup(self, request, *args, **kwargs):
        super().setup(request, *args, **kwargs)
        self.student = get_object_or_404(Student, pk=self.kwargs["student_pk"])

    def get_queryset(self):
        queryset = Result.objects.filter(student=self.student).select_related("exam")
        return self.filter_queryset(queryset).order_by(self.get_ordering())

    def get_table_columns(self):
        return [
            {"label": "Exam", "attr": "exam.code", "sort": "exam"},
            {"label": "Name", "attr": "exam.name"},
            {"label": "Total", "attr": "total_marks", "align": "end"},
            {"label": "Max", "attr": "max_marks", "align": "end"},
            {"label": "Percentage", "attr": "percentage", "pct": True, "sort": "percentage"},
            {"label": "Grade", "attr": "grade", "align": "center"},
            {"label": "Result", "attr": "is_pass", "bool": True},
        ]

    def get_table_actions(self):
        return {
            "detail": "exams:result_detail",
            "extra": [{"url": "exams:result_marksheet", "label": "Marksheet", "icon": "bi-printer"}],
        }

    def get_export_rows(self, queryset=None):
        queryset = queryset if queryset is not None else self.get_queryset()
        headers = ["Exam", "Name", "Total", "Max", "Percentage", "Grade", "Result"]
        rows = [
            [
                item.exam.code,
                item.exam.name,
                item.total_marks,
                item.max_marks,
                item.percentage,
                item.grade,
                "PASS" if item.is_pass else "FAIL",
            ]
            for item in queryset
        ]
        return headers, rows

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        results = list(context["results"]) if context.get("results") else []
        aggregate = Result.objects.filter(student=self.student).aggregate(average=Avg("percentage"))
        context.update(
            {
                "student": self.student,
                "filter_form": StudentExamFilterForm(initial={"student": self.student}),
                "average_percentage": round(float(aggregate["average"] or 0), 2),
                "passed_total": Result.objects.filter(student=self.student, is_pass=True).count(),
                "failed_total": Result.objects.filter(student=self.student, is_pass=False).count(),
                "chart_data": {
                    "labels": [result.exam.code for result in results],
                    "values": [float(result.percentage or 0) for result in results],
                },
            }
        )
        return context


@staff_required
def exam_report(request):
    """Exam wise analytics: pass rate, average marks and grade distribution."""
    exams = Exam.objects.select_related("course", "semester").prefetch_related("results")
    rows = []
    grade_labels = [band["grade"] for band in GRADE_SCALE]
    chart_data = {"labels": [], "passed": [], "failed": [], "average": []}
    for exam in exams:
        results = list(exam.results.all())
        total = len(results)
        passed = sum(1 for item in results if item.is_pass)
        failed = total - passed
        average = round(sum(float(item.percentage or 0) for item in results) / total, 2) if total else 0.0
        distribution = {band["grade"]: 0 for band in GRADE_SCALE}
        for item in results:
            if item.grade in distribution:
                distribution[item.grade] += 1
        rows.append(
            {
                "exam": exam,
                "total": total,
                "passed": passed,
                "failed": failed,
                "average": average,
                "pass_rate": round((passed / total) * 100, 2) if total else 0.0,
                "distribution": distribution,
            }
        )
        chart_data["labels"].append(exam.code)
        chart_data["passed"].append(passed)
        chart_data["failed"].append(failed)
        chart_data["average"].append(average)

    headers = ["Exam", "Course", "Semester", "Type", "Students", "Passed", "Failed", "Pass %", "Average %"]
    export_rows = [
        [row["exam"].code, row["exam"].course.name, row["exam"].semester.name,
         row["exam"].get_exam_type_display(), row["total"], row["passed"], row["failed"],
         row["pass_rate"], row["average"]]
        for row in rows
    ]

    if request.GET.get("format"):
        from core.exports import ExportError, export_data

        try:
            response = export_data(
                request,
                "exam_report",
                headers,
                export_rows,
                title="Exam Report",
                meta=[("Generated", timezone.localtime().strftime("%Y-%m-%d %H:%M"))],
            )
        except ExportError as exc:
            messages.error(request, str(exc))
            return redirect("exams:exam_report")
        log_action(
            request,
            AuditLog.Action.EXPORT,
            module="exams",
            description="Exported exam report",
        )
        return response

    page = paginate(request, rows, per_page=15)
    return render(
        request,
        "exams/exam_report.html",
        {
            "page_obj": page,
            "is_paginated": page.has_other_pages(),
            "rows": page.object_list,
            "grade_labels": grade_labels,
            "chart_data": chart_data,
            "page_title": "Exam Report",
            "active_menu": "reports",
        },
    )


__all__ = [
    "ExamListView",
    "ExamCreateView",
    "ExamUpdateView",
    "ExamDetailView",
    "ExamDeleteView",
    "exam_publish_toggle",
    "exam_recalculate",
    "exam_results_publish",
    "ExamSubjectDeleteView",
    "MarksEntryView",
    "MarkEntryListView",
    "ResultListView",
    "ResultDetailView",
    "result_marksheet",
    "grade_scale",
    "StudentResultListView",
    "exam_report",
    "calculate_grade",
]