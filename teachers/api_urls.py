from django.urls import include, path
from rest_framework.routers import DefaultRouter

from teachers.api import TeacherViewSet

app_name = "teachers_api"

router = DefaultRouter()
router.register("teachers", TeacherViewSet, basename="teacher")

urlpatterns = [path("", include(router.urls))]
