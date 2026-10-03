import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models
import django.utils.timezone
from django.db.migrations.swappable_dependency import swappable_dependency


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("academics", "0001_initial"),
        ("students", "0001_initial"),
        swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="FeeType",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("name", models.CharField(max_length=80, unique=True)),
                ("code", models.CharField(blank=True, max_length=20, unique=True)),
                ("description", models.TextField(blank=True)),
                ("is_active", models.BooleanField(default=True)),
                ("is_mandatory", models.BooleanField(default=True)),
            ],
            options={
                "verbose_name": "fee type",
                "verbose_name_plural": "fee types",
                "ordering": ["name"],
            },
        ),
        migrations.CreateModel(
            name="FeeStructure",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("amount", models.DecimalField(decimal_places=2, max_digits=12)),
                ("frequency", models.CharField(default="SEMESTER", max_length=20)),
                ("academic_year", models.CharField(blank=True, max_length=20)),
                ("is_active", models.BooleanField(default=True)),
                ("description", models.CharField(blank=True, max_length=255)),
                (
                    "course",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="fee_structures",
                        to="academics.course",
                    ),
                ),
                (
                    "department",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="fee_structures",
                        to="academics.department",
                    ),
                ),
                (
                    "fee_type",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="structures",
                        to="fees.feetype",
                    ),
                ),
                (
                    "semester",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="fee_structures",
                        to="academics.semester",
                    ),
                ),
            ],
            options={
                "verbose_name": "fee structure",
                "verbose_name_plural": "fee structures",
                "ordering": ["fee_type__name", "-academic_year"],
                "constraints": [
                    models.UniqueConstraint(
                        fields=("fee_type", "course", "semester", "academic_year"),
                        name="uniq_fee_structure_scope",
                    )
                ],
            },
        ),
        migrations.CreateModel(
            name="FeeRecord",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("invoice_no", models.CharField(db_index=True, max_length=30, unique=True)),
                ("amount", models.DecimalField(decimal_places=2, max_digits=12)),
                ("discount", models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ("due_date", models.DateField()),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("PENDING", "Pending"),
                            ("PARTIAL", "Partially Paid"),
                            ("PAID", "Paid"),
                            ("OVERDUE", "Overdue"),
                            ("CANCELLED", "Cancelled"),
                        ],
                        db_index=True,
                        default="PENDING",
                        max_length=10,
                    ),
                ),
                ("academic_year", models.CharField(blank=True, max_length=20)),
                ("notes", models.CharField(blank=True, max_length=255)),
                ("is_carried_forward", models.BooleanField(default=False)),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="fee_records_created",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "fee_structure",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="billed_records",
                        to="fees.feestructure",
                    ),
                ),
                (
                    "fee_type",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="fee_records",
                        to="fees.feetype",
                    ),
                ),
                (
                    "student",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="fee_records",
                        to="students.student",
                    ),
                ),
            ],
            options={
                "verbose_name": "fee record",
                "verbose_name_plural": "fee records",
                "ordering": ["-due_date", "-created_at"],
                "indexes": [
                    models.Index(fields=["student", "status"], name="fee_student_status_idx"),
                    models.Index(fields=["due_date", "status"], name="fee_due_status_idx"),
                ],
            },
        ),
        migrations.CreateModel(
            name="Payment",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("receipt_no", models.CharField(db_index=True, max_length=30, unique=True)),
                ("amount", models.DecimalField(decimal_places=2, max_digits=12)),
                ("payment_date", models.DateField(default=django.utils.timezone.localdate)),
                (
                    "method",
                    models.CharField(
                        choices=[
                            ("CASH", "Cash"),
                            ("BANK", "Bank Transfer"),
                            ("CHEQUE", "Cheque"),
                            ("CARD", "Card"),
                            ("MOBILE", "Mobile Banking"),
                            ("ONLINE", "Online Gateway"),
                        ],
                        default="CASH",
                        max_length=10,
                    ),
                ),
                ("reference_no", models.CharField(blank=True, max_length=60)),
                ("remarks", models.CharField(blank=True, max_length=255)),
                ("is_cancelled", models.BooleanField(default=False)),
                (
                    "fee_record",
                    models.ForeignKey(
                        blank=True,
                        help_text="Leave empty to settle several invoices at once.",
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="payments",
                        to="fees.feerecord",
                    ),
                ),
                (
                    "received_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="payments_received",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "student",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="payments",
                        to="students.student",
                    ),
                ),
            ],
            options={
                "verbose_name": "payment",
                "verbose_name_plural": "payments",
                "ordering": ["-payment_date", "-created_at"],
                "indexes": [
                    models.Index(fields=["payment_date", "method"], name="payment_date_method_idx"),
                ],
            },
        ),
    ]