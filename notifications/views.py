from django.contrib import messages
from django.db.models import Count
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST
from django.views.generic import CreateView, DeleteView, DetailView, UpdateView

from core.mixins import FilterableListView, FormSuccessMixin, ProtectedDeleteMixin
from core.models import AuditLog
from core.permissions import StaffRequiredMixin, log_action, staff_required
from notifications.forms import (
    NotificationFilterForm,
    NotificationForm,
    StudentAnnouncementForm,
)
from notifications.models import Notification, StudentAnnouncement
from notifications.services import (
    broadcast,
    expiring_soon,
    mark_all_read,
    read_history,
    unread_list,
)
from students.models import Student


class NotificationListView(StaffRequiredMixin, FilterableListView):
    model = Notification
    template_name = "notifications/notification_list.html"
    context_object_name = "notifications"
    list_title = "Notifications"
    active_menu = "notifications"
    module_name = "notifications"
    search_fields = ["title", "body"]
    filter_fields = ["priority", "audience"]
    ordering_fields = {
        "title": "title",
        "priority": "priority",
        "read": "-read_count",
        "created": "-created_at",
    }
    default_ordering = "-created_at"

    def get_queryset(self):
        queryset = Notification.objects.select_related("created_by", "department", "course", "batch")
        queryset = self.filter_queryset(queryset)
        active = (self.request.GET.get("is_active") or "").strip()
        if active == "true":
            queryset = queryset.filter(is_active=True)
        elif active == "false":
            queryset = queryset.filter(is_active=False)
        if (self.request.GET.get("is_pinned") or "").lower() in {"on", "1", "true"}:
            queryset = queryset.filter(is_pinned=True)
        return queryset.order_by("-is_pinned", self.get_ordering())

    def get_filter_choices(self):
        return {
            "priority": list(Notification.Priority.choices),
            "audience": list(Notification.Audience.choices),
        }

    def get_table_columns(self):
        return [
            {"label": "Title", "attr": "title", "sort": "title"},
            {"label": "Priority", "attr": "priority", "badge": "badge"},
            {"label": "Audience", "attr": "get_audience_display"},
            {"label": "Scope", "attr": "scope_label"},
            {"label": "Pinned", "attr": "is_pinned", "bool": True},
            {"label": "Active", "attr": "is_active", "bool": True},
            {"label": "Reads", "attr": "read_count", "align": "center", "sort": "read"},
            {"label": "Expires", "attr": "expires_at", "date": "d M Y"},
            {"label": "Created", "attr": "created_at", "datetime": "d M Y H:i", "sort": "created"},
        ]

    def get_table_actions(self):
        return {
            "detail": "notifications:notification_detail",
            "edit": "notifications:notification_edit",
            "delete": "notifications:notification_delete",
            "extra": [
                {
                    "url": "notifications:notification_broadcast_preview",
                    "label": "Audience preview",
                    "icon": "bi-people",
                }
            ],
        }

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        unread = Notification.objects.unread_for(self.request.user)
        context.update(
            {
                "filter_form": NotificationFilterForm(self.request.GET or None),
                "unread_total": unread.count(),
                "unread_list": unread_list(self.request.user),
                "active_total": Notification.objects.filter(is_active=True).count(),
                "pinned_total": Notification.objects.filter(is_pinned=True).count(),
                "expiring": expiring_soon(),
            }
        )
        return context

    def get_export_rows(self, queryset=None):
        queryset = queryset if queryset is not None else self.get_queryset()
        headers = ["Title", "Priority", "Audience", "Scope", "Pinned", "Active", "Reads", "Created By", "Created"]
        rows = [
            [
                item.title,
                item.get_priority_display(),
                item.get_audience_display(),
                item.scope_label,
                "Yes" if item.is_pinned else "No",
                "Yes" if item.is_active else "No",
                item.read_count,
                item.created_by.username if item.created_by else "-",
                item.created_at,
            ]
            for item in queryset
        ]
        return headers, rows


