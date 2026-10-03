"""Student module views: list, CRUD, advanced filters, export, print, promotion."""

from __future__ import annotations

from django.contrib import messages
from django.db.models import Count, Q
from django.http import FileResponse, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST
from django.views.generic import CreateView, DeleteView, DetailView, UpdateView

from academics.models import Batch, Course, Department, Semester
from core.mixins import FilterableListView, FormSuccessMixin, ProtectedDeleteMixin
from core.models import AuditLog
from core.permissions import (
    AdminRequiredMixin,
    StaffRequiredMixin,
    admin_required,
    log_action,
    staff_required,
)
from core.utils import querystring_without_page
from students.forms import (
    StudentDocumentForm,
    StudentFilterForm,
    StudentForm,
    StudentPromotionForm,
)
from students.models import Student, StudentDocument, StudentPromotion
from students.services import promote_student, student_profile_context

LIST_TITLE = "Students"


# ---------------------------------------------------------------------------
# List + advanced search / filter / sort / paginate / export
# ---------------------------------------------------------------------------
class StudentListView(StaffRequiredMixin, FilterableListView):
    model = Student
    template_name = "students/student_list.html"
    list_title = LIST_TITLE
    active_menu = "students"
    paginate_by = 10
    search_fields = [
        "student_id",
        "first_name",
        "last_name",
        "email",
        "phone",
        "guardian_name",
        "guardian_phone",
    ]
    filter_fields = [
        "department",
        "course",
        "semester",
        "batch",
        "gender",
        "status",
        "blood_group",
        "category",
        "city",
        "state",
    ]
    date_range_fields = ["admission_date"]
    ordering_fields = {
        "student_id": "student_id",
        "-student_id": "-student_id",
        "name": "first_name",
        "-name": "-first_name",
        "admission_date": "admission_date",
        "-admission_date": "-admission_date",
        "created_at": "created_at",
        "-created_at": "-created_at",
        "age": "date_of_birth",
        "-age": "-date_of_birth",
        "email": "email",
    }
    default_ordering = "student_id"
    select_field = "student_ids"
    bulk_action_url = "students:student_bulk_action"

    def get_queryset(self):
        queryset = (
            Student.objects.with_details()
            .select_related("created_by")
            .all()
        )
        return self.filter_queryset(queryset).order_by(self.get_ordering())

    def get_filter_choices(self):
        return {
            "department": [(d.pk, d.name) for d in Department.objects.all()],
            "course": [(c.pk, f"{c.code} - {c.name}") for c in Course.objects.all()],
            "semester": [(s.pk, str(s)) for s in Semester.objects.all()],
            "batch": [(b.pk, b.name) for b in Batch.objects.all()],
            "gender": Student.Gender.choices,
            "status": Student.Status.choices,
            "blood_group": Student.BloodGroup.choices,
            "category": [
                ("GENERAL", "General"),
                ("OBC", "OBC"),
                ("SC", "SC"),
                ("ST", "ST"),
                ("EWS", "EWS"),
            ],
            "city": sorted({c for c in Student.objects.values_list("city", flat=True) if c}),
            "state": sorted({s for s in Student.objects.values_list("state", flat=True) if s}),
        }

    def get_table_columns(self):
        return [
            {"label": "ID", "attr": "student_id", "sort": "student_id"},
            {"label": "Name", "attr": "full_name", "sort": "name"},
            {"label": "Course", "attr": "course.name"},
            {"label": "Semester", "attr": "semester.number", "align": "center"},
            {"label": "Batch", "attr": "batch.name"},
            {"label": "Gender", "attr": "get_gender_display"},
            {"label": "Phone", "attr": "phone"},
            {"label": "Admission", "attr": "admission_date", "date": "d M Y", "sort": "admission_date"},
            {"label": "Status", "attr": "status", "badge": "status"},
        ]

    def get_table_actions(self):
        return {
            "detail": "students:student_detail",
            "edit": "students:student_edit",
            "delete": "students:student_delete",
            "extra": [
                {"url": "students:student_print", "label": "Profile", "icon": "bi-printer"},
                {"url": "students:student_id_card", "label": "ID card", "icon": "bi-person-badge"},
            ],
        }

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        params = self.request.GET
        context.update(
            {
                "filter_form": StudentFilterForm(params or None),
                "quick_search": params.get("q", ""),
                "total_students": Student.objects.count(),
                "active_count": Student.objects.filter(status=Student.Status.ACTIVE).count(),
                "inactive_count": Student.objects.exclude(status=Student.Status.ACTIVE).count(),
                "graduated_count": Student.objects.filter(status=Student.Status.GRADUATED).count(),
                "preserve_query": querystring_without_page(self.request),
                "selected_count": len(params.getlist("selected")),
            }
        )
        return context

    def get_export_rows(self, queryset=None):
        queryset = queryset if queryset is not None else self.get_queryset()
        headers = [
            "Student ID", "First Name", "Last Name", "Email", "Phone", "Gender", "DOB",
            "Blood Group", "Admission Date", "Department", "Course", "Semester", "Batch",
            "Status", "City", "State", "Pincode", "Guardian", "Guardian Phone",
        ]
        rows = [
            [
                obj.student_id,
                obj.first_name,
                obj.last_name,
                obj.email,
                obj.phone,
                obj.get_gender_display(),
                obj.date_of_birth.strftime("%Y-%m-%d") if obj.date_of_birth else "",
                obj.get_blood_group_display(),
                obj.admission_date.strftime("%Y-%m-%d") if obj.admission_date else "",
                obj.department.name if obj.department else "",
                obj.course.name if obj.course else "",
                str(obj.semester) if obj.semester else "",
                obj.batch.name if obj.batch else "",
                obj.get_status_display(),
                obj.city,
                obj.state,
                obj.pincode,
                obj.guardian_name,
                obj.guardian_phone,
            ]
            for obj in queryset
        ]
        return headers, rows


