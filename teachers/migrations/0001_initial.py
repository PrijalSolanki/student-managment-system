import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models
from django.db.migrations.swappable_dependency import swappable_dependency

import core.validators
import teachers.models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("academics", "0001_initial"),
        swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Teacher",
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
                    "employee_id",
                    models.CharField(blank=True, db_index=True, max_length=20, unique=True),
                ),
                ("first_name", models.CharField(max_length=80)),
                ("last_name", models.CharField(blank=True, max_length=80)),
                ("email", models.EmailField(max_length=254, unique=True)),
                (
                    "phone",
                    models.CharField(max_length=20, validators=[core.validators.validate_phone]),
                ),
                (
                    "gender",
                    models.CharField(
                        choices=[("M", "Male"), ("F", "Female"), ("O", "Other")],
                        default="M",
                        max_length=1,
                    ),
                ),
                ("date_of_birth", models.DateField(blank=True, null=True)),
                ("blood_group", models.CharField(blank=True, max_length=5)),
                ("qualification", models.CharField(blank=True, max_length=120)),
                ("specialization", models.CharField(blank=True, max_length=120)),
                ("designation", models.CharField(blank=True, max_length=80)),
                ("joining_date", models.DateField(blank=True, null=True)),
                ("salary", models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ("address", models.TextField(blank=True)),
                ("city", models.CharField(blank=True, max_length=80)),
                ("state", models.CharField(blank=True, max_length=80)),
                (
                    "pincode",
                    models.CharField(
                        blank=True,
                        max_length=10,
                        validators=[core.validators.validate_pincode],
                    ),
                ),
                (
                    "photo",
                    models.ImageField(
                        blank=True, null=True, upload_to=teachers.models.teacher_photo_path
                    ),
                ),
                ("bio", models.TextField(blank=True)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("ACTIVE", "Active"),
                            ("ON_LEAVE", "On Leave"),
                            ("INACTIVE", "Inactive"),
                        ],
                        db_index=True,
                        default="ACTIVE",
                        max_length=10,
                    ),
                ),
                (
                    "department",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="teachers",
                        to="academics.department",
                    ),
                ),
                (
                    "user",
                    models.OneToOneField(
                        blank=True,
                        help_text="Optional portal login for this teacher.",
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="teacher_profile",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "teacher",
                "verbose_name_plural": "teachers",
                "ordering": ["first_name", "last_name"],
                "indexes": [
                    models.Index(fields=["last_name", "first_name"], name="teacher_name_idx"),
                    models.Index(
                        fields=["department", "status"], name="teacher_dept_status_idx"
                    ),
                ],
            },
        ),
        migrations.CreateModel(
            name="SubjectAssignment",
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
                ("academic_year", models.CharField(blank=True, max_length=20)),
                ("is_primary", models.BooleanField(default=True)),
                ("remarks", models.CharField(blank=True, max_length=200)),
                (
                    "assigned_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="subject_assignments_made",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "subject",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="assignments",
                        to="academics.subject",
                    ),
                ),
                (
                    "teacher",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="assignments",
                        to="teachers.teacher",
                    ),
                ),
            ],
            options={
                "verbose_name": "subject assignment",
                "verbose_name_plural": "subject assignments",
                "ordering": ["subject__code"],
                "constraints": [
                    models.UniqueConstraint(
                        fields=("teacher", "subject"),
                        name="uniq_teacher_subject_assignment",
                    )
                ],
            },
        ),
    ]
