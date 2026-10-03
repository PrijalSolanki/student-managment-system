"""Authentication, profile and user management views."""

from __future__ import annotations

from django.contrib import messages
from django.contrib.auth import login, logout, update_session_auth_hash
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import LoginView
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.views.generic import CreateView, DeleteView, DetailView, UpdateView, View

from academics.models import Department
from accounts.forms import (
    LoginForm,
    RegistrationForm,
    StyledPasswordChangeForm,
    UserForm,
    UserProfileForm,
)
from accounts.models import User
from core.mixins import FilterableListView, FormSuccessMixin, ProtectedDeleteMixin
from core.models import AuditLog
from core.permissions import (
    AdminRequiredMixin,
    StaffRequiredMixin,
    log_action,
    staff_required,
)


class SMSLoginView(LoginView):
    template_name = "accounts/login.html"
    authentication_form = LoginForm
    redirect_authenticated_user = True

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = "Sign in"
        return context

    def form_valid(self, form):
        response = super().form_valid(form)
        if not form.get_user().is_internal_user:
            logout(self.request)
            messages.error(
                self.request,
                "This account is not authorised to use the management system.",
            )
            return redirect(reverse("accounts:login"))
        messages.success(self.request, f"Welcome back, {form.get_user().first_name or form.get_user().username}!")
        return response


def logout_view(request):
    logout(request)
    messages.info(request, "You have been signed out successfully.")
    return redirect(reverse("accounts:login"))


class RegisterView(CreateView):
    model = User
    form_class = RegistrationForm
    template_name = "accounts/register.html"
    success_url = reverse_lazy("accounts:login")

    def form_valid(self, form):
        user = form.save(commit=False)
        user.is_active = False  # requires administrator approval
        user.is_staff = False
        user.role = User.Role.STAFF
        user.save()
        log_action(
            self.request,
            AuditLog.Action.CREATE,
            module="accounts",
            obj=user,
            description=f"New registration request for '{user.username}' (pending approval)",
        )
        messages.success(
            self.request,
            "Registration submitted. An administrator must activate your account before you can sign in.",
        )
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = "Create account"
        return context


# ---------------------------------------------------------------------------
# Profile
# ---------------------------------------------------------------------------
class ProfileView(StaffRequiredMixin, DetailView):
    model = User
    template_name = "accounts/profile.html"
    context_object_name = "profile_user"

    def get_object(self, queryset=None):
        return self.request.user

    def get_context_data(self, **kwargs):
        from attendance.models import Attendance
        from fees.models import Payment
        from notifications.models import Notification

        context = super().get_context_data(**kwargs)
        user = self.request.user
        activity = AuditLog.objects.filter(user=user)[:10]
        context.update(
            {
                "page_title": "My Profile",
                "breadcrumb_parent": "Profile",
                "active_menu": "profile",
                "activity": activity,
                "permissions": _permission_summary(user),
                "notifications_sent": Notification.objects.filter(created_by=user).count(),
                "payments_recorded": Payment.objects.filter(received_by=user).count(),
                "attendance_marked": Attendance.objects.filter(marked_by=user).count(),
                "unread_notifications": Notification.objects.unread_for(user).count(),
            }
        )
        return context


def _permission_summary(user) -> list[str]:
    summary = []
    summary.append("Full administrative access" if user.is_admin else "Restricted (Staff) access")
    if user.can("delete_records"):
        summary.append("Can delete records")
    else:
        summary.append("Cannot delete records")
    summary.append("Can mark attendance")
    summary.append("Can record fee payments" if user.can("manage_fees") else "Can view fee records")
    summary.append("Can export reports")
    if user.can("manage_settings"):
        summary.append("Can change institute settings")
    return summary


class ProfileUpdateView(StaffRequiredMixin, FormSuccessMixin, UpdateView):
    form_class = UserProfileForm
    template_name = "accounts/profile_form.html"
    success_url = reverse_lazy("accounts:profile")
    success_message = "Profile updated successfully."

    def get_object(self, queryset=None):
        return self.request.user

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(
            {
                "page_title": "Edit Profile",
                "breadcrumb_parent": "Profile",
                "active_menu": "profile",
                "form_title": "Edit Profile",
            }
        )
        return context


