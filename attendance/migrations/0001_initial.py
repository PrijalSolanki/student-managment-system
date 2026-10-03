import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models
from django.db.migrations.swappable_dependency import swappable_dependency


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("academics", "0001_initial"),
        ("students", "0001_initial"),
        ("teachers", "0001_initial"),
        swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Attendance",
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
                ("date", models.DateField(db_index=True)),
                (
                    "status",
                    models.CharField(
                        choices=[("PRESENT", "Present"), ("ABSENT", "Absent"), ("LEAVE", "On Leave")],
                        default="PRESENT",
                        max_length=10,
                    ),
                ),
                ("remarks", models.CharField(blank=True, max_length=200)),
                ("marked_at", models.DateTimeField(auto_now=True)),
                (
                    "marked_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="attendance_marked",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "student",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="attendance_records",
                        to="students.student",
                    ),
                ),
                (
                    "subject",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="attendance_records",
                        to="academics.subject",
                    ),
                ),
                (
                    "teacher",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="attendance_records",
                        to="teachers.teacher",
                    ),
                ),
            ],
            options={
                "verbose_name": "attendance",
                "verbose_name_plural": "attendance records",
                "ordering": ["-date", "student__first_name"],
                "indexes": [
                    models.Index(fields=["date", "subject"], name="att_date_subject_idx"),
                    models.Index(fields=["student", "date"], name="att_student_date_idx"),
                    models.Index(fields=["status", "date"], name="att_status_date_idx"),
                ],
                "constraints": [
                    models.UniqueConstraint(
                        fields=("student", "subject", "date"),
                        name="uniq_attendance_student_subject_date",
                    )
                ],
            },
        ),
    ]
