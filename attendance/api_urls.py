from django.urls import include, path
from rest_framework.routers import DefaultRouter

from attendance.api import AttendanceViewSet

app_name = "attendance_api"

router = DefaultRouter()
router.register("attendance", AttendanceViewSet, basename="attendance")

urlpatterns = [path("", include(router.urls))]
