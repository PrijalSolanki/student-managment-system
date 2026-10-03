from django.urls import include, path
from rest_framework.routers import DefaultRouter

from notifications.api import NotificationViewSet, StudentAnnouncementViewSet

app_name = "notifications_api"

router = DefaultRouter()
router.register("notifications", NotificationViewSet, basename="notification")
router.register("student-announcements", StudentAnnouncementViewSet, basename="student-announcement")

urlpatterns = [path("", include(router.urls))]