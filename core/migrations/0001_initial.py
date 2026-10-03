import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models
from django.db.migrations.swappable_dependency import swappable_dependency


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="SiteSetting",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "institute_name",
                    models.CharField(
                        default="Springfield Institute of Technology", max_length=200
                    ),
                ),
                ("institute_code", models.CharField(blank=True, default="SIT", max_length=20)),
                ("address", models.TextField(blank=True)),
                ("city", models.CharField(blank=True, max_length=100)),
                ("state", models.CharField(blank=True, max_length=100)),
                ("pincode", models.CharField(blank=True, max_length=10)),
                ("phone", models.CharField(blank=True, max_length=20)),
                ("email", models.EmailField(blank=True, max_length=254)),
                ("website", models.URLField(blank=True)),
                (
                    "logo",
                    models.ImageField(blank=True, null=True, upload_to="branding/"),
                ),
                ("academic_year", models.CharField(default="2024-2025", max_length=20)),
                ("current_semester", models.PositiveSmallIntegerField(default=1)),
                (
                    "pass_percentage",
                    models.DecimalField(
                        decimal_places=2,
                        default=40,
                        help_text="Minimum overall percentage required to pass.",
                        max_digits=5,
                    ),
                ),
                (
                    "attendance_shortage_percentage",
                    models.DecimalField(decimal_places=2, default=75, max_digits=5),
                ),
                ("currency_symbol", models.CharField(default="₹", max_length=10)),
                ("receipt_prefix", models.CharField(default="RCPT", max_length=10)),
                ("id_card_validity_months", models.PositiveSmallIntegerField(default=12)),
                (
                    "updated_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="setting_updates",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "site setting",
                "verbose_name_plural": "site settings",
            },
        ),
        migrations.CreateModel(
            name="AuditLog",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "created_at",
                    models.DateTimeField(db_index=True, default=django.utils.timezone.now),
                ),
                (
                    "user",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="audit_logs",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                ("username_snapshot", models.CharField(blank=True, max_length=150)),
                (
                    "action",
                    models.CharField(
                        choices=[
                            ("CREATE", "Create"),
                            ("UPDATE", "Update"),
                            ("DELETE", "Delete"),
                            ("VIEW", "View"),
                            ("LOGIN", "Login"),
                            ("LOGOUT", "Logout"),
                            ("LOGIN_FAILED", "Login failed"),
                            ("EXPORT", "Export"),
                            ("PRINT", "Print"),
                            ("PAYMENT", "Payment"),
                            ("PROMOTE", "Promote"),
                            ("UPLOAD", "Upload"),
                            ("DOWNLOAD", "Download"),
                            ("STATUS_CHANGE", "Status change"),
                        ],
                        db_index=True,
                        max_length=20,
                    ),
                ),
                ("module", models.CharField(blank=True, db_index=True, max_length=50)),
                ("record_type", models.CharField(blank=True, max_length=50)),
                ("record_id", models.CharField(blank=True, db_index=True, max_length=64)),
                ("record_repr", models.CharField(blank=True, max_length=255)),
                ("description", models.TextField(blank=True)),
                ("changes", models.JSONField(blank=True, null=True)),
                ("http_method", models.CharField(blank=True, max_length=10)),
                ("path", models.CharField(blank=True, max_length=255)),
                ("ip_address", models.GenericIPAddressField(blank=True, null=True)),
                ("user_agent", models.CharField(blank=True, max_length=255)),
                ("status_code", models.PositiveSmallIntegerField(blank=True, null=True)),
            ],
            options={
                "verbose_name": "audit log",
                "verbose_name_plural": "audit logs",
                "ordering": ["-created_at", "-id"],
                "indexes": [
                    models.Index(
                        fields=["module", "action"], name="audit_module_action_idx"
                    ),
                    models.Index(
                        fields=["user", "created_at"], name="audit_user_created_idx"
                    ),
                ],
            },
        ),
    ]
