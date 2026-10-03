from django.urls import path

from notifications import views

app_name = "notifications"

urlpatterns = [
    path("", views.NotificationListView.as_view(), name="notification_list"),
    path("export/", views.NotificationListView.as_view(), name="notification_export"),
    path("add/", views.NotificationCreateView.as_view(), name="notification_add"),
    path("<int:pk>/", views.NotificationDetailView.as_view(), name="notification_detail"),
    path("<int:pk>/edit/", views.NotificationUpdateView.as_view(), name="notification_edit"),
    path("<int:pk>/delete/", views.NotificationDeleteView.as_view(), name="notification_delete"),
    path("<int:pk>/toggle/", views.notification_toggle_active, name="notification_toggle_active"),
    path("<int:pk>/pin/", views.notification_toggle_pin, name="notification_toggle_pin"),
    path("<int:pk>/preview/", views.notification_broadcast_preview, name="notification_broadcast_preview"),
    path("inbox/", views.notification_inbox, name="notification_inbox"),
    path("mark-all-read/", views.notifications_mark_all_read, name="notifications_mark_all_read"),
    path("student-notices/", views.StudentAnnouncementListView.as_view(), name="student_announcement_list"),
    path("student-notices/export/", views.StudentAnnouncementListView.as_view(), name="student_announcement_export"),
    path("student-notices/add/", views.StudentAnnouncementCreateView.as_view(), name="student_announcement_add"),
    path("student-notices/<int:pk>/delete/", views.StudentAnnouncementDeleteView.as_view(), name="student_announcement_delete"),
    path("reports/stats/", views.notification_stats, name="notification_stats"),
]