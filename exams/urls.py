from django.urls import path

from exams import views

app_name = "exams"

urlpatterns = [
    path("", views.ExamListView.as_view(), name="exam_list"),
    path("export/", views.ExamListView.as_view(), name="exam_export"),
    path("add/", views.ExamCreateView.as_view(), name="exam_add"),
    path("<int:pk>/", views.ExamDetailView.as_view(), name="exam_detail"),
    path("<int:pk>/edit/", views.ExamUpdateView.as_view(), name="exam_edit"),
    path("<int:pk>/delete/", views.ExamDeleteView.as_view(), name="exam_delete"),
    path("<int:pk>/publish/", views.exam_publish_toggle, name="exam_publish_toggle"),
    path("<int:pk>/recalculate/", views.exam_recalculate, name="exam_recalculate"),
    path("<int:pk>/results-publish/", views.exam_results_publish, name="exam_results_publish"),
    path("<int:pk>/marks/", views.MarksEntryView.as_view(), name="mark_entry"),
    path("subject/<int:pk>/delete/", views.ExamSubjectDeleteView.as_view(), name="exam_subject_delete"),
    path("marks/", views.MarkEntryListView.as_view(), name="mark_entry_list"),
    path("marks/export/", views.MarkEntryListView.as_view(), name="mark_entry_export"),
    path("results/", views.ResultListView.as_view(), name="result_list"),
    path("results/export/", views.ResultListView.as_view(), name="result_export"),
    path("results/grading-policy/", views.grade_scale, name="grade_scale"),
    path("results/<int:pk>/", views.ResultDetailView.as_view(), name="result_detail"),
    path("results/<int:pk>/marksheet/", views.result_marksheet, name="result_marksheet"),
    path("results/student/<int:student_pk>/", views.StudentResultListView.as_view(), name="student_result_list"),
    path("report/", views.exam_report, name="exam_report"),
]