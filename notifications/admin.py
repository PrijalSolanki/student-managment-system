from django.contrib import admin

from notifications.models import Notification, NotificationRead, StudentAnnouncement


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("title", "priority", "audience", "is_pinned", "is_active", "read_count", "created_by", "created_at")
    list_filter = ("priority", "audience", "is_pinned", "is_active")
    search_fields = ("title", "body")
    readonly_fields = ("read_count",)


@admin.register(NotificationRead)
class NotificationReadAdmin(admin.ModelAdmin):
    list_display = ("notification", "user", "read_at")
    list_filter = ("read_at",)


@admin.register(StudentAnnouncement)
class StudentAnnouncementAdmin(admin.ModelAdmin):
    list_display = ("student", "title", "created_by", "created_at")
    search_fields = ("title", "message", "student__student_id")