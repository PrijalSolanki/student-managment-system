from django.contrib import admin

from exams.models import Exam, ExamSubject, MarkEntry, Result


class ExamSubjectInline(admin.TabularInline):
    model = ExamSubject
    extra = 1
    fields = ("subject", "max_marks", "exam_date", "exam_time", "venue")


@admin.register(Exam)
class ExamAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "exam_type", "course", "semester", "start_date", "end_date", "is_published", "results_published")
    list_filter = ("exam_type", "is_published", "results_published", "course", "semester")
    search_fields = ("code", "name", "academic_year")
    date_hierarchy = "start_date"
    inlines = [ExamSubjectInline]


@admin.register(ExamSubject)
class ExamSubjectAdmin(admin.ModelAdmin):
    list_display = ("exam", "subject", "max_marks", "exam_date", "venue")
    list_filter = ("exam",)


@admin.register(MarkEntry)
class MarkEntryAdmin(admin.ModelAdmin):
    list_display = ("exam", "exam_subject", "student", "marks_obtained", "is_absent", "entered_by", "updated_at")
    list_filter = ("exam", "is_absent", "exam_subject")
    search_fields = ("student__student_id", "student__first_name", "student__last_name")


@admin.register(Result)
class ResultAdmin(admin.ModelAdmin):
    list_display = ("exam", "student", "total_marks", "max_marks", "percentage", "grade", "is_pass", "published")
    list_filter = ("grade", "is_pass", "published", "exam")
    search_fields = ("student__student_id", "student__first_name", "student__last_name")
    readonly_fields = ("calculated_at",)