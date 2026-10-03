from django.urls import include, path
from rest_framework.routers import DefaultRouter

from students.api import (
    StudentDocumentViewSet,
    StudentPromotionViewSet,
    StudentStatisticsViewSet,
    StudentViewSet,
)

app_name = "students_api"

router = DefaultRouter()
router.register("students", StudentViewSet, basename="student")
router.register("documents", StudentDocumentViewSet, basename="student-document")
router.register("promotions", StudentPromotionViewSet, basename="student-promotion")
router.register("statistics", StudentStatisticsViewSet, basename="student-statistics")

urlpatterns = [path("", include(router.urls))]
