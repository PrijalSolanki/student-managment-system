"""REST API for academic master data."""

from __future__ import annotations

from django.db.models import Count
from rest_framework import serializers, viewsets

from academics.models import Batch, Course, Department, Semester, Subject
from core.api_pagination import StandardResultsSetPagination
from core.api_permissions import IsAdminOrStaff, ReadOnlyForStaff


class DepartmentSerializer(serializers.ModelSerializer):
    student_count = serializers.IntegerField(read_only=True)
    course_count = serializers.IntegerField(read_only=True)
    teacher_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Department
        fields = [
            "id",
            "code",
            "name",
            "hod",
            "email",
            "phone",
            "description",
            "established_year",
            "is_active",
            "student_count",
            "course_count",
            "teacher_count",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["created_at", "updated_at"]


class CourseSerializer(serializers.ModelSerializer):
    department_name = serializers.CharField(source="department.name", read_only=True)
    student_count = serializers.IntegerField(read_only=True)
    subject_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Course
        fields = [
            "id",
            "code",
            "name",
            "department",
            "department_name",
            "level",
            "duration_years",
            "total_semesters",
            "annual_fee",
            "eligibility",
            "description",
            "is_active",
            "student_count",
            "subject_count",
            "created_at",
        ]
        read_only_fields = ["created_at"]


class SubjectSerializer(serializers.ModelSerializer):
    course_name = serializers.CharField(source="course.name", read_only=True)
    semester_number = serializers.IntegerField(source="semester.number", read_only=True)
    teachers = serializers.SerializerMethodField()

    class Meta:
        model = Subject
        fields = [
            "id",
            "code",
            "name",
            "course",
            "course_name",
            "semester",
            "semester_number",
            "credits",
            "subject_type",
            "lecture_hours",
            "is_active",
            "teachers",
        ]

    def get_teachers(self, obj):
        return [teacher.full_name for teacher in obj.assigned_teachers]


class SemesterSerializer(serializers.ModelSerializer):
    class Meta:
        model = Semester
        fields = ["id", "number", "name", "is_current"]


class BatchSerializer(serializers.ModelSerializer):
    department_name = serializers.CharField(source="department.name", read_only=True)

    class Meta:
        model = Batch
        fields = [
            "id",
            "name",
            "start_year",
            "end_year",
            "department",
            "department_name",
            "is_active",
        ]


class DepartmentViewSet(viewsets.ModelViewSet):
    queryset = Department.objects.annotate(
        student_count=Count("students", distinct=True),
        course_count=Count("courses", distinct=True),
        teacher_count=Count("teachers", distinct=True),
    )
    serializer_class = DepartmentSerializer
    permission_classes = [ReadOnlyForStaff]
    pagination_class = StandardResultsSetPagination
    filterset_fields = ["is_active", "code"]
    search_fields = ["name", "code", "hod"]
    ordering_fields = ["name", "code", "created_at"]


class CourseViewSet(viewsets.ModelViewSet):
    queryset = Course.objects.select_related("department").annotate(
        student_count=Count("students", distinct=True),
        subject_count=Count("subjects", distinct=True),
    )
    serializer_class = CourseSerializer
    permission_classes = [ReadOnlyForStaff]
    pagination_class = StandardResultsSetPagination
    filterset_fields = ["department", "level", "is_active", "duration_years"]
    search_fields = ["name", "code", "department__name"]
    ordering_fields = ["name", "code", "annual_fee", "created_at"]


class SubjectViewSet(viewsets.ModelViewSet):
    queryset = Subject.objects.select_related("course", "semester")
    serializer_class = SubjectSerializer
    permission_classes = [ReadOnlyForStaff]
    pagination_class = StandardResultsSetPagination
    filterset_fields = ["course", "semester", "subject_type", "is_active"]
    search_fields = ["name", "code", "course__name"]
    ordering_fields = ["name", "code", "credits", "created_at"]


class SemesterViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Semester.objects.all()
    serializer_class = SemesterSerializer
    permission_classes = [IsAdminOrStaff]
    pagination_class = None
    filterset_fields = ["is_current"]


class BatchViewSet(viewsets.ModelViewSet):
    queryset = Batch.objects.select_related("department")
    serializer_class = BatchSerializer
    permission_classes = [ReadOnlyForStaff]
    pagination_class = StandardResultsSetPagination
    filterset_fields = ["department", "is_active", "start_year"]
    search_fields = ["name"]