class PasswordChangeView(StaffRequiredMixin, FormSuccessMixin, UpdateView):
    form_class = StyledPasswordChangeForm
    template_name = "accounts/password_change_form.html"
    success_url = reverse_lazy("accounts:password_change_done")
    success_message = "Password changed successfully."

    def get_object(self, queryset=None):
        return self.request.user

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    def form_valid(self, form):
        response = super().form_valid(form)
        update_session_auth_hash(self.request, form.user)
        log_action(
            self.request,
            AuditLog.Action.UPDATE,
            module="accounts",
            obj=self.request.user,
            description="Changed own password",
        )
        return response

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(
            {
                "page_title": "Change Password",
                "breadcrumb_parent": "Profile",
                "active_menu": "profile",
            }
        )
        return context


def password_change_done(request):
    return render(
        request,
        "accounts/password_change_done.html",
        {"page_title": "Password Updated", "active_menu": "profile"},
    )


# ---------------------------------------------------------------------------
# User administration
# ---------------------------------------------------------------------------
class UserListView(AdminRequiredMixin, FilterableListView):
    model = User
    template_name = "accounts/user_list.html"
    list_title = "Users"
    active_menu = "users"
    search_fields = ["username", "first_name", "last_name", "email", "phone"]
    filter_fields = ["role", "department", "is_active"]
    ordering_fields = {
        "username": "username",
        "-username": "-username",
        "role": "role",
        "newest": "-date_joined",
        "-date_joined": "-date_joined",
    }
    default_ordering = "-date_joined"
    paginate_by = 10

    def get_queryset(self):
        queryset = User.objects.select_related("department").annotate(
            login_count=Count("audit_logs", distinct=True)
        )
        return self.filter_queryset(queryset).order_by(self.get_ordering())

    def get_filter_choices(self):
        return {
            "role": User.Role.choices,
            "department": [(d.pk, d.name) for d in Department.objects.all()],
            "is_active": [("true", "Active"), ("false", "Inactive")],
        }

    def get_table_columns(self):
        return [
            {"label": "Username", "attr": "username", "sort": "username"},
            {"label": "Name", "attr": "display_name"},
            {"label": "Email", "attr": "email"},
            {"label": "Phone", "attr": "phone"},
            {"label": "Role", "attr": "role", "badge": "role"},
            {"label": "Department", "attr": "department.name"},
            {"label": "Active", "attr": "is_active", "bool": True},
            {"label": "Last login", "attr": "last_login", "datetime": "d M Y H:i"},
            {"label": "Joined", "attr": "date_joined", "date": "d M Y"},
        ]

    def get_table_actions(self):
        return {
            "detail": "accounts:user_detail",
            "edit": "accounts:user_edit",
            "delete": "accounts:user_delete",
        }

    def filter_queryset(self, queryset):
        queryset = super().filter_queryset(queryset)
        status = self.request.GET.get("is_active")
        if status in {"true", "false"}:
            queryset = queryset.filter(is_active=(status == "true"))
        return queryset

    def get_export_rows(self, queryset=None):
        queryset = queryset if queryset is not None else self.get_queryset()
        headers = ["Username", "First Name", "Last Name", "Email", "Phone", "Role", "Department", "Active", "Last Login", "Date Joined"]
        rows = [
            [u.username, u.first_name, u.last_name, u.email, u.phone, u.get_role_display(),
             u.department.name if u.department else "", "Yes" if u.is_active else "No",
             u.last_login.strftime("%Y-%m-%d %H:%M") if u.last_login else "", 
             u.date_joined.strftime("%Y-%m-%d")]
            for u in queryset
        ]
        return headers, rows


