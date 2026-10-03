from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from accounts.models import User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ("username", "email", "first_name", "last_name", "role", "is_active", "date_joined")
    list_filter = ("role", "is_active", "is_staff", "department")
    search_fields = ("username", "first_name", "last_name", "email")
    ordering = ("-date_joined",)
    fieldsets = BaseUserAdmin.fieldsets + (
        ("Role & Profile", {"fields": ("role", "phone", "designation", "department", "date_of_birth", "address", "avatar")}),
    )
    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        ("Role & Profile", {"fields": ("role", "email", "phone", "designation", "department")}),
    )
