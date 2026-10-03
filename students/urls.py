from django.urls import path

from students import views

app_name = "students"

urlpatterns = [
    path("", views.StudentListView.as_view(), name="student_list"),
    path("add/", views.StudentCreateView.as_view(), name="student_add"),
    path("export/", views.StudentListView.as_view(), name="student_export"),
    path("stats/", views.StudentStatsView.as_view(), name="student_stats"),
    path("promotions/", views.promotion_history, name="promotion_history"),
    path("bulk-action/", views.student_bulk_action, name="student_bulk_action"),
    path("bulk-delete/", views.student_bulk_delete, name="student_bulk_delete"),
    path("filter-options/", views.student_filter_options, name="student_filter_options"),
    path("<int:pk>/", views.StudentDetailView.as_view(), name="student_detail"),
    path("<int:pk>/edit/", views.StudentUpdateView.as_view(), name="student_edit"),
    path("<int:pk>/delete/", views.StudentDeleteView.as_view(), name="student_delete"),
    path("<int:pk>/status/", views.student_status_toggle, name="student_status_toggle"),
    path("<int:pk>/promote/", views.student_promote, name="student_promote"),
    path("<int:pk>/print/", views.student_print, name="student_print"),
    path("<int:pk>/id-card/", views.student_id_card, name="student_id_card"),
    path("<int:pk>/id-card/download/", views.student_id_card_download, name="student_id_card_download"),
    path("<int:pk>/documents/upload/", views.student_document_upload, name="student_document_upload"),
    # Documents
    path("documents/<int:pk>/download/", views.student_document_download, name="student_document_download"),
    path("documents/<int:pk>/delete/", views.student_document_delete, name="student_document_delete"),
]
