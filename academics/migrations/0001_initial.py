import django.core.validators
import django.db.models.deletion
from django.db import migrations, models

import core.validators


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="Semester",
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
                    "number",
                    models.PositiveSmallIntegerField(
                        unique=True,
                        validators=[django.core.validators.MinValueValidator(1)],
                    ),
                ),
                ("name", models.CharField(blank=True, max_length=40)),
                ("is_current", models.BooleanField(default=False)),
            ],
            options={
                "verbose_name": "semester",
                "verbose_name_plural": "semesters",
                "ordering": ["number"],
            },
        ),
        migrations.CreateModel(
            name="Department",
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
                    "code",
                    models.CharField(
                        db_index=True,
                        help_text="e.g. CSE",
                        max_length=10,
                        unique=True,
                        validators=[core.validators.validate_code],
                    ),
                ),
                ("name", models.CharField(max_length=120, unique=True)),
                ("description", models.TextField(blank=True)),
                (
                    "hod",
                    models.CharField(
                        blank=True,
                        help_text="Head of Department (name of the faculty member).",
                        max_length=120,
                    ),
                ),
                ("email", models.EmailField(blank=True, max_length=254)),
                ("phone", models.CharField(blank=True, max_length=20)),
                ("established_year", models.PositiveSmallIntegerField(blank=True, null=True)),
                ("is_active", models.BooleanField(default=True, db_index=True)),
            ],
            options={
                "verbose_name": "department",
                "verbose_name_plural": "departments",
                "ordering": ["name"],
                "indexes": [
                    models.Index(fields=["name"], name="dept_name_idx"),
                ],
            },
        ),
        migrations.CreateModel(
            name="Batch",
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
                    "name",
                    models.CharField(help_text="e.g. 2022-2026", max_length=30, unique=True),
                ),
                ("start_year", models.PositiveSmallIntegerField()),
                ("end_year", models.PositiveSmallIntegerField()),
                ("is_active", models.BooleanField(default=True)),
                (
                    "department",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="batches",
                        to="academics.department",
                    ),
                ),
            ],
            options={
                "verbose_name": "batch",
                "verbose_name_plural": "batches",
                "ordering": ["-start_year"],
            },
        ),
        migrations.CreateModel(
            name="Course",
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
                ("name", models.CharField(max_length=140)),
                (
                    "code",
                    models.CharField(
                        db_index=True,
                        max_length=20,
                        unique=True,
                        validators=[core.validators.validate_code],
                    ),
                ),
                (
                    "level",
                    models.CharField(
                        choices=[
                            ("UG", "Under Graduate"),
                            ("PG", "Post Graduate"),
                            ("DIPLOMA", "Diploma"),
                            ("CERTIFICATE", "Certificate"),
                        ],
                        default="UG",
                        max_length=30,
                    ),
                ),
                (
                    "duration_years",
                    models.PositiveSmallIntegerField(
                        default=4, validators=[django.core.validators.MinValueValidator(1)]
                    ),
                ),
                ("total_semesters", models.PositiveSmallIntegerField(default=8)),
                ("annual_fee", models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ("description", models.TextField(blank=True)),
                ("eligibility", models.CharField(blank=True, max_length=255)),
                ("is_active", models.BooleanField(default=True, db_index=True)),
                (
                    "department",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="courses",
                        to="academics.department",
                    ),
                ),
            ],
            options={
                "verbose_name": "course",
                "verbose_name_plural": "courses",
                "ordering": ["name"],
                "indexes": [
                    models.Index(
                        fields=["department", "is_active"], name="course_dept_active_idx"
                    ),
                ],
                "constraints": [
                    models.UniqueConstraint(
                        fields=("code", "department"), name="uniq_course_code_per_department"
                    )
                ],
            },
        ),
        migrations.CreateModel(
            name="Subject",
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
                ("name", models.CharField(max_length=140)),
                (
                    "code",
                    models.CharField(
                        db_index=True,
                        max_length=20,
                        unique=True,
                        validators=[core.validators.validate_code],
                    ),
                ),
                (
                    "credits",
                    models.PositiveSmallIntegerField(
                        default=4, validators=[django.core.validators.MinValueValidator(1)]
                    ),
                ),
                (
                    "subject_type",
                    models.CharField(
                        choices=[
                            ("THEORY", "Theory"),
                            ("PRACTICAL", "Practical"),
                            ("BOTH", "Theory + Practical"),
                        ],
                        default="THEORY",
                        max_length=20,
                    ),
                ),
                ("lecture_hours", models.PositiveSmallIntegerField(default=4)),
                ("description", models.TextField(blank=True)),
                ("is_active", models.BooleanField(default=True, db_index=True)),
                (
                    "course",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="subjects",
                        to="academics.course",
                    ),
                ),
                (
                    "semester",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="subjects",
                        to="academics.semester",
                    ),
                ),
            ],
            options={
                "verbose_name": "subject",
                "verbose_name_plural": "subjects",
                "ordering": ["semester__number", "name"],
                "indexes": [
                    models.Index(
                        fields=["course", "semester"], name="subject_course_sem_idx"
                    ),
                ],
                "constraints": [
                    models.UniqueConstraint(
                        fields=("course", "semester", "name"),
                        name="uniq_subject_per_course_sem",
                    )
                ],
            },
        ),
    ]
