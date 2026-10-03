"""Dashboard, settings, audit log and error handler views."""

from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.template import loader
from django.urls import reverse_lazy
from django.utils import timezone
from django.views.generic import DetailView, ListView, UpdateView
from django.views.decorators.http import require_GET

from core.forms import SiteSettingForm
from core.models import AuditLog, SiteSetting
from core.permissions import AdminRequiredMixin, StaffRequiredMixin, log_action, staff_required
from core.services import dashboard_charts, dashboard_stats


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------
@staff_required
@require_GET
def dashboard(request):
    from students.models import Student

    stats = dashboard_stats()
    recent_students = (
        Student.objects.select_related("department", "course", "semester")
        .order_by("-created_at", "-id")[:6]
    )
    latest_activity = AuditLog.objects.select_related("user")[:8]

    log_action(
        request,
        AuditLog.Action.VIEW,
        module="dashboard",
        description="Opened admin dashboard",
    )

    context = {
        "stats": stats,
        "recent_students": recent_students,
        "latest_activity": latest_activity,
        "upcoming_exams": _upcoming_exams(),
        "charts": dashboard_charts(stats),
        "page_title": "Dashboard",
        "breadcrumb_parent": None,
        "active_menu": "dashboard",
    }
    return render(request, "core/dashboard.html", context)


def _upcoming_exams(limit: int = 4):
    from exams.models import Exam

    today = timezone.localdate()
    return (
        Exam.objects.select_related("course", "semester")
        .filter(start_date__gte=today)
        .order_by("start_date")[:limit]
    )


@staff_required
@require_GET
def dashboard_data(request):
    """JSON endpoint powering the dashboard charts (Chart.js)."""
    stats = dashboard_stats()
    return JsonResponse({"stats": stats, "charts": dashboard_charts(stats)})


@staff_required
@require_GET
def global_search(request):
    """Quick search across students, teachers, courses and departments."""
    from academics.models import Course, Department, Subject
    from students.models import Student
    from teachers.models import Teacher

    query = (request.GET.get("q") or "").strip()
    results = {"students": [], "teachers": [], "courses": [], "departments": [], "subjects": []}
    if len(query) >= 2:
        results["students"] = list(
            Student.objects.select_related("course", "department").filter(
                Q(student_id__icontains=query)
                | Q(first_name__icontains=query)
                | Q(last_name__icontains=query)
                | Q(email__icontains=query)
                | Q(phone__icontains=query)
            )[:10]
        )
        results["teachers"] = list(
            Teacher.objects.select_related("department").filter(
                Q(employee_id__icontains=query)
                | Q(first_name__icontains=query)
                | Q(last_name__icontains=query)
                | Q(email__icontains=query)
                | Q(phone__icontains=query)
            )[:10]
        )
        results["courses"] = list(
            Course.objects.filter(
                Q(name__icontains=query) | Q(code__icontains=query)
            ).select_related("department")[:10]
        )
        results["departments"] = list(
            Department.objects.filter(
                Q(name__icontains=query) | Q(code__icontains=query)
            )[:10]
        )
        results["subjects"] = list(
            Subject.objects.filter(
                Q(name__icontains=query) | Q(code__icontains=query)
            ).select_related("course")[:10]
        )

    total = sum(len(value) for value in results.values())
    return render(
        request,
        "core/global_search.html",
        {
            "query": query,
            "results": results,
            "total": total,
            "page_title": f"Search results for '{query}'" if query else "Global Search",
        },
    )


# ---------------------------------------------------------------------------
# Site settings
# ---------------------------------------------------------------------------
class SiteSettingUpdateView(AdminRequiredMixin, UpdateView):
    model = SiteSetting
    form_class = SiteSettingForm
    template_name = "core/settings_form.html"
    success_url = reverse_lazy("core:settings")

    def get_object(self, queryset=None):
        return SiteSetting.load()

    def get_success_url(self):
        messages.success(self.request, "Institute settings updated successfully.")
        log_action(
            self.request,
            AuditLog.Action.UPDATE,
            module="settings",
            obj=self.object,
            description="Updated institute settings",
        )
        return str(self.success_url)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = "Settings"
        context["breadcrumb_parent"] = "Settings"
        context["active_menu"] = "settings"
        return context


