"""REST API for teachers."""

from __future__ import annotations

from django.db.models import Count
from rest_framework import serializers, viewsets

from core.api_permissions import ReadOnlyForStaff
from teachers.models import Teacher


class TeacherSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(read_only=True)
    department_name = serializers.CharField(source="department.name", read_only=True)
    subject_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Teacher
        fields = [
            "id",
            "employee_id",
            "first_name",
            "last_name",
            "full_name",
            "email",
            "phone",
            "gender",
            "date_of_birth",
            "qualification",
            "designation",
            "department",
            "department_name",
            "joining_date",
            "salary",
            "status",
            "photo",
            "subject_count",
            "created_at",
        ]
        read_only_fields = ["employee_id", "created_at"]


class TeacherViewSet(viewsets.ModelViewSet):
    queryset = Teacher.objects.select_related("department").annotate(
        subject_count=Count("assignments", distinct=True)
    )
    serializer_class = TeacherSerializer
    permission_classes = [ReadOnlyForStaff]
    filterset_fields = ["department", "status", "gender", "designation"]
    search_fields = ["employee_id", "first_name", "last_name", "email", "phone"]
    ordering_fields = ["first_name", "employee_id", "salary", "joining_date", "created_at"]