class StudentStatsView(StaffRequiredMixin, FilterableListView):
    """Aggregate breakdown shown above the student table."""

    model = Student
    template_name = "students/student_stats.html"
    list_title = "Student Statistics"

    def get_queryset(self):
        return Student.objects.with_details()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        queryset = self.get_queryset()
        context.update(
            {
                "by_department": list(
                    Department.objects.annotate(
                        total=Count("students", distinct=True),
                        active=Count(
                            "students",
                            distinct=True,
                            filter=Q(students__status=Student.Status.ACTIVE),
                        ),
                        male=Count(
                            "students", distinct=True, filter=Q(students__gender=Student.Gender.MALE)
                        ),
                        female=Count(
                            "students", distinct=True, filter=Q(students__gender=Student.Gender.FEMALE)
                        ),
                    )
                ),
                "by_course": list(
                    Course.objects.annotate(total=Count("students", distinct=True))
                ),
                "by_semester": list(
                    Semester.objects.annotate(total=Count("students", distinct=True))
                ),
                "by_status": list(
                    Student.objects.values("status")
                    .annotate(total=Count("id"))
                    .order_by("-total")
                ),
                "by_gender": list(
                    Student.objects.values("gender").annotate(total=Count("id"))
                ),
                "totals": {
                    "students": queryset.count(),
                    "male": queryset.filter(gender=Student.Gender.MALE).count(),
                    "female": queryset.filter(gender=Student.Gender.FEMALE).count(),
                    "other": queryset.filter(gender=Student.Gender.OTHER).count(),
                },
            }
        )
        return context

    def get_export_rows(self, queryset=None):
        headers = ["Department", "Total Students", "Active", "Male", "Female"]
        rows = []
        for item in Department.objects.annotate(
            total=Count("students", distinct=True),
            active=Count(
                "students", distinct=True, filter=Q(students__status=Student.Status.ACTIVE)
            ),
            male=Count(
                "students", distinct=True, filter=Q(students__gender=Student.Gender.MALE)
            ),
            female=Count(
                "students", distinct=True, filter=Q(students__gender=Student.Gender.FEMALE)
            ),
        ):
            rows.append([item.name, item.total, item.active, item.male, item.female])
        return headers, rows


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------
class StudentCreateView(StaffRequiredMixin, FormSuccessMixin, CreateView):
    model = Student
    form_class = StudentForm
    template_name = "students/student_form.html"
    success_url = reverse_lazy("students:student_list")
    created_message = "Student '%(object)s' created successfully."

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        response = super().form_valid(form)
        log_action(
            self.request,
            AuditLog.Action.CREATE,
            module="students",
            obj=self.object,
            description=f"Registered student {self.object.student_id} ({self.object.full_name})",
        )
        return response

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(
            {
                "page_title": "Add Student",
                "breadcrumb_parent": LIST_TITLE,
                "active_menu": "students",
                "form_title": "Add Student",
                "departments": Department.objects.filter(is_active=True),
                "courses": Course.objects.filter(is_active=True),
                "semesters": Semester.objects.all(),
                "batches": Batch.objects.filter(is_active=True),
            }
        )
        return context


