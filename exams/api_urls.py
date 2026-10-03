from django.urls import include, path
from rest_framework.routers import DefaultRouter

from exams.api import ExamViewSet, MarkEntryViewSet, ResultViewSet

app_name = "exams_api"

router = DefaultRouter()
router.register("exams", ExamViewSet, basename="exam")
router.register("marks", MarkEntryViewSet, basename="mark")
router.register("results", ResultViewSet, basename="result")

urlpatterns = [path("", include(router.urls))]