class NotificationCreateView(StaffRequiredMixin, FormSuccessMixin, CreateView):
    model = Notification
    form_class = NotificationForm
    template_name = "notifications/notification_form.html"
    success_url = "/notifications/"

    def form_valid(self, form):
        self.object = form.save(commit=False)
        self.object.created_by = self.request.user
        self.object.save()
        copied = broadcast(self.object)
        log_action(
            self.request,
            AuditLog.Action.CREATE,
            module="notifications",
            obj=self.object,
            description=f"Notification '{self.object.title}' published ({copied} student profile(s))",
        )
        if copied:
            messages.success(
                self.request,
                f"Notification published and pinned to {copied} student profile(s).",
            )
        return redirect(self.get_success_url())


class NotificationUpdateView(StaffRequiredMixin, FormSuccessMixin, UpdateView):
    model = Notification
    form_class = NotificationForm
    template_name = "notifications/notification_form.html"
    success_url = "/notifications/"


class NotificationDetailView(StaffRequiredMixin, DetailView):
    model = Notification
    template_name = "notifications/notification_detail.html"
    context_object_name = "notification"

    def get_queryset(self):
        return Notification.objects.select_related("created_by", "department", "course", "batch")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        self.object.mark_read(self.request.user)
        context.update(
            {
                "page_title": self.object.title,
                "active_menu": "notifications",
                "readers": self.object.reads.select_related("user")[:20],
                "pinned_students": self.object.student_announcements.count(),
            }
        )
        return context


class NotificationDeleteView(StaffRequiredMixin, ProtectedDeleteMixin, DeleteView):
    model = Notification
    template_name = "notifications/confirm_delete.html"
    success_url = "/notifications/"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(
            {
                "page_title": f"Delete {self.object.title}",
                "breadcrumb_parent": "Notifications",
                "blocking_reason": (
                    f"{self.object.reads.count()} read receipt(s) and "
                    f"{self.object.student_announcements.count()} student profile(s) reference this notice."
                ),
            }
        )
        return context


@staff_required
@require_POST
def notification_toggle_active(request, pk):
    notification = get_object_or_404(Notification, pk=pk)
    notification.is_active = not notification.is_active
    notification.save(update_fields=["is_active", "updated_at"])
    log_action(
        request,
        AuditLog.Action.UPDATE,
        module="notifications",
        obj=notification,
        description=f"Notification '{notification.title}' {'activated' if notification.is_active else 'deactivated'}",
    )
    messages.success(
        request,
        f"Notification {'activated' if notification.is_active else 'deactivated'}.",
    )
    return redirect("notifications:notification_list")


@staff_required
@require_POST
def notification_toggle_pin(request, pk):
    notification = get_object_or_404(Notification, pk=pk)
    notification.is_pinned = not notification.is_pinned
    notification.save(update_fields=["is_pinned", "updated_at"])
    messages.success(
        request,
        f"Notification {'pinned to top' if notification.is_pinned else 'unpinned'}.",
    )
    return redirect("notifications:notification_list")


@staff_required
@require_POST
def notifications_mark_all_read(request):
    count = mark_all_read(request.user)
    log_action(
        request,
        AuditLog.Action.UPDATE,
        module="notifications",
        description=f"Marked {count} notification(s) as read",
    )
    messages.success(request, f"Marked {count} notification(s) as read.")
    return redirect(request.POST.get("next") or "notifications:notification_list")


class StudentAnnouncementListView(StaffRequiredMixin, FilterableListView):
    model = StudentAnnouncement
    template_name = "notifications/student_announcement_list.html"
    context_object_name = "announcements"
    list_title = "Student Notices"
    active_menu = "notifications"
    breadcrumb_parent = "Notifications"
    module_name = "student_notices"
    search_fields = ["title", "message", "student__first_name", "student__last_name", "student__student_id"]
    filter_fields = ["student"]
    filter_lookups = {"student": "student_id"}
    ordering_fields = {"student": "student__student_id", "created": "-created_at"}
    default_ordering = "-created_at"

    def get_queryset(self):
        queryset = StudentAnnouncement.objects.select_related("student", "created_by")
        return self.filter_queryset(queryset).order_by(self.get_ordering())

    def get_table_columns(self):
        return [
            {"label": "Student ID", "attr": "student.student_id", "sort": "student"},
            {"label": "Student", "attr": "student.full_name"},
            {"label": "Title", "attr": "title"},
            {"label": "Message", "attr": "message"},
            {"label": "Sent by", "attr": "created_by.username"},
            {"label": "Created", "attr": "created_at", "datetime": "d M Y H:i", "sort": "created"},
        ]

    def get_table_actions(self):
        return {
            "delete": "notifications:student_announcement_delete",
        }

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({"total_notices": StudentAnnouncement.objects.count()})
        return context

    def get_export_rows(self, queryset=None):
        queryset = queryset if queryset is not None else self.get_queryset()
        headers = ["Student ID", "Student", "Title", "Message", "Sent By", "Created"]
        rows = [
            [
                item.student.student_id,
                item.student.full_name,
                item.title,
                item.message,
                item.created_by.username if item.created_by else "-",
                item.created_at,
            ]
            for item in queryset
        ]
        return headers, rows


