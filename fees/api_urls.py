from django.urls import include, path
from rest_framework.routers import DefaultRouter

from fees.api import FeeRecordViewSet, FeeStructureViewSet, FeeTypeViewSet, PaymentViewSet

app_name = "fees_api"

router = DefaultRouter()
router.register("fee-types", FeeTypeViewSet, basename="fee-type")
router.register("fee-structures", FeeStructureViewSet, basename="fee-structure")
router.register("invoices", FeeRecordViewSet, basename="fee-record")
router.register("payments", PaymentViewSet, basename="payment")

urlpatterns = [path("", include(router.urls))]