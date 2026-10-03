from django.urls import include, path
from rest_framework.routers import DefaultRouter

from core.api import AuditLogViewSet, SiteSettingViewSet, dashboard_statistics

app_name = "core_api"

router = DefaultRouter()
router.register("settings", SiteSettingViewSet, basename="site-setting")
router.register("audit-logs", AuditLogViewSet, basename="audit-log")

urlpatterns = [
    path("dashboard/", dashboard_statistics, name="dashboard-statistics"),
    path("", include(router.urls)),
]
