"""REST API for attendance."""

from __future__ import annotations

from django.db.models import Count, Q
from rest_framework import serializers, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from attendance.models import Attendance
from core.api_pagination import LargeResultsSetPagination
from core.api_permissions import IsAdminOrStaff
from core.utils import percent


class AttendanceSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source="student.full_name", read_only=True)
    student_code = serializers.CharField(source="student.student_id", read_only=True)
    subject_code = serializers.CharField(source="subject.code", read_only=True)
    subject_name = serializers.CharField(source="subject.name", read_only=True)
    teacher_name = serializers.CharField(source="teacher.full_name", read_only=True)
    marked_by = serializers.CharField(source="marked_by.username", read_only=True)

    class Meta:
        model = Attendance
        fields = [
            "id",
            "student",
            "student_code",
            "student_name",
            "subject",
            "subject_code",
            "subject_name",
            "teacher",
            "teacher_name",
            "date",
            "status",
            "remarks",
            "marked_by",
            "marked_at",
        ]
        read_only_fields = ["marked_at", "marked_by"]

    def validate(self, attrs):
        status = attrs.get("status")
        if status and status not in Attendance.Status.values:
            raise serializers.ValidationError({"status": f"Invalid status '{status}'."})
        return attrs


class BulkAttendanceSerializer(serializers.Serializer):
    """Mark attendance for many students in one request."""

    date = serializers.DateField()
    subject = serializers.PrimaryKeyRelatedField(queryset=None)
    teacher = serializers.PrimaryKeyRelatedField(queryset=None, required=False, allow_null=True)
    entries = serializers.ListField(
        child=serializers.ListField(child=serializers.IntegerField()), allow_empty=False
    )
    remarks = serializers.CharField(required=False, allow_blank=True, max_length=200)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from academics.models import Subject
        from teachers.models import Teacher

        self.fields["subject"].queryset = Subject.objects.all()
        self.fields["teacher"].queryset = Teacher.objects.all()


class AttendanceViewSet(viewsets.ModelViewSet):
    queryset = Attendance.objects.select_related("student", "subject", "teacher", "marked_by")
    serializer_class = AttendanceSerializer
    permission_classes = [IsAdminOrStaff]
    pagination_class = LargeResultsSetPagination
    filterset_fields = ["student", "subject", "teacher", "status", "date", "date__gte", "date__lte"]
    search_fields = ["student__student_id", "student__first_name", "subject__code"]
    ordering_fields = ["date", "status"]

    def perform_create(self, serializer):
        serializer.save(marked_by=self.request.user)

    @action(detail=False, methods=["post"], url_path="bulk-mark")
    def bulk_mark(self, request):
        payload = request.data.copy()
        entries = payload.pop("entries", [])
        if not isinstance(entries, list) or not entries:
            return Response({"detail": "No entries supplied."}, status=400)
        from attendance.services import save_bulk_attendance

        parsed = []
        for entry in entries:
            try:
                student_id, status = entry[0], entry[1]
            except (IndexError, TypeError):
                continue
            if status not in Attendance.Status.values:
                continue
            parsed.append(
                (
                    student_id,
                    status,
                    payload.get("subject"),
                    payload.get("teacher"),
                    payload.get("date"),
                    payload.get("remarks", ""),
                )
            )
        result = save_bulk_attendance(parsed, request.user)
        return Response(result)

    @action(detail=False, methods=["get"], url_path="daily-summary")
    def daily_summary(self, request):
        from django.utils import timezone

        from core.utils import parse_date

        date = parse_date(request.query_params.get("date")) or timezone.localdate()
        queryset = self.get_queryset().filter(date=date)
        totals = queryset.aggregate(
            total=Count("id"),
            present=Count("id", filter=Q(status=Attendance.Status.PRESENT)),
            absent=Count("id", filter=Q(status=Attendance.Status.ABSENT)),
            leave=Count("id", filter=Q(status=Attendance.Status.LEAVE)),
        )
        totals["percentage"] = percent(totals["present"], totals["total"])
        return Response({"date": str(date), **totals})
