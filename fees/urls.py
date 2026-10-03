from django.urls import path

from fees import views

app_name = "fees"

urlpatterns = [
    # fee types
    path("types/", views.FeeTypeListView.as_view(), name="fee_type_list"),
    path("types/export/", views.FeeTypeListView.as_view(), name="fee_type_export"),
    path("types/add/", views.FeeTypeCreateView.as_view(), name="fee_type_add"),
    path("types/<int:pk>/edit/", views.FeeTypeUpdateView.as_view(), name="fee_type_edit"),
    path("types/<int:pk>/delete/", views.FeeTypeDeleteView.as_view(), name="fee_type_delete"),
    # fee structures
    path("structures/", views.FeeStructureListView.as_view(), name="fee_structure_list"),
    path("structures/export/", views.FeeStructureListView.as_view(), name="fee_structure_export"),
    path("structures/add/", views.FeeStructureCreateView.as_view(), name="fee_structure_add"),
    path("structures/<int:pk>/edit/", views.FeeStructureUpdateView.as_view(), name="fee_structure_edit"),
    path("structures/<int:pk>/delete/", views.FeeStructureDeleteView.as_view(), name="fee_structure_delete"),
    path("structures/<int:pk>/generate/", views.bulk_invoice_generate_structure, name="fee_structure_generate"),
    path("invoices/generate/", views.bulk_invoice_generate, name="bulk_invoice_generate"),
    # fee records / invoices
    path("records/", views.FeeRecordListView.as_view(), name="fee_record_list"),
    path("records/export/", views.FeeRecordListView.as_view(), name="fee_record_export"),
    path("records/add/", views.FeeRecordCreateView.as_view(), name="fee_record_add"),
    path("records/<int:pk>/", views.FeeRecordDetailView.as_view(), name="fee_record_detail"),
    path("records/<int:pk>/edit/", views.FeeRecordUpdateView.as_view(), name="fee_record_edit"),
    path("records/<int:pk>/delete/", views.FeeRecordDeleteView.as_view(), name="fee_record_delete"),
    path("records/<int:pk>/cancel/", views.fee_record_cancel, name="fee_record_cancel"),
    path("records/<int:pk>/invoice/", views.fee_record_invoice, name="fee_record_invoice"),
    # payments
    path("payments/", views.PaymentListView.as_view(), name="payment_list"),
    path("payments/export/", views.PaymentListView.as_view(), name="payment_export"),
    path("payments/add/", views.PaymentCreateView.as_view(), name="payment_add"),
    path("payments/collect/<int:student_pk>/", views.collect_payment, name="collect_payment"),
    path("payments/<int:pk>/", views.PaymentDetailView.as_view(), name="payment_detail"),
    path("payments/<int:pk>/cancel/", views.payment_cancel, name="payment_cancel"),
    path("payments/<int:pk>/receipt/", views.payment_receipt, name="payment_receipt"),
    path("ledger/<int:student_pk>/", views.student_ledger_view, name="student_ledger"),
    # reports
    path("reports/overdue/", views.overdue_report, name="overdue_report"),
    path("reports/collection/", views.fee_collection_report, name="fee_report"),
]