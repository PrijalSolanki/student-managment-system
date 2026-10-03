from django.urls import include, path
from rest_framework.routers import DefaultRouter

from academics.api import (
    BatchViewSet,
    CourseViewSet,
    DepartmentViewSet,
    SemesterViewSet,
    SubjectViewSet,
)

app_name = "academics_api"

router = DefaultRouter()
router.register("departments", DepartmentViewSet, basename="department")
router.register("courses", CourseViewSet, basename="course")
router.register("subjects", SubjectViewSet, basename="subject")
router.register("semesters", SemesterViewSet, basename="semester")
router.register("batches", BatchViewSet, basename="batch")

urlpatterns = [path("", include(router.urls))]
