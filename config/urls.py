"""Root URL configuration."""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

admin.site.site_header = f"{settings.SMS['INSTITUTE_NAME']} Administration"
admin.site.site_title = "SMS Admin"
admin.site.index_title = "Student Management System"

urlpatterns = [
    path("django-admin/", admin.site.urls),
    path("accounts/", include("accounts.urls")),
    path("students/", include("students.urls")),
    path("teachers/", include("teachers.urls")),
    path("academics/", include("academics.urls")),
    path("attendance/", include("attendance.urls")),
    path("exams/", include("exams.urls")),
    path("fees/", include("fees.urls")),
    path("notifications/", include("notifications.urls")),
    path("reports/", include("reports.urls")),
    # REST API
    path("api/auth/", include("rest_framework.urls", namespace="rest_auth")),
    path("api/", include("accounts.api_urls")),
    path("api/students/", include("students.api_urls")),
    path("api/teachers/", include("teachers.api_urls")),
    path("api/academics/", include("academics.api_urls")),
    path("api/attendance/", include("attendance.api_urls")),
    path("api/exams/", include("exams.api_urls")),
    path("api/fees/", include("fees.api_urls")),
    path("api/notifications/", include("notifications.api_urls")),
    path("api/core/", include("core.api_urls")),
    # Dashboard / shared modules (must be last: it owns the root route).
    path("", include("core.urls")),
]

if settings.DEBUG:  # pragma: no cover
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

# Friendly error handlers -------------------------------------------------
handler400 = "core.views.error_400"
handler403 = "core.views.error_403"
handler404 = "core.views.error_404"
handler500 = "core.views.error_500"