class StudentUpdateView(StaffRequiredMixin, FormSuccessMixin, UpdateView):
    model = Student
    form_class = StudentForm
    template_name = "students/student_form.html"
    success_url = reverse_lazy("students:student_list")
    success_message = "Student '%(object)s' updated successfully."

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(
            {
                "page_title": f"Edit {self.object.full_name}",
                "breadcrumb_parent": LIST_TITLE,
                "active_menu": "students",
                "form_title": f"Edit Student: {self.object.full_name}",
                "departments": Department.objects.filter(is_active=True),
                "courses": Course.objects.filter(is_active=True),
                "semesters": Semester.objects.all(),
                "batches": Batch.objects.filter(is_active=True),
            }
        )
        return context


class StudentDeleteView(AdminRequiredMixin, ProtectedDeleteMixin, DeleteView):
    model = Student
    template_name = "students/student_confirm_delete.html"
    success_url = reverse_lazy("students:student_list")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(
            {
                "page_title": "Delete Student",
                "breadcrumb_parent": LIST_TITLE,
                "active_menu": "students",
                "attendance_count": self.object.attendance_records.count(),
                "marks_count": self.object.mark_entries.count(),
                "fee_count": self.object.fee_records.count(),
                "document_count": self.object.documents.count(),
            }
        )
        return context


class StudentDetailView(StaffRequiredMixin, DetailView):
    model = Student
    template_name = "students/student_detail.html"
    context_object_name = "student"

    def get_queryset(self):
        return Student.objects.select_related(
            "department", "course", "semester", "batch", "created_by"
        )

    def get_context_data(self, **kwargs):
        from students.services import student_notifications

        context = super().get_context_data(**kwargs)
        student = self.object
        context.update(
            {
                "page_title": student.full_name,
                "breadcrumb_parent": LIST_TITLE,
                "active_menu": "students",
                "profile": student_profile_context(student),
                "promotions": student.promotions.select_related(
                    "promoted_by", "to_semester", "to_course", "to_department"
                )[:10],
                "promotion_form": StudentPromotionForm(student=student),
                "document_form": StudentDocumentForm(student=student),
                "notifications": student_notifications(student),
                "promotion_history": StudentPromotion.objects.filter(student=student),
                "can_promote": self.request.user.can("promote_students"),
            }
        )
        log_action(
            self.request,
            AuditLog.Action.VIEW,
            module="students",
            obj=student,
            description=f"Viewed student profile {student.student_id}",
        )
        return context


@staff_required
@require_POST
def student_status_toggle(request, pk):
    student = get_object_or_404(Student, pk=pk)
    new_status = (
        Student.Status.INACTIVE
        if student.status == Student.Status.ACTIVE
        else Student.Status.ACTIVE
    )
    student.status = new_status
    student.save(update_fields=["status", "updated_at"])
    messages.success(
        request,
        f"{student.full_name} marked as {student.get_status_display().lower()}.",
    )
    log_action(
        request,
        AuditLog.Action.STATUS_CHANGE,
        module="students",
        obj=student,
        description=f"Status changed to {student.get_status_display()}",
    )
    return redirect(reverse("students:student_detail", args=[student.pk]))


