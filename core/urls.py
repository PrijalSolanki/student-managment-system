from django.urls import path

from core import views

app_name = "core"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("dashboard/data/", views.dashboard_data, name="dashboard_data"),
    path("search/", views.global_search, name="global_search"),
    path("settings/", views.SiteSettingUpdateView.as_view(), name="settings"),
    path("audit-logs/", views.AuditLogListView.as_view(), name="audit_list"),
    path("audit-logs/<int:pk>/", views.AuditLogDetailView.as_view(), name="audit_detail"),
]
