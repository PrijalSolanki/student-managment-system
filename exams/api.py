"""REST API for exams, mark entry and results."""

from __future__ import annotations

from django.db.models import Avg, Count, Q
from rest_framework import serializers, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from core.api_pagination import LargeResultsSetPagination
from core.api_permissions import IsAdminOrStaff
from core.models import AuditLog
from core.permissions import log_action
from exams.models import Exam, ExamSubject, MarkEntry, Result
from exams.services import GRADE_SCALE, calculate_grade, recalculate_exam_results, result_sheet


class ExamSubjectSerializer(serializers.ModelSerializer):
    subject_code = serializers.CharField(source="subject.code", read_only=True)
    subject_name = serializers.CharField(source="subject.name", read_only=True)
    pass_marks = serializers.FloatField(read_only=True)

    class Meta:
        model = ExamSubject
        fields = [
            "id",
            "exam",
            "subject",
            "subject_code",
            "subject_name",
            "max_marks",
            "pass_marks",
            "exam_date",
            "exam_time",
            "venue",
            "instructions",
        ]


class ExamSerializer(serializers.ModelSerializer):
    exam_type_display = serializers.CharField(source="get_exam_type_display", read_only=True)
    course_name = serializers.CharField(source="course.name", read_only=True)
    course_code = serializers.CharField(source="course.code", read_only=True)
    semester_name = serializers.CharField(source="semester.name", read_only=True)
    subject_count = serializers.IntegerField(read_only=True)
    result_count = serializers.IntegerField(read_only=True)
    subjects = ExamSubjectSerializer(many=True, read_only=True)

    class Meta:
        model = Exam
        fields = [
            "id",
            "name",
            "code",
            "exam_type",
            "exam_type_display",
            "course",
            "course_code",
            "course_name",
            "semester",
            "semester_name",
            "academic_year",
            "start_date",
            "end_date",
            "total_marks",
            "passing_marks",
            "passing_percentage",
            "is_published",
            "results_published",
            "allow_marks_entry",
            "description",
            "subject_count",
            "result_count",
            "subjects",
            "created_at",
        ]
        read_only_fields = ["total_marks", "passing_marks", "created_at"]

    def create(self, validated_data):
        request = self.context.get("request")
        validated_data["created_by"] = getattr(request, "user", None)
        return super().create(validated_data)


class MarkEntrySerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source="student.full_name", read_only=True)
    student_code = serializers.CharField(source="student.student_id", read_only=True)
    subject_code = serializers.CharField(source="exam_subject.subject.code", read_only=True)
    max_marks = serializers.DecimalField(source="exam_subject.max_marks", max_digits=7, decimal_places=2, read_only=True)
    percentage = serializers.FloatField(read_only=True)
    is_pass = serializers.BooleanField(read_only=True)

    class Meta:
        model = MarkEntry
        fields = [
            "id",
            "exam",
            "exam_subject",
            "student",
            "student_code",
            "student_name",
            "subject_code",
            "marks_obtained",
            "max_marks",
            "is_absent",
            "percentage",
            "is_pass",
            "remarks",
            "entered_by",
            "updated_at",
        ]
        read_only_fields = ["entered_by", "updated_at"]

    def validate(self, attrs):
        marks = attrs.get("marks_obtained")
        exam_subject = attrs.get("exam_subject") or getattr(self.instance, "exam_subject", None)
        if exam_subject and marks is not None and marks > exam_subject.max_marks:
            raise serializers.ValidationError(
                {"marks_obtained": f"Marks cannot exceed {exam_subject.max_marks}."}
            )
        return attrs


class ResultSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source="student.full_name", read_only=True)
    student_code = serializers.CharField(source="student.student_id", read_only=True)
    exam_code = serializers.CharField(source="exam.code", read_only=True)
    exam_name = serializers.CharField(source="exam.name", read_only=True)

    class Meta:
        model = Result
        fields = [
            "id",
            "exam",
            "exam_code",
            "exam_name",
            "student",
            "student_code",
            "student_name",
            "total_marks",
            "max_marks",
            "percentage",
            "grade",
            "grade_point",
            "is_pass",
            "failed_subjects",
            "absent_subjects",
            "published",
            "calculated_at",
        ]
        read_only_fields = [
            "total_marks",
            "max_marks",
            "percentage",
            "grade",
            "grade_point",
            "is_pass",
            "failed_subjects",
            "absent_subjects",
            "calculated_at",
        ]


