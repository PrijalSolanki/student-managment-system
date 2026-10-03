import django.core.validators
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models
from django.db.migrations.swappable_dependency import swappable_dependency

import core.validators
import students.models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("academics", "0001_initial"),
        swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Student",
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
                    "student_id",
                    models.CharField(
                        blank=True,
                        db_index=True,
                        help_text="Enrolment number",
                        max_length=20,
                        unique=True,
                    ),
                ),
                ("first_name", models.CharField(max_length=80)),
                ("last_name", models.CharField(blank=True, max_length=80)),
                ("email", models.EmailField(max_length=254, unique=True)),
                (
                    "phone",
                    models.CharField(max_length=20, validators=[core.validators.validate_phone]),
                ),
                ("date_of_birth", models.DateField()),
                (
                    "gender",
                    models.CharField(
                        choices=[("M", "Male"), ("F", "Female"), ("O", "Other")],
                        db_index=True,
                        default="M",
                        max_length=1,
                    ),
                ),
                (
                    "blood_group",
                    models.CharField(
                        choices=[
                            ("A+", "A+"),
                            ("A-", "A-"),
                            ("B+", "B+"),
                            ("B-", "B-"),
                            ("O+", "O+"),
                            ("O-", "O-"),
                            ("AB+", "AB+"),
                            ("AB-", "AB-"),
                        ],
                        blank=True,
                        max_length=4,
                    ),
                ),
                ("nationality", models.CharField(default="Indian", max_length=60)),
                ("religion", models.CharField(blank=True, max_length=40)),
                (
                    "category",
                    models.CharField(
                        blank=True,
                        choices=[
                            ("GENERAL", "General"),
                            ("OBC", "OBC"),
                            ("SC", "SC"),
                            ("ST", "ST"),
                            ("EWS", "EWS"),
                        ],
                        max_length=30,
                    ),
                ),
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
                        blank=True, null=True, upload_to=students.models.student_photo_path
                    ),
                ),
                ("admission_date", models.DateField(db_index=True)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("ACTIVE", "Active"),
                            ("INACTIVE", "Inactive"),
                            ("ON_LEAVE", "On Leave"),
                            ("SUSPENDED", "Suspended"),
                            ("GRADUATED", "Graduated"),
                            ("DROPPED", "Dropped"),
                        ],
                        db_index=True,
                        default="ACTIVE",
                        max_length=12,
                    ),
                ),
                ("guardian_name", models.CharField(blank=True, max_length=120)),
                (
                    "guardian_phone",
                    models.CharField(
                        blank=True, max_length=20, validators=[core.validators.validate_phone]
                    ),
                ),
                ("guardian_relation", models.CharField(blank=True, max_length=30)),
                (
                    "emergency_contact",
                    models.CharField(
                        blank=True, max_length=20, validators=[core.validators.validate_phone]
                    ),
                ),
                ("previous_qualification", models.CharField(blank=True, max_length=120)),
                (
                    "previous_percentage",
                    models.DecimalField(blank=True, decimal_places=2, max_digits=5, null=True),
                ),
                ("scholarship", models.CharField(blank=True, max_length=60)),
                ("notes", models.TextField(blank=True)),
                (
                    "batch",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="students",
                        to="academics.batch",
                    ),
                ),
                (
                    "course",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="students",
                        to="academics.course",
                    ),
                ),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="students_created",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "department",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="students",
                        to="academics.department",
                    ),
                ),
                (
                    "semester",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="students",
                        to="academics.semester",
                    ),
                ),
            ],
            options={
                "verbose_name": "student",
                "verbose_name_plural": "students",
                "ordering": ["student_id"],
                "indexes": [
                    models.Index(fields=["last_name", "first_name"], name="student_name_idx"),
                    models.Index(
                        fields=["department", "course", "semester"],
                        name="student_academic_idx",
                    ),
                    models.Index(
                        fields=["status", "admission_date"], name="student_status_idx"
                    ),
                    models.Index(fields=["email"], name="student_email_idx"),
                ],
            },
        ),
        migrations.CreateModel(
            name="StudentPromotion",
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
                ("academic_year_from", models.CharField(blank=True, max_length=20)),
                ("academic_year_to", models.CharField(blank=True, max_length=20)),
                (
                    "promotion_type",
                    models.CharField(
                        choices=[
                            ("SEMESTER", "Semester Promotion"),
                            ("BATCH", "Batch Promotion"),
                            ("COURSE_CHANGE", "Course Change"),
                            ("DEPARTMENT_CHANGE", "Department Change"),
                            ("REVISION", "Backlog / Revision"),
                        ],
                        default="SEMESTER",
                        max_length=20,
                    ),
                ),
                ("reason", models.CharField(blank=True, max_length=255)),
                ("remarks", models.TextField(blank=True)),
                (
                    "from_batch",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="promotions_from",
                        to="academics.batch",
                    ),
                ),
                (
                    "from_course",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="promotions_from",
                        to="academics.course",
                    ),
                ),
                (
                    "from_department",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="promotions_from",
                        to="academics.department",
                    ),
                ),
                (
                    "from_semester",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="promotions_from",
                        to="academics.semester",
                    ),
                ),
                (
                    "promoted_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="student_promotions",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "student",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="promotions",
                        to="students.student",
                    ),
                ),
                (
                    "to_batch",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="promotions_to",
                        to="academics.batch",
                    ),
                ),
                (
                    "to_course",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="promotions_to",
                        to="academics.course",
                    ),
                ),
                (
                    "to_department",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="promotions_to",
                        to="academics.department",
                    ),
                ),
                (
                    "to_semester",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="promotions_to",
                        to="academics.semester",
                    ),
                ),
            ],
            options={
                "verbose_name": "student promotion",
                "verbose_name_plural": "student promotions",
                "ordering": ["-created_at"],
                "indexes": [
                    models.Index(fields=["student", "-created_at"], name="promo_student_idx"),
                ],
            },
        ),
        migrations.CreateModel(
            name="StudentDocument",
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
                    "document_type",
                    models.CharField(
                        choices=[
                            ("AADHAAR", "Aadhaar / National ID"),
                            ("BIRTH_CERTIFICATE", "Birth Certificate"),
                            ("MARKSHEET", "Previous Marksheet"),
                            ("TRANSFER_CERTIFICATE", "Transfer Certificate"),
                            ("CASTE_CERTIFICATE", "Caste / Category Certificate"),
                            ("PHOTO_ID", "Photo ID Card"),
                            ("OTHER", "Other Document"),
                        ],
                        default="OTHER",
                        max_length=25,
                    ),
                ),
                ("title", models.CharField(max_length=150)),
                (
                    "file",
                    models.FileField(
                        upload_to=students.models.document_path,
                        validators=[
                            core.validators.FileSizeValidator(5),
                            core.validators.validate_document,
                        ],
                    ),
                ),
                ("description", models.CharField(blank=True, max_length=255)),
                ("file_size", models.PositiveIntegerField(default=0)),
                ("content_type", models.CharField(blank=True, max_length=100)),
                ("expiry_date", models.DateField(blank=True, null=True)),
                ("is_verified", models.BooleanField(default=False)),
                (
                    "student",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="documents",
                        to="students.student",
                    ),
                ),
                (
                    "uploaded_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="documents_uploaded",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "student document",
                "verbose_name_plural": "student documents",
                "ordering": ["-created_at"],
                "indexes": [
                    models.Index(
                        fields=["student", "document_type"], name="doc_student_type_idx"
                    )
                ],
            },
        ),
    ]
