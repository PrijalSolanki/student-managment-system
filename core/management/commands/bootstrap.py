"""``python manage.py bootstrap`` — idempotent first-run setup.

Creates the site-settings singleton, the base academic structure and the two
default login accounts. Safe to run repeatedly: every step uses ``get_or_create``
so existing rows are updated in place instead of duplicated.
"""

from __future__ import annotations

from django.core.management.base import BaseCommand
from django.db import transaction

DEFAULT_ADMIN = {
    "username": "admin",
    "email": "admin@example.com",
    "first_name": "System",
    "last_name": "Administrator",
}
DEFAULT_STAFF = {
    "username": "staff",
    "email": "staff@example.com",
    "first_name": "Demo",
    "last_name": "Staff",
}
DEFAULT_PASSWORD = "Admin@123"


class Command(BaseCommand):
    help = "Create the site settings, base academic data and default users."

    def add_arguments(self, parser):
        parser.add_argument(
            "--password",
            default=DEFAULT_PASSWORD,
            help="Password assigned to the default admin/staff accounts.",
        )
        parser.add_argument(
            "--no-users",
            action="store_true",
            help="Skip creating the default admin and staff accounts.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        from accounts.models import User
        from academics.models import Course, Department, Semester, Subject
        from core.models import SiteSetting

        self.stdout.write("Bootstrapping Student Management System...")

        settings_row = SiteSetting.load()
        self.stdout.write(self.style.SUCCESS(f"  site settings: {settings_row.institute_name}"))

        department, _ = Department.objects.get_or_create(
            code="CSE", defaults={"name": "Computer Science & Engineering"}
        )
        course, _ = Course.objects.get_or_create(
            code="BTCS",
            department=department,
            defaults={
                "name": "B.Tech Computer Science",
                "level": "UG",
                "duration_years": 4,
                "total_semesters": 8,
                "annual_fee": 200000,
            },
        )
        semesters = []
        for number in range(1, 9):
            semester, _ = Semester.objects.get_or_create(
                number=number, defaults={"name": f"Semester {number}"}
            )
            semesters.append(semester)

        syllabus = [
            ("CS101", "Programming Fundamentals", 4),
            ("CS102", "Data Structures", 4),
            ("CS103", "Database Management Systems", 4),
            ("CS104", "Operating Systems", 3),
            ("CS105", "Computer Networks", 3),
            ("CS106", "Software Engineering", 3),
        ]
        for code, name, credits in syllabus:
            Subject.objects.get_or_create(
                code=code, defaults={"name": name, "credits": credits, "course": course}
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"  academics: 1 department, 1 course, {len(semesters)} semesters, "
                f"{Subject.objects.count()} subjects"
            )
        )

        if options["no_users"]:
            self.stdout.write("  users: skipped (--no-users)")
            return

        password = options["password"]
        _, created_admin = self._ensure_superuser(User, DEFAULT_ADMIN, password)
        _, created_staff = self._ensure_staff(User, DEFAULT_STAFF, password)

        self.stdout.write(
            self.style.SUCCESS(
                f"  users: admin={'created' if created_admin else 'exists'}, "
                f"staff={'created' if created_staff else 'exists'}"
            )
        )
        self.stdout.write("")
        self.stdout.write("Login with:")
        self.stdout.write(f"  admin / {password}   (administrator)")
        self.stdout.write(f"  staff / {password}   (staff member)")
        self.stdout.write(self.style.WARNING("Change these passwords before going live."))

    # ------------------------------------------------------------------ helpers
    def _ensure_superuser(self, user_model, data, password):
        user = user_model.objects.filter(username=data["username"]).first()
        if user:
            return user, False
        user = user_model.objects.create_superuser(password=password, **data)
        return user, True

    def _ensure_staff(self, user_model, data, password):
        user = user_model.objects.filter(username=data["username"]).first()
        if user:
            return user, False
        user = user_model.objects.create_user(password=password, role=user_model.Role.STAFF, **data)
        user.is_staff = True
        user.save(update_fields=["is_staff"])
        return user, True