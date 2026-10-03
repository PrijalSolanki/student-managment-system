from django.contrib import admin

from students.models import Student, StudentDocument, StudentPromotion


@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = ("student_id", "first_name", "last_name", "department", "course", "semester", "status")
    list_filter = ("status", "gender", "department", "course", "semester")
    search_fields = ("student_id", "first_name", "last_name", "email", "phone")
    ordering = ("student_id",)


@admin.register(StudentPromotion)
class StudentPromotionAdmin(admin.ModelAdmin):
    list_display = ("student", "promotion_type", "to_semester", "to_course", "promoted_by", "created_at")
    list_filter = ("promotion_type",)
    search_fields = ("student__student_id", "student__first_name", "student__last_name")


@admin.register(StudentDocument)
class StudentDocumentAdmin(admin.ModelAdmin):
    list_display = ("title", "student", "document_type", "is_verified", "created_at")
    list_filter = ("document_type", "is_verified")
