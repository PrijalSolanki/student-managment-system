import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models
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
            name="Notification",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("title", models.CharField(max_length=150)),
                ("body", models.TextField()),
                (
                    "priority",
                    models.CharField(
                        choices=[
                            ("LOW", "Low"),
                            ("NORMAL", "Normal"),
                            ("HIGH", "High"),
                            ("URGENT", "Urgent"),
                        ],
                        default="NORMAL",
                        max_length=10,
                    ),
                ),
                (
                    "audience",
                    models.CharField(
                        choices=[
                            ("ALL", "Everyone"),
                            ("STAFF", "Staff Only"),
                            ("ADMIN", "Administrators"),
                            ("STUDENT", "Students"),
                            ("COURSE", "Specific Course"),
                            ("DEPARTMENT", "Specific Department"),
                            ("BATCH", "Specific Batch"),
                        ],
                        db_index=True,
                        default="ALL",
                        max_length=15,
                    ),
                ),
                ("is_pinned", models.BooleanField(default=False)),
                ("is_active", models.BooleanField(db_index=True, default=True)),
                ("expires_at", models.DateTimeField(blank=True, null=True)),
                ("action_url", models.CharField(blank=True, max_length=255)),
                ("attachment", models.FileField(blank=True, upload_to="notifications/")),
                ("read_count", models.PositiveIntegerField(default=0, editable=False)),
                (
                    "batch",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="notifications",
                        to="academics.batch",
                    ),
                ),
                (
                    "course",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="notifications",
                        to="academics.course",
                    ),
                ),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="notifications_created",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "department",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="notifications",
                        to="academics.department",
                    ),
                ),
            ],
            options={
                "verbose_name": "notification",
                "verbose_name_plural": "notifications",
                "ordering": ["-is_pinned", "-created_at"],
                "indexes": [
                    models.Index(fields=["is_active", "created_at"], name="notif_active_created_idx"),
                ],
            },
        ),
        migrations.CreateModel(
            name="NotificationRead",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("read_at", models.DateTimeField(auto_now_add=True)),
                (
                    "notification",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="reads",
                        to="notifications.notification",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="notification_reads",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "notification read receipt",
                "verbose_name_plural": "notification read receipts",
                "ordering": ["-read_at"],
                "constraints": [
                    models.UniqueConstraint(fields=("notification", "user"), name="uniq_notification_read")
                ],
            },
        ),
        migrations.CreateModel(
            name="StudentAnnouncement",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("title", models.CharField(max_length=150)),
                ("message", models.TextField()),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="student_announcements_created",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "notification",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="student_announcements",
                        to="notifications.notification",
                    ),
                ),
                (
                    "student",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="announcements",
                        to="students.student",
                    ),
                ),
            ],
            options={
                "verbose_name": "student announcement",
                "verbose_name_plural": "student announcements",
                "ordering": ["-created_at"],
            },
        ),
    ]