# ---------------------------------------------------------------------------
# Bulk operations
# ---------------------------------------------------------------------------
@admin_required
@require_POST
def student_bulk_action(request):
    ids = request.POST.getlist("student_ids")
    action = request.POST.get("bulk_action", "")
    if not ids:
        messages.error(request, "Select at least one student first.")
        return redirect(reverse("students:student_list"))

    students = Student.objects.filter(pk__in=ids)
    count = students.count()

    if action == "delete":
        deleted, blocked = 0, []
        for student in students:
            try:
                student.delete()
                deleted += 1
            except Exception:
                blocked.append(student.student_id)
        if deleted:
            messages.success(request, f"{deleted} student record(s) deleted.")
        if blocked:
            messages.warning(
                request,
                f"Skipped {len(blocked)} student(s) with linked records: "
                f"{', '.join(blocked[:8])}{'...' if len(blocked) > 8 else ''}",
            )
        log_action(
            request,
            AuditLog.Action.DELETE,
            module="students",
            description=f"Bulk deleted {deleted} student record(s)",
        )
    elif action in {"activate", "deactivate", "graduate"}:
        status = {
            "activate": Student.Status.ACTIVE,
            "deactivate": Student.Status.INACTIVE,
            "graduate": Student.Status.GRADUATED,
        }[action]
        updated = students.update(status=status)
        messages.success(request, f"{updated} student(s) updated to {Student.Status(status).label}.")
        log_action(
            request,
            AuditLog.Action.STATUS_CHANGE,
            module="students",
            description=f"Bulk status update: {updated} student(s) -> {status}",
        )
    else:
        messages.error(request, "Unknown bulk action.")
    return redirect(reverse("students:student_list"))


@admin_required
@require_POST
def student_bulk_delete(request):
    ids = request.POST.getlist("student_ids")
    if not ids:
        messages.error(request, "Select at least one student first.")
        return redirect(reverse("students:student_list"))
    students = Student.objects.filter(pk__in=ids)
    deleted, blocked = 0, []
    for student in students:
        try:
            student.delete()
            deleted += 1
        except Exception:
            blocked.append(student.student_id)
    if deleted:
        messages.success(request, f"{deleted} student(s) deleted.")
    if blocked:
        messages.warning(
            request,
            f"{len(blocked)} student(s) could not be deleted because of linked records.",
        )
    log_action(
        request,
        AuditLog.Action.DELETE,
        module="students",
        description=f"Bulk delete: {deleted} deleted, {len(blocked)} skipped",
    )
    return redirect(reverse("students:student_list"))


# ---------------------------------------------------------------------------
# Promotion
# ---------------------------------------------------------------------------
@staff_required
@require_POST
def student_promote(request, pk):
    student = get_object_or_404(
        Student.objects.select_related("semester", "batch", "course", "department"), pk=pk
    )
    form = StudentPromotionForm(request.POST, student=student)
    if form.is_valid():
        promotion = promote_student(
            student,
            to_semester=form.cleaned_data.get("to_semester"),
            to_batch=form.cleaned_data.get("to_batch"),
            to_course=form.cleaned_data.get("to_course"),
            to_department=form.cleaned_data.get("to_department"),
            promotion_type=form.cleaned_data["promotion_type"],
            reason=form.cleaned_data.get("reason", ""),
            remarks=form.cleaned_data.get("remarks", ""),
            promoted_by=request.user,
            academic_year_from=form.cleaned_data.get("academic_year_from", ""),
            academic_year_to=form.cleaned_data.get("academic_year_to", ""),
        )
        messages.success(request, f"{student.full_name} promoted successfully: {promotion.summary}")
        log_action(
            request,
            AuditLog.Action.PROMOTE,
            module="students",
            obj=student,
            description=f"Promoted {student.full_name}: {promotion.summary}",
        )
    else:
        from core.utils import form_error_summary

        messages.error(request, "Promotion failed: " + form_error_summary(form))
    return redirect(reverse("students:student_detail", args=[student.pk]))


