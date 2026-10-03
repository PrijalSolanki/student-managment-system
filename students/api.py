"""REST API for students, documents and promotions."""

from __future__ import annotations

from django.db.models import Count
from rest_framework import serializers, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from core.api_pagination import LargeResultsSetPagination
from core.api_permissions import IsAdminUser, ReadOnlyForStaff
from students.models import Student, StudentDocument, StudentPromotion


class StudentSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(read_only=True)
    department_name = serializers.CharField(source="department.name", read_only=True)
    course_name = serializers.CharField(source="course.name", read_only=True)
    semester_number = serializers.IntegerField(source="semester.number", read_only=True)
    batch_name = serializers.CharField(source="batch.name", read_only=True)
    attendance_percentage = serializers.SerializerMethodField()
    photo_url = serializers.SerializerMethodField()

    class Meta:
        model = Student
        fields = [
            "id",
            "student_id",
            "first_name",
            "last_name",
            "full_name",
            "email",
            "phone",
            "gender",
            "date_of_birth",
            "blood_group",
            "category",
            "address",
            "city",
            "state",
            "pincode",
            "photo",
            "photo_url",
            "admission_date",
            "department",
            "department_name",
            "course",
            "course_name",
            "semester",
            "semester_number",
            "batch",
            "batch_name",
            "status",
            "guardian_name",
            "guardian_phone",
            "emergency_contact",
            "attendance_percentage",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["student_id", "created_at", "updated_at"]

    def get_attendance_percentage(self, obj):
        from students.services import student_attendance_summary

        return student_attendance_summary(obj)["percentage"]

    def get_photo_url(self, obj):
        if not obj.photo:
            return None
        request = self.context.get("request")
        url = obj.photo.url
        return request.build_absolute_uri(url) if request else url


class StudentListSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(read_only=True)
    department_name = serializers.CharField(source="department.name", read_only=True)
    course_name = serializers.CharField(source="course.name", read_only=True)

    class Meta:
        model = Student
        fields = [
            "id",
            "student_id",
            "full_name",
            "email",
            "phone",
            "gender",
            "department_name",
            "course_name",
            "status",
            "admission_date",
        ]


class StudentDocumentSerializer(serializers.ModelSerializer):
    document_url = serializers.SerializerMethodField()
    size_human = serializers.CharField(read_only=True)

    class Meta:
        model = StudentDocument
        fields = [
            "id",
            "student",
            "document_type",
            "title",
            "file",
            "document_url",
            "description",
            "file_size",
            "size_human",
            "is_verified",
            "uploaded_by",
            "created_at",
        ]
        read_only_fields = ["file_size", "uploaded_by", "created_at"]

    def get_document_url(self, obj):
        if not obj.file:
            return None
        request = self.context.get("request")
        url = obj.file.url
        return request.build_absolute_uri(url) if request else url


class StudentPromotionSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source="student.full_name", read_only=True)
    summary = serializers.CharField(read_only=True)
    promoted_by = serializers.CharField(source="promoted_by.username", read_only=True)

    class Meta:
        model = StudentPromotion
        fields = [
            "id",
            "student",
            "student_name",
            "promotion_type",
            "summary",
            "from_semester",
            "to_semester",
            "from_course",
            "to_course",
            "from_department",
            "to_department",
            "from_batch",
            "to_batch",
            "academic_year_from",
            "academic_year_to",
            "reason",
            "remarks",
            "promoted_by",
            "created_at",
        ]
        read_only_fields = ["created_at"]


class StudentViewSet(viewsets.ModelViewSet):
    """CRUD + filtering + search + statistics for students."""

    queryset = (
        Student.objects.select_related("department", "course", "semester", "batch")
        .all()
    )
    permission_classes = [ReadOnlyForStaff]
    pagination_class = LargeResultsSetPagination
    parser_classes = [JSONParser, FormParser, MultiPartParser]
    filterset_fields = [
        "department",
        "course",
        "semester",
        "batch",
        "gender",
        "status",
        "blood_group",
        "category",
    ]
    search_fields = ["student_id", "first_name", "last_name", "email", "phone"]
    ordering_fields = ["student_id", "first_name", "admission_date", "created_at"]

    def get_serializer_class(self):
        if self.action == "list":
            return StudentListSerializer
        return StudentSerializer

    @action(detail=True, methods=["get"])
    def attendance(self, request, pk=None):
        from students.services import student_attendance_summary

        student = self.get_object()
        return Response(student_attendance_summary(student))

    @action(detail=True, methods=["get"])
    def results(self, request, pk=None):
        from exams.models import Result

        student = self.get_object()
        data = Result.objects.filter(student=student).select_related("exam").values(
            "id",
            "exam__name",
            "total_marks",
            "max_marks",
            "percentage",
            "grade",
            "is_pass",
        )
        return Response(list(data))

    @action(detail=True, methods=["get"], url_path="fee-summary")
    def fee_summary(self, request, pk=None):
        from students.services import student_fee_summary

        return Response(student_fee_summary(self.get_object()))

    @action(detail=True, methods=["get"])
    def documents(self, request, pk=None):
        student = self.get_object()
        serializer = StudentDocumentSerializer(
            student.documents.all(), many=True, context={"request": request}
        )
        return Response(serializer.data)


class StudentDocumentViewSet(viewsets.ModelViewSet):
    queryset = StudentDocument.objects.select_related("student", "uploaded_by")
    serializer_class = StudentDocumentSerializer
    permission_classes = [IsAdminUser]
    parser_classes = [JSONParser, FormParser, MultiPartParser]
    filterset_fields = ["student", "document_type", "is_verified"]
    search_fields = ["title", "student__student_id", "student__first_name"]

    def perform_create(self, serializer):
        serializer.save(uploaded_by=self.request.user)


class StudentPromotionViewSet(viewsets.ModelViewSet):
    queryset = StudentPromotion.objects.select_related(
        "student", "promoted_by", "to_semester", "to_course"
    )
    serializer_class = StudentPromotionSerializer
    permission_classes = [IsAdminUser]
    filterset_fields = ["student", "promotion_type", "academic_year_to"]
    search_fields = ["student__student_id", "student__first_name", "student__last_name", "reason"]


class StudentStatisticsViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated]

    def list(self, request):
        queryset = Student.objects.all()
        department_id = request.query_params.get("department")
        if department_id:
            queryset = queryset.filter(department_id=department_id)
        return Response(
            {
                "total": queryset.count(),
                "by_department": list(
                    queryset.values("department__name")
                    .annotate(total=Count("id"))
                    .order_by("-total")
                ),
                "by_gender": list(queryset.values("gender").annotate(total=Count("id"))),
                "by_status": list(queryset.values("status").annotate(total=Count("id"))),
            }
        )
