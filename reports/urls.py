from django.urls import path

from reports import views

app_name = "reports"

urlpatterns = [
    path("", views.report_index, name="report_index"),
    path("enrollment/", views.enrollment_report, name="enrollment_report"),
    path("attendance/", views.attendance_report, name="attendance_report"),
    path("attendance/defaulters/", views.defaulters_report, name="defaulters_report"),
    path("performance/", views.performance_report, name="performance_report"),
    path("fees/", views.fee_report, name="fee_report"),
    path("teachers/", views.teacher_report, name="teacher_report"),
    path("overview/", views.overview_report, name="overview_report"),
]