@staff_required
def promotion_history(request):
    queryset = (
        StudentPromotion.objects.select_related(
            "student", "promoted_by", "to_semester", "to_course", "to_department"
        )
        .all()
    )
    term = (request.GET.get("q") or "").strip()
    if term:
        queryset = queryset.filter(
            Q(student__student_id__icontains=term)
            | Q(student__first_name__icontains=term)
            | Q(student__last_name__icontains=term)
            | Q(reason__icontains=term)
        )
    promotion_type = request.GET.get("promotion_type")
    if promotion_type:
        queryset = queryset.filter(promotion_type=promotion_type)

    from core.utils import paginate

    page = paginate(request, queryset, 15)
    rows = [
        [
            item.student.student_id,
            item.student.full_name,
            item.get_promotion_type_display(),
            item.summary,
            item.academic_year_from,
            item.academic_year_to,
            item.reason,
            item.promoted_by.username if item.promoted_by else "",
            item.created_at.strftime("%Y-%m-%d %H:%M"),
        ]
        for item in page.object_list
    ]
    if request.GET.get("export"):
        from core.exports import export_data

        return export_data(
            request,
            "promotions",
            [
                "Student ID", "Student", "Type", "Change", "Academic Year From",
                "Academic Year To", "Reason", "Promoted By", "Date",
            ],
            rows,
            title="Student Promotion History",
        )
    return render(
        request,
        "students/promotion_history.html",
        {
            "promotions": page.object_list,
            "page_obj": page,
            "is_paginated": page.has_other_pages(),
            "page_title": "Promotion History",
            "breadcrumb_parent": "Students",
            "active_menu": "students",
            "search_term": term,
            "promotion_types": StudentPromotion._meta.get_field("promotion_type").choices,
            "selected_promotion_type": promotion_type or "",
        },
    )


# ---------------------------------------------------------------------------
# Documents
# ---------------------------------------------------------------------------
@staff_required
@require_POST
def student_document_upload(request, pk):
    student = get_object_or_404(Student, pk=pk)
    form = StudentDocumentForm(request.POST, request.FILES, student=student)
    if form.is_valid():
        document = form.save(commit=False)
        document.student = student
        document.uploaded_by = request.user
        document.save()
        messages.success(request, f"Document '{document.title}' uploaded successfully.")
        log_action(
            request,
            AuditLog.Action.UPLOAD,
            module="students",
            obj=document,
            description=f"Uploaded '{document.title}' for {student.full_name}",
        )
    else:
        from core.utils import form_error_summary

        messages.error(request, "Upload failed: " + form_error_summary(form))
    return redirect(f"{reverse('students:student_detail', args=[student.pk])}#documents")


@staff_required
def student_document_download(request, pk):
    document = get_object_or_404(StudentDocument, pk=pk)
    student_pk = document.student_id
    try:
        handle = document.file.open("rb")
    except (FileNotFoundError, ValueError):
        messages.error(request, "The stored file is missing from the server.")
        return redirect(reverse("students:student_detail", args=[student_pk]))
    filename = document.file.name.split("/")[-1]
    response = FileResponse(handle, as_attachment=True, filename=filename)
    log_action(
        request,
        AuditLog.Action.DOWNLOAD,
        module="students",
        obj=document,
        description=f"Downloaded '{document.title}'",
    )
    return response


@admin_required
@require_POST
def student_document_delete(request, pk):
    document = get_object_or_404(StudentDocument, pk=pk)
    student_pk = document.student_id
    title = document.title
    document.delete()
    messages.success(request, f"Document '{title}' deleted.")
    return redirect(f"{reverse('students:student_detail', args=[student_pk])}#documents")


# ---------------------------------------------------------------------------
# Print / ID card
# ---------------------------------------------------------------------------
@staff_required
@require_GET
def student_print(request, pk):
    student = get_object_or_404(
        Student.objects.select_related("department", "course", "semester", "batch"), pk=pk
    )
    log_action(
        request,
        AuditLog.Action.PRINT,
        module="students",
        obj=student,
        description=f"Printed profile of {student.full_name}",
    )
    return render(
        request,
        "students/student_print.html",
        {
            "student": student,
            "profile": student_profile_context(student),
            "page_title": f"{student.full_name} - Printable Profile",
            "generated_at": timezone.localtime(),
        },
    )


@staff_required
@require_GET
def student_id_card(request, pk):
    from core.models import SiteSetting

    student = get_object_or_404(
        Student.objects.select_related("department", "course", "semester", "batch"), pk=pk
    )
    settings_obj = SiteSetting.load()
    log_action(
        request,
        AuditLog.Action.PRINT,
        module="students",
        obj=student,
        description=f"Generated ID card for {student.full_name}",
    )
    return render(
        request,
        "students/student_id_card.html",
        {
            "student": student,
            "institute": settings_obj,
            "generated_at": timezone.localtime(),
            "page_title": f"ID Card - {student.full_name}",
        },
    )


