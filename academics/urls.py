from django.urls import path

from academics import views

app_name = "academics"

urlpatterns = [
    # Departments
    path("departments/", views.DepartmentListView.as_view(), name="department_list"),
    path("departments/add/", views.DepartmentCreateView.as_view(), name="department_add"),
    path("departments/export/", views.DepartmentListView.as_view(), name="department_export"),
    path("departments/<int:pk>/", views.DepartmentDetailView.as_view(), name="department_detail"),
    path("departments/<int:pk>/edit/", views.DepartmentUpdateView.as_view(), name="department_edit"),
    path("departments/<int:pk>/delete/", views.DepartmentDeleteView.as_view(), name="department_delete"),
    # Semesters
    path("semesters/", views.semester_list, name="semester_list"),
    path("semesters/add/", views.SemesterCreateView.as_view(), name="semester_add"),
    path("semesters/<int:pk>/edit/", views.SemesterUpdateView.as_view(), name="semester_edit"),
    path("semesters/<int:pk>/delete/", views.SemesterDeleteView.as_view(), name="semester_delete"),
    # Batches
    path("batches/", views.BatchListView.as_view(), name="batch_list"),
    path("batches/add/", views.BatchCreateView.as_view(), name="batch_add"),
    path("batches/export/", views.BatchListView.as_view(), name="batch_export"),
    path("batches/<int:pk>/edit/", views.BatchUpdateView.as_view(), name="batch_edit"),
    path("batches/<int:pk>/delete/", views.BatchDeleteView.as_view(), name="batch_delete"),
    # Courses
    path("courses/", views.CourseListView.as_view(), name="course_list"),
    path("courses/add/", views.CourseCreateView.as_view(), name="course_add"),
    path("courses/export/", views.CourseListView.as_view(), name="course_export"),
    path("courses/<int:pk>/", views.CourseDetailView.as_view(), name="course_detail"),
    path("courses/<int:pk>/edit/", views.CourseUpdateView.as_view(), name="course_edit"),
    path("courses/<int:pk>/delete/", views.CourseDeleteView.as_view(), name="course_delete"),
    # Subjects
    path("subjects/", views.SubjectListView.as_view(), name="subject_list"),
    path("subjects/add/", views.SubjectCreateView.as_view(), name="subject_add"),
    path("subjects/export/", views.SubjectListView.as_view(), name="subject_export"),
    path("subjects/<int:pk>/", views.SubjectDetailView.as_view(), name="subject_detail"),
    path("subjects/<int:pk>/edit/", views.SubjectUpdateView.as_view(), name="subject_edit"),
    path("subjects/<int:pk>/delete/", views.SubjectDeleteView.as_view(), name="subject_delete"),
    path(
        "subjects/<int:pk>/assign/",
        views.subject_assignment_create,
        name="subject_assignment_create",
    ),
    path(
        "subject-assignments/<int:pk>/delete/",
        views.subject_assignment_delete,
        name="subject_assignment_delete",
    ),
    # Helpers
    path("ajax/courses/", views.course_options, name="course_options"),
]
