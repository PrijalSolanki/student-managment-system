"""REST API for the core app (dashboard statistics + audit log)."""

from __future__ import annotations

from rest_framework import serializers, viewsets
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from core.api_permissions import IsAdminOrStaff, IsAdminUser
from core.models import AuditLog, SiteSetting
from core.services import dashboard_charts, dashboard_stats


class SiteSettingSerializer(serializers.ModelSerializer):
    class Meta:
        model = SiteSetting
        fields = [
            "institute_name",
            "institute_code",
            "address",
            "city",
            "state",
            "pincode",
            "phone",
            "email",
            "website",
            "logo",
            "academic_year",
            "current_semester",
            "pass_percentage",
            "attendance_shortage_percentage",
            "currency_symbol",
        ]


class AuditLogSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source="username_snapshot", read_only=True)
    action_display = serializers.CharField(source="get_action_display", read_only=True)

    class Meta:
        model = AuditLog
        fields = [
            "id",
            "created_at",
            "username",
            "action",
            "action_display",
            "module",
            "record_type",
            "record_id",
            "record_repr",
            "description",
            "changes",
            "ip_address",
            "path",
        ]


class SiteSettingViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [IsAdminOrStaff]
    serializer_class = SiteSettingSerializer

    def get_queryset(self):
        return SiteSetting.objects.all()


class AuditLogViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [IsAdminUser]
    serializer_class = AuditLogSerializer
    filterset_fields = ["action", "module", "user"]

    def get_queryset(self):
        return AuditLog.objects.select_related("user").all()


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def dashboard_statistics(request):
    """Aggregate dashboard numbers + chart data as JSON."""
    stats = dashboard_stats()
    return Response({"stats": stats, "charts": dashboard_charts(stats)})