@staff_required
@require_GET
def student_id_card_download(request, pk):
    """Return the ID card as a single page PDF (when reportlab is available)."""
    from core.exports import REPORTLAB_AVAILABLE

    student = get_object_or_404(Student, pk=pk)
    if not REPORTLAB_AVAILABLE:
        messages.error(
            request, "PDF generation needs the reportlab package: pip install reportlab"
        )
        return redirect(reverse("students:student_id_card", args=[student.pk]))
    pdf = build_id_card_pdf(student)
    response = HttpResponse(pdf, content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="id_card_{student.student_id}.pdf"'
    log_action(
        request,
        AuditLog.Action.DOWNLOAD,
        module="students",
        obj=student,
        description=f"Downloaded ID card PDF for {student.full_name}",
    )
    return response


def build_id_card_pdf(student):
    """Render a simple CR-80 sized PDF ID card (no external templates)."""
    import datetime as dt
    import io

    from reportlab.lib import colors
    from reportlab.lib.pagesizes import landscape
    from reportlab.lib.units import mm
    from reportlab.pdfgen import canvas

    from core.models import SiteSetting

    institute = SiteSetting.load()
    today = timezone.localdate()
    valid_until = today + dt.timedelta(days=365)
    width, height = 86 * mm, 54 * mm
    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=landscape((width, height)))
    pdf.setFillColor(colors.HexColor("#1f3c88"))
    pdf.rect(0, 0, width, height, stroke=0, fill=1)

    pdf.setFillColor(colors.white)
    pdf.rect(0, height - 14 * mm, width, 14 * mm, stroke=0, fill=1)
    pdf.setFillColor(colors.HexColor("#1f3c88"))
    pdf.setFont("Helvetica-Bold", 12)
    pdf.drawString(5 * mm, height - 9 * mm, institute.institute_name[:48])
    pdf.setFont("Helvetica", 7)
    pdf.drawString(
        5 * mm,
        6 * mm,
        f"{institute.institute_code} | {institute.phone} | {institute.email}"[:70],
    )

    text_x = 40 * mm
    pdf.setFont("Helvetica-Bold", 11)
    pdf.setFillColor(colors.white)
    pdf.drawString(text_x, height - 24 * mm, student.full_name[:26])
    pdf.setFont("Helvetica", 8)
    lines = [
        f"ID: {student.student_id}",
        f"Course: {student.course.name if student.course else '-'}",
        f"Department: {student.department.name if student.department else '-'}",
        f"Semester: {student.semester if student.semester else '-'} | "
        f"Batch: {student.batch.name if student.batch else '-'}",
        f"Phone: {student.phone}",
        f"Valid: {today:%d-%m-%Y} to {valid_until:%d-%m-%Y}",
    ]
    y = height - 30 * mm
    for line in lines:
        pdf.drawString(text_x, y, line[:48])
        y -= 4.6 * mm

    if student.photo:
        try:
            pdf.drawImage(
                student.photo.path,
                6 * mm,
                16 * mm,
                width=28 * mm,
                height=32 * mm,
                preserveAspectRatio=True,
                anchor="c",
            )
        except Exception:  # pragma: no cover - broken image file
            pass
    pdf.showPage()
    pdf.save()
    return buffer.getvalue()


# ---------------------------------------------------------------------------
# AJAX helpers
# ---------------------------------------------------------------------------
@staff_required
@require_GET
def student_filter_options(request):
    """JSON options used to build dependent dropdowns."""
    courses = Course.objects.filter(is_active=True)
    department_id = request.GET.get("department")
    if department_id:
        courses = courses.filter(department_id=department_id)
    data = {
        "courses": [{"id": c.pk, "label": c.name, "total_semesters": c.total_semesters} for c in courses],
        "semesters": [{"id": s.pk, "label": str(s)} for s in Semester.objects.all()],
        "batches": [{"id": b.pk, "label": b.name} for b in Batch.objects.filter(is_active=True)],
        "genders": [{"value": value, "label": label} for value, label in Student.Gender.choices],
        "statuses": [{"value": value, "label": label} for value, label in Student.Status.choices],
    }
    return JsonResponse(data)
