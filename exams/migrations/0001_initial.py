import django.core.validators
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
            name="Exam",
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
                ("name", models.CharField(max_length=150)),
                ("code", models.CharField(db_index=True, max_length=30, unique=True)),
                (
                    "exam_type",
                    models.CharField(
                        choices=[
                            ("UNIT", "Unit Test"),
                            ("INTERNAL", "Internal Assessment"),
                            ("MIDTERM", "Mid Term"),
                            ("SEMESTER", "Semester Exam"),
                            ("PRACTICAL", "Practical Exam"),
                            ("VIVA", "Viva Voce"),
                            ("SUPPLEMENT", "Supplementary Exam"),
                            ("FINAL", "Final Exam"),
                        ],
                        default="SEMESTER",
                        max_length=15,
                    ),
                ),
                ("academic_year", models.CharField(blank=True, max_length=20)),
                ("start_date", models.DateField()),
                ("end_date", models.DateField()),
                ("total_marks", models.DecimalField(decimal_places=2, default=0, max_digits=8)),
                ("passing_marks", models.DecimalField(decimal_places=2, default=0, max_digits=8)),
                (
                    "passing_percentage",
                    models.DecimalField(
                        decimal_places=2,
                        default=40,
                        help_text="Minimum overall percentage to pass.",
                        max_digits=5,
                    ),
                ),
                ("is_published", models.BooleanField(db_index=True, default=False)),
                ("results_published", models.BooleanField(default=False)),
                ("allow_marks_entry", models.BooleanField(default=True)),
                ("description", models.TextField(blank=True)),
                (
                    "course",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="exams",
                        to="academics.course",
                    ),
                ),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="exams_created",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "semester",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="exams",
                        to="academics.semester",
                    ),
                ),
            ],
            options={
                "verbose_name": "exam",
                "verbose_name_plural": "exams",
                "ordering": ["-start_date", "name"],
                "indexes": [
                    models.Index(fields=["course", "semester"], name="exam_course_sem_idx"),
                    models.Index(fields=["start_date", "end_date"], name="exam_date_idx"),
                ],
            },
        ),
        migrations.CreateModel(
            name="ExamSubject",
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
                ("max_marks", models.DecimalField(decimal_places=2, default=100, max_digits=7)),
                ("exam_date", models.DateField(blank=True, null=True)),
                ("exam_time", models.CharField(blank=True, max_length=60)),
                ("venue", models.CharField(blank=True, max_length=100)),
                ("instructions", models.CharField(blank=True, max_length=255)),
                (
                    "exam",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="exam_subjects",
                        to="exams.exam",
                    ),
                ),
                (
                    "subject",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="exam_subjects",
                        to="academics.subject",
                    ),
                ),
            ],
            options={
                "verbose_name": "exam subject",
                "verbose_name_plural": "exam subjects",
                "ordering": ["subject__code"],
                "constraints": [
                    models.UniqueConstraint(
                        fields=("exam", "subject"), name="uniq_exam_subject"
                    )
                ],
            },
        ),
        migrations.CreateModel(
            name="MarkEntry",
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
                    "marks_obtained",
                    models.DecimalField(blank=True, decimal_places=2, max_digits=7, null=True),
                ),
                ("is_absent", models.BooleanField(default=False)),
                ("remarks", models.CharField(blank=True, max_length=200)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "entered_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="marks_entered",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "exam",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="mark_entries",
                        to="exams.exam",
                    ),
                ),
                (
                    "exam_subject",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="mark_entries",
                        to="exams.examsubject",
                    ),
                ),
                (
                    "student",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="mark_entries",
                        to="students.student",
                    ),
                ),
            ],
            options={
                "verbose_name": "mark entry",
                "verbose_name_plural": "mark entries",
                "ordering": ["exam_subject__subject__code", "student__student_id"],
                "indexes": [
                    models.Index(fields=["exam", "student"], name="mark_exam_student_idx"),
                ],
                "constraints": [
                    models.UniqueConstraint(
                        fields=("exam_subject", "student"),
                        name="uniq_mark_exam_subject_student",
                    )
                ],
            },
        ),
        migrations.CreateModel(
            name="Result",
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
                ("total_marks", models.DecimalField(decimal_places=2, default=0, max_digits=8)),
                ("max_marks", models.DecimalField(decimal_places=2, default=0, max_digits=8)),
                (
                    "percentage",
                    models.DecimalField(decimal_places=2, default=0, max_digits=6),
                ),
                ("grade", models.CharField(blank=True, max_length=3)),
                (
                    "grade_point",
                    models.DecimalField(decimal_places=2, default=0, max_digits=4),
                ),
                ("is_pass", models.BooleanField(default=False)),
                ("failed_subjects", models.PositiveSmallIntegerField(default=0)),
                ("absent_subjects", models.PositiveSmallIntegerField(default=0)),
                ("calculated_at", models.DateTimeField(auto_now=True)),
                ("published", models.BooleanField(default=False)),
                (
                    "exam",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="results",
                        to="exams.exam",
                    ),
                ),
                (
                    "student",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="results",
                        to="students.student",
                    ),
                ),
            ],
            options={
                "verbose_name": "result",
                "verbose_name_plural": "results",
                "ordering": ["-percentage"],
                "constraints": [
                    models.UniqueConstraint(
                        fields=("exam", "student"), name="uniq_result_exam_student"
                    )
                ],
                "indexes": [
                    models.Index(fields=["grade", "percentage"], name="result_grade_idx"),
                ],
            },
        ),
    ]
