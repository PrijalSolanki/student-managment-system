"""REST API for announcements."""

from __future__ import annotations

from django.db.models import Count
from rest_framework import serializers, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from core.api_pagination import LargeResultsSetPagination
from core.api_permissions import IsAdminOrStaff
from core.models import AuditLog
from core.permissions import log_action
from notifications.models import Notification, StudentAnnouncement
from notifications.services import broadcast, mark_all_read, unread_list


class NotificationSerializer(serializers.ModelSerializer):
    created_by = serializers.CharField(source="created_by.username", read_only=True)
    scope_label = serializers.CharField(read_only=True)
    is_read = serializers.SerializerMethodField()

    class Meta:
        model = Notification
        fields = [
            "id",
            "title",
            "body",
            "priority",
            "audience",
            "department",
            "course",
            "batch",
            "scope_label",
            "is_pinned",
            "is_active",
            "expires_at",
            "action_url",
            "attachment",
            "created_by",
            "read_count",
            "is_read",
            "created_at",
        ]
        read_only_fields = ["read_count", "created_at"]

    def get_is_read(self, obj):
        user = self.context.get("request").user if self.context.get("request") else None
        return obj.is_read_by(user) if user else False

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    def create(self, validated_data):
        notification = super().create(validated_data)
        copied = broadcast(notification)
        log_action(
            self.context.get("request"),
            AuditLog.Action.CREATE,
            module="notifications",
            obj=notification,
            description=f"Notification created via API ({copied} student profile(s))",
        )
        return notification


class StudentAnnouncementSerializer(serializers.ModelSerializer):
    student_code = serializers.CharField(source="student.student_id", read_only=True)
    student_name = serializers.CharField(source="student.full_name", read_only=True)

    class Meta:
        model = StudentAnnouncement
        fields = [
            "id",
            "student",
            "student_code",
            "student_name",
            "notification",
            "title",
            "message",
            "created_by",
            "created_at",
        ]
        read_only_fields = ["created_by", "created_at"]

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)


class NotificationViewSet(viewsets.ModelViewSet):
    queryset = Notification.objects.select_related("created_by", "department", "course", "batch")
    serializer_class = NotificationSerializer
    permission_classes = [IsAdminOrStaff]
    pagination_class = LargeResultsSetPagination
    filterset_fields = ["priority", "audience", "is_active", "is_pinned"]
    search_fields = ["title", "body"]
    ordering_fields = ["created_at", "priority", "read_count"]

    def get_queryset(self):
        queryset = super().get_queryset()
        if not (self.request.user.is_authenticated and self.request.user.is_admin):
            queryset = queryset.filter(is_active=True)
        return queryset

    @action(detail=True, methods=["post"])
    def mark_read(self, request, pk=None):
        notification = self.get_object()
        notification.mark_read(request.user)
        return Response(self.get_serializer(notification).data)

    @action(detail=False, methods=["post"])
    def mark_all_read(self, request):
        count = mark_all_read(request.user)
        return Response({"marked": count})

    @action(detail=False, methods=["get"])
    def unread(self, request):
        notifications = unread_list(request.user, limit=20)
        return Response(self.get_serializer(notifications, many=True).data)

    @action(detail=False, methods=["get"])
    def statistics(self, request):
        rows = (
            Notification.objects.values("priority")
            .annotate(total=Count("id"))
            .order_by("priority")
        )
        return Response(
            {
                "total": Notification.objects.count(),
                "active": Notification.objects.filter(is_active=True).count(),
                "by_priority": list(rows),
                "total_reads": Notification.objects.aggregate(total=Count("reads"))["total"] or 0,
            }
        )


class StudentAnnouncementViewSet(viewsets.ModelViewSet):
    queryset = StudentAnnouncement.objects.select_related("student")
    serializer_class = StudentAnnouncementSerializer
    permission_classes = [IsAdminOrStaff]
    pagination_class = LargeResultsSetPagination
    filterset_fields = ["student"]
    search_fields = ["title", "message", "student__student_id"]
    ordering_fields = ["created_at"]