class StudentAnnouncementCreateView(StaffRequiredMixin, FormSuccessMixin, CreateView):
    model = StudentAnnouncement
    form_class = StudentAnnouncementForm
    template_name = "notifications/student_announcement_form.html"
    success_url = "/notifications/student-notices/"

    def form_valid(self, form):
        self.object = form.save(commit=False)
        self.object.created_by = self.request.user
        self.object.save()
        log_action(
            self.request,
            AuditLog.Action.CREATE,
            module="notifications",
            obj=self.object,
            description=f"Notice '{self.object.title}' sent to {self.object.student.full_name}",
        )
        return redirect(self.get_success_url())


class StudentAnnouncementDeleteView(StaffRequiredMixin, ProtectedDeleteMixin, DeleteView):
    model = StudentAnnouncement
    template_name = "notifications/confirm_delete.html"
    success_url = "/notifications/student-notices/"


@staff_required
def notification_inbox(request):
    """Personal inbox: unread first, then history."""
    unread = unread_list(request.user, limit=20)
    history = read_history(request.user, limit=30)
    return render(
        request,
        "notifications/inbox.html",
        {
            "unread": unread,
            "history": history,
            "unread_total": Notification.objects.unread_for(request.user).count(),
            "page_title": "My Inbox",
            "active_menu": "notifications",
        },
    )


@staff_required
def notification_broadcast_preview(request, pk):
    """Preview how many student profiles a notice will reach."""
    notification = get_object_or_404(Notification, pk=pk)
    queryset = Student.objects.filter(status=Student.Status.ACTIVE)
    if notification.audience == Notification.Audience.COURSE:
        queryset = queryset.filter(course_id=notification.course_id)
    elif notification.audience == Notification.Audience.DEPARTMENT:
        queryset = queryset.filter(department_id=notification.department_id)
    elif notification.audience == Notification.Audience.BATCH:
        queryset = queryset.filter(batch_id=notification.batch_id)
    return render(
        request,
        "notifications/broadcast_preview.html",
        {
            "notification": notification,
            "students": queryset.count(),
            "page_title": "Broadcast Preview",
            "active_menu": "notifications",
        },
    )


@staff_required
def notification_stats(request):
    counts = (
        Notification.objects.values("priority")
        .annotate(total=Count("id"))
        .order_by("priority")
    )
    return render(
        request,
        "notifications/stats.html",
        {
            "priority_rows": [
                {
                    "priority": row["priority"],
                    "label": dict(Notification.Priority.choices).get(row["priority"], row["priority"]),
                    "total": row["total"],
                }
                for row in counts
            ],
            "total": Notification.objects.count(),
            "active": Notification.objects.filter(is_active=True).count(),
            "reads": Notification.objects.aggregate(total=Count("reads"))["total"] or 0,
            "page_title": "Notification Report",
            "active_menu": "reports",
        },
    )


__all__ = [
    "NotificationListView",
    "NotificationCreateView",
    "NotificationUpdateView",
    "NotificationDetailView",
    "NotificationDeleteView",
    "notification_toggle_active",
    "notification_toggle_pin",
    "notifications_mark_all_read",
    "StudentAnnouncementListView",
    "StudentAnnouncementCreateView",
    "StudentAnnouncementDeleteView",
    "notification_inbox",
    "notification_broadcast_preview",
    "notification_stats",
]