class ExamViewSet(viewsets.ModelViewSet):
    queryset = Exam.objects.select_related("course", "semester").prefetch_related("exam_subjects")
    serializer_class = ExamSerializer
    permission_classes = [IsAdminOrStaff]
    pagination_class = LargeResultsSetPagination
    filterset_fields = ["course", "semester", "exam_type", "is_published", "results_published"]
    search_fields = ["name", "code", "academic_year"]
    ordering_fields = ["start_date", "end_date", "name", "created_at"]

    @action(detail=True, methods=["post"])
    def publish(self, request, pk=None):
        exam = self.get_object()
        exam.is_published = True
        exam.save(update_fields=["is_published", "updated_at"])
        log_action(
            request,
            AuditLog.Action.UPDATE,
            module="exams",
            obj=exam,
            description=f"Exam '{exam.code}' published via API",
        )
        return Response(self.get_serializer(exam).data)

    @action(detail=True, methods=["post"])
    def recalculate(self, request, pk=None):
        exam = self.get_object()
        summary = recalculate_exam_results(exam)
        log_action(
            request,
            AuditLog.Action.UPDATE,
            module="exams",
            obj=exam,
            description=f"Results recalculated via API: {summary}",
        )
        return Response(summary)

    @action(detail=False, methods=["get"])
    def grading_policy(self, request):
        return Response(
            {
                "scale": [
                    {
                        "grade": band["grade"],
                        "min_percentage": band["min"],
                        "point": float(band["point"]),
                        "description": band["description"],
                    }
                    for band in GRADE_SCALE
                ],
                "example": calculate_grade(78.5),
            }
        )


class MarkEntryViewSet(viewsets.ModelViewSet):
    queryset = MarkEntry.objects.select_related("exam", "exam_subject__subject", "student")
    serializer_class = MarkEntrySerializer
    permission_classes = [IsAdminOrStaff]
    pagination_class = LargeResultsSetPagination
    filterset_fields = ["exam", "exam_subject", "student", "is_absent"]
    search_fields = ["student__student_id", "student__first_name", "student__last_name"]

    def perform_create(self, serializer):
        serializer.save(entered_by=self.request.user)

    @action(detail=False, methods=["get"])
    def sheet(self, request):
        """Subject-wise marksheet rows for one exam/student pair."""
        from students.models import Student

        exam_id = request.query_params.get("exam")
        student_id = request.query_params.get("student")
        if not exam_id or not student_id:
            return Response({"detail": "Both 'exam' and 'student' are required."}, status=400)
        exam = Exam.objects.filter(pk=exam_id).first()
        student = Student.objects.filter(pk=student_id).first()
        if not exam or not student:
            return Response({"detail": "Exam or student not found."}, status=404)
        rows = result_sheet(exam, student)
        payload = [
            {
                "subject_code": row["subject"].code,
                "subject_name": row["subject"].name,
                "max_marks": row["max_marks"],
                "pass_marks": row["pass_marks"],
                "obtained": row["obtained"],
                "is_absent": row["is_absent"],
                "percentage": row["percentage"],
                "grade": row["grade"],
                "is_pass": row["is_pass"],
            }
            for row in rows
        ]
        return Response({"exam": exam.code, "student": student_id, "rows": payload})


class ResultViewSet(viewsets.ModelViewSet):
    queryset = Result.objects.select_related("exam", "student")
    serializer_class = ResultSerializer
    permission_classes = [IsAdminOrStaff]
    pagination_class = LargeResultsSetPagination
    filterset_fields = ["exam", "student", "grade", "is_pass"]
    search_fields = ["student__student_id", "student__first_name", "student__last_name"]
    ordering_fields = ["percentage", "grade_point", "calculated_at"]

    @action(detail=False, methods=["get"])
    def summary(self, request):
        queryset = self.filter_queryset(self.get_queryset())
        totals = queryset.aggregate(
            total=Count("id"),
            passed=Count("id", filter=Q(is_pass=True)),
            failed=Count("id", filter=Q(is_pass=False)),
            average=Avg("percentage"),
        )
        return Response(
            {
                **totals,
                "average_percentage": round(float(totals["average"] or 0), 2),
            }
        )