# ---------------------------------------------------------------------------
# Audit logs
# ---------------------------------------------------------------------------
class AuditLogListView(StaffRequiredMixin, ListView):
    model = AuditLog
    template_name = "core/audit_list.html"
    context_object_name = "logs"
    paginate_by = 25

    def get_queryset(self):
        queryset = AuditLog.objects.select_related("user").all()
        params = self.request.GET
        search = (params.get("q") or "").strip()
        if search:
            queryset = queryset.filter(
                Q(record_repr__icontains=search)
                | Q(description__icontains=search)
                | Q(username_snapshot__icontains=search)
                | Q(record_id__icontains=search)
                | Q(module__icontains=search)
            )
        action = params.get("action")
        if action:
            queryset = queryset.filter(action=action)
        module = params.get("module")
        if module:
            queryset = queryset.filter(module=module)

        from core.utils import parse_date

        date_from = parse_date(params.get("date_from"))
        date_to = parse_date(params.get("date_to"))
        if date_from:
            queryset = queryset.filter(created_at__date__gte=date_from)
        if date_to:
            queryset = queryset.filter(created_at__date__lte=date_to)

        ordering = params.get("ordering") or "-created_at"
        allowed = {"-created_at", "created_at", "action", "module"}
        if ordering in allowed:
            queryset = queryset.order_by(ordering, "-id" if ordering == "created_at" else "id")
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        params = self.request.GET
        modules = list(
            AuditLog.objects.values_list("module", flat=True).distinct().order_by("module")
        )
        context.update(
            {
                "page_title": "Audit Logs",
                "breadcrumb_parent": "Audit Logs",
                "active_menu": "audit",
                "filters": params,
                "action_choices": AuditLog.Action.choices,
                "modules": modules,
                "today_count": AuditLog.objects.filter(
                    created_at__date=timezone.localdate()
                ).count(),
                "logins_today": AuditLog.objects.filter(
                    action__in=[AuditLog.Action.LOGIN, AuditLog.Action.LOGOUT],
                    created_at__date=timezone.localdate(),
                ).count(),
                "users_active": AuditLog.objects.values("username_snapshot")
                .distinct()
                .count(),
            }
        )
        return context


class AuditLogDetailView(StaffRequiredMixin, DetailView):
    model = AuditLog
    template_name = "core/audit_detail.html"
    context_object_name = "log"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = "Audit Log Detail"
        context["breadcrumb_parent"] = "Audit Logs"
        context["active_menu"] = "audit"
        return context


# ---------------------------------------------------------------------------
# Error handlers
# ---------------------------------------------------------------------------
def _render_error(request, status, title, message, template_name):
    context = {
        "status_code": status,
        "error_title": title,
        "error_message": message,
        "page_title": f"{status} - {title}",
    }
    try:
        return loader.render_to_string(template_name, context, request=request)
    except Exception:  # pragma: no cover - template must never break the handler
        return (
            f"<!doctype html><html><head><title>{status} {title}</title></head>"
            f"<body style='font-family:sans-serif;text-align:center;padding:60px'>"
            f"<h1>{status}</h1><h2>{title}</h2><p>{message}</p>"
            f"<p><a href='/'>Back to dashboard</a></p></body></html>"
        )


def error_400(request, exception=None):
    return HttpResponse(
        _render_error(
            request,
            400,
            "Bad Request",
            "The request could not be understood by the server. Please go back and try again.",
            "errors/400.html",
        ),
        status=400,
    )


def error_403(request, exception=None):
    return HttpResponse(
        _render_error(
            request,
            403,
            "Permission Denied",
            "You do not have permission to access this page. Contact an administrator "
            "if you believe this is a mistake.",
            "errors/403.html",
        ),
        status=403,
    )


def error_404(request, exception=None):
    return HttpResponse(
        _render_error(
            request,
            404,
            "Page Not Found",
            "The page you are looking for does not exist, was moved, or the link is broken.",
            "errors/404.html",
        ),
        status=404,
    )


def error_500(request):
    return HttpResponse(
        _render_error(
            request,
            500,
            "Internal Server Error",
            "Something went wrong on our side. The issue has been logged and the "
            "team has been notified. Please try again in a moment.",
            "errors/500.html",
        ),
        status=500,
    )


@login_required
def profile_redirect(request):
    return redirect("accounts:profile")
