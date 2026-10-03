from django.contrib import admin

from attendance.models import Attendance


@admin.register(Attendance)
class AttendanceAdmin(admin.ModelAdmin):
    list_display = ("date", "student", "subject", "teacher", "status", "marked_by")
    list_filter = ("status", "date", "subject")
    search_fields = ("student__student_id", "student__first_name", "student__last_name")
    date_hierarchy = "date"
