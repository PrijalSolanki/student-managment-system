from django.contrib import admin

from teachers.models import SubjectAssignment, Teacher


@admin.register(Teacher)
class TeacherAdmin(admin.ModelAdmin):
    list_display = ("employee_id", "first_name", "last_name", "department", "email", "status")
    list_filter = ("status", "department", "gender")
    search_fields = ("employee_id", "first_name", "last_name", "email")


@admin.register(SubjectAssignment)
class SubjectAssignmentAdmin(admin.ModelAdmin):
    list_display = ("teacher", "subject", "academic_year", "is_primary")
    list_filter = ("academic_year", "is_primary")
