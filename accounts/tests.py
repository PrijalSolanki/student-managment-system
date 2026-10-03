"""Tests for roles, capabilities and view-level access control."""

from datetime import date

from django.test import TestCase
from django.urls import reverse


class RoleTests(TestCase):
    def test_superuser_is_forced_to_admin_role(self):
        from accounts.models import User

        user = User.objects.create_superuser(username="root", password="x")
        self.assertEqual(user.role, User.Role.ADMIN)
        self.assertTrue(user.is_admin)

    def test_staff_user_capabilities(self):
        from accounts.models import User

        staff = User.objects.create_user(
            username="staffer", password="x", role=User.Role.STAFF, is_staff=True
        )
        self.assertTrue(staff.is_internal_user)
        self.assertFalse(staff.is_admin)
        self.assertTrue(staff.can("mark_attendance"))
        self.assertTrue(staff.can("view_reports"))
        self.assertFalse(staff.can("manage_fees"))
        self.assertFalse(staff.can("delete_records"))

    def test_admin_capabilities(self):
        from accounts.models import User

        admin = User.objects.create_user(
            username="adm", password="x", role=User.Role.ADMIN, is_staff=True
        )
        self.assertTrue(admin.can("manage_fees"))
        self.assertTrue(admin.can("manage_settings"))
        self.assertTrue(admin.can("manage_users"))

    def test_inactive_user_loses_internal_access(self):
        from accounts.models import User

        staff = User.objects.create_user(
            username="gone", password="x", role=User.Role.STAFF, is_staff=True
        )
        staff.is_active = False
        staff.save()
        staff.refresh_from_db()
        self.assertFalse(staff.is_internal_user)

    def test_unknown_capability_is_denied(self):
        from accounts.models import User

        admin = User.objects.create_superuser(username="root2", password="x")
        self.assertFalse(admin.can("launch_rockets"))

    def test_display_helpers(self):
        from accounts.models import User

        user = User.objects.create_user(
            username="nameless", password="x", first_name="Ravi", last_name="Kumar"
        )
        self.assertEqual(user.display_name, "Ravi Kumar")
        self.assertEqual(user.initials, "RK")


class AccessControlTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        from accounts.models import User
        from academics.models import Department

        cls.staff = User.objects.create_user(
            username="viewer", password="secret-pass-123", role=User.Role.STAFF, is_staff=True
        )
        Department.objects.create(code="CSE", name="Computer Science")

    def test_anonymous_users_are_redirected_to_login(self):
        response = self.client.get(reverse("students:student_list"))
        self.assertEqual(response.status_code, 302)
        self.assertIn("login", response["Location"])

    def test_staff_can_open_list_pages(self):
        self.client.force_login(self.staff)
        for name in ["dashboard", "students:student_list", "teachers:teacher_list"]:
            with self.subTest(name=name):
                response = self.client.get(reverse(name))
                self.assertEqual(response.status_code, 200)

    def test_csv_export_is_available_to_staff(self):
        self.client.force_login(self.staff)
        response = self.client.get(reverse("students:student_list"), {"export": 1, "format": "csv"})
        self.assertEqual(response.status_code, 200)
        self.assertIn("text/csv", response["Content-Type"])

    def test_unknown_export_format_is_handled(self):
        self.client.force_login(self.staff)
        response = self.client.get(
            reverse("students:student_list"), {"export": 1, "format": "exe"}
        )
        self.assertIn(response.status_code, [200, 302])


class StudentCreationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        from accounts.models import User
        from academics.models import Department

        cls.admin = User.objects.create_superuser(username="creator", password="x")
        cls.department = Department.objects.create(code="CSE", name="Computer Science")

    def test_student_can_be_added_from_the_ui(self):
        from academics.models import Course, Semester
        from students.models import Student

        course = Course.objects.create(
            code="BTCS", name="B.Tech CS", department=self.department, total_semesters=8
        )
        semester = Semester.objects.create(number=1, name="Semester 1")
        self.client.force_login(self.admin)
        response = self.client.post(
            reverse("students:student_add"),
            {
                "first_name": "Aarav",
                "email": "aarav.form@example.com",
                "phone": "9812300070",
                "date_of_birth": date(2004, 4, 4).isoformat(),
                "gender": "M",
                "nationality": "Indian",
                "admission_date": date(2023, 7, 1).isoformat(),
                "department": self.department.pk,
                "course": course.pk,
                "semester": semester.pk,
                "status": "ACTIVE",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Student.objects.filter(email="aarav.form@example.com").exists())