from django.urls import include, path
from rest_framework.routers import DefaultRouter

from accounts.api import CurrentUserViewSet, UserViewSet

app_name = "accounts_api"

router = DefaultRouter()
router.register("me", CurrentUserViewSet, basename="me")
router.register("users", UserViewSet, basename="user")

urlpatterns = [path("", include(router.urls))]