class UserDetailView(AdminRequiredMixin, DetailView):
    model = User
    template_name = "accounts/user_detail.html"
    context_object_name = "account_user"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.object
        context.update(
            {
                "page_title": user.username,
                "breadcrumb_parent": "Users",
                "active_menu": "users",
                "activity": AuditLog.objects.filter(user=user)[:15],
                "permissions": _permission_summary(user),
                "permissions_summary": _permission_summary(user),
            }
        )
        return context


class UserCreateView(AdminRequiredMixin, FormSuccessMixin, CreateView):
    model = User
    form_class = UserForm
    template_name = "accounts/user_form.html"
    success_url = reverse_lazy("accounts:user_list")
    created_message = "User account created successfully."

    def form_valid(self, form):
        response = super().form_valid(form)
        user = self.object
        user.is_staff = user.is_admin
        if not user.is_active:
            user.is_active = True
        user.save(update_fields=["is_staff", "is_active"])
        messages.info(self.request, f"{user.username} can now sign in to the system.")
        return response

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(
            {
                "page_title": "Add User",
                "breadcrumb_parent": "Users",
                "active_menu": "users",
                "form_title": "Add User",
            }
        )
        return context


class UserUpdateView(AdminRequiredMixin, FormSuccessMixin, UpdateView):
    model = User
    form_class = UserForm
    template_name = "accounts/user_form.html"
    success_url = reverse_lazy("accounts:user_list")
    success_message = "User account updated successfully."

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["instance"] = self.object
        return kwargs

    def form_valid(self, form):
        if self.object == self.request.user and self.object.is_superuser:
            form.instance.role = User.Role.ADMIN
            form.instance.is_active = True
        response = super().form_valid(form)
        self.object.is_staff = self.object.is_admin
        self.object.save(update_fields=["is_staff"])
        return response

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(
            {
                "page_title": f"Edit {self.object}",
                "breadcrumb_parent": "Users",
                "active_menu": "users",
                "form_title": f"Edit User: {self.object.username}",
                "editing_self": self.object == self.request.user,
            }
        )
        return context


class UserDeleteView(AdminRequiredMixin, ProtectedDeleteMixin, DeleteView):
    model = User
    template_name = "accounts/user_confirm_delete.html"
    success_url = reverse_lazy("accounts:user_list")

    def get_object(self, queryset=None):
        user = super().get_object(queryset)
        if user == self.request.user:
            from django.core.exceptions import PermissionDenied

            raise PermissionDenied("You cannot delete your own account.")
        if user.is_superuser:
            from django.core.exceptions import PermissionDenied

            raise PermissionDenied("Superuser accounts cannot be deleted.")
        return user

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(
            {
                "page_title": "Delete User",
                "breadcrumb_parent": "Users",
                "active_menu": "users",
            }
        )
        return context


class UserToggleActiveView(AdminRequiredMixin, View):
    model = User

    @require_POST
    def post(self, request, *args, **kwargs):
        user = get_object_or_404(User, pk=kwargs["pk"])
        if user == request.user:
            messages.error(request, "You cannot deactivate your own account.")
            return redirect("accounts:user_detail", pk=user.pk)
        user.is_active = not user.is_active
        user.save(update_fields=["is_active"])
        state = "activated" if user.is_active else "deactivated"
        messages.success(request, f"{user.username} has been {state}.")
        log_action(
            request,
            AuditLog.Action.STATUS_CHANGE,
            module="accounts",
            obj=user,
            description=f"User {state}",
        )
        return redirect("accounts:user_detail", pk=user.pk)


@staff_required
def my_activity(request):
    """Personal activity trail."""
    from core.utils import paginate

    queryset = AuditLog.objects.filter(user=request.user).select_related("user")
    page = paginate(request, queryset, 25)
    return render(
        request,
        "accounts/my_activity.html",
        {
            "logs": page.object_list,
            "page_obj": page,
            "is_paginated": page.has_other_pages(),
            "page_title": "My Activity",
            "breadcrumb_parent": "Profile",
            "active_menu": "profile",
        },
    )
