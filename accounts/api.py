"""REST API for user accounts (read-only profile endpoint)."""

from __future__ import annotations

from rest_framework import serializers, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from accounts.models import User
from core.api_permissions import IsAdminUser


class UserSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(source="get_full_name", read_only=True)
    is_admin = serializers.BooleanField(read_only=True)

    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "full_name",
            "email",
            "phone",
            "role",
            "designation",
            "department",
            "is_admin",
            "is_active",
            "date_joined",
            "last_login",
        ]


class CurrentUserViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = UserSerializer

    def list(self, request):
        return Response(UserSerializer(request.user).data)

    @action(detail=False, methods=["get"], url_path="permissions")
    def permissions(self, request):
        user = request.user
        return Response(
            {
                "role": user.role,
                "is_admin": user.is_admin,
                "capabilities": {
                    "delete_records": user.can("delete_records"),
                    "manage_users": user.can("manage_users"),
                    "manage_settings": user.can("manage_settings"),
                    "mark_attendance": user.can("mark_attendance"),
                    "export_data": user.can("export_data"),
                },
                "model_permissions": sorted(user.get_all_permissions()),
            }
        )


class UserViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = User.objects.select_related("department").all()
    serializer_class = UserSerializer
    permission_classes = [IsAdminUser]
    filterset_fields = ["role", "is_active", "department"]
    search_fields = ["username", "first_name", "last_name", "email"]
    ordering_fields = ["username", "date_joined", "last_login"]
