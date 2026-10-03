from django.urls import path

from attendance import views

app_name = "attendance"

urlpatterns = [
    path("", views.AttendanceListView.as_view(), name="attendance_list"),
    path("records/", views.AttendanceListView.as_view(), name="attendance_records"),
    path("records/export/", views.AttendanceListView.as_view(), name="attendance_export"),
    path("mark/", views.MarkAttendanceView.as_view(), name="mark"),
    path("<int:pk>/delete/", views.AttendanceDeleteView.as_view(), name="attendance_delete"),
    path("report/daily/", views.report_daily, name="report_daily"),
    path("report/monthly/", views.report_monthly, name="report_monthly"),
    path("report/student/", views.report_student, name="report_student"),
    path("report/subject/", views.report_subject, name="report_subject"),
]
