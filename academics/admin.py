from django.contrib import admin

from academics.models import Batch, Course, Department, Semester, Subject


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "hod", "is_active", "created_at")
    list_filter = ("is_active",)
    search_fields = ("name", "code", "hod")


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "department", "level", "duration_years", "is_active")
    list_filter = ("department", "level", "is_active")
    search_fields = ("name", "code")


@admin.register(Subject)
class SubjectAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "course", "semester", "credits", "is_active")
    list_filter = ("semester", "subject_type", "is_active", "course")
    search_fields = ("name", "code")


@admin.register(Semester)
class SemesterAdmin(admin.ModelAdmin):
    list_display = ("number", "name", "is_current")
    list_filter = ("is_current",)


@admin.register(Batch)
class BatchAdmin(admin.ModelAdmin):
    list_display = ("name", "start_year", "end_year", "department", "is_active")
    list_filter = ("department", "is_active")
