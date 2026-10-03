"""Tests for notification visibility, reading and announcement delivery."""

from datetime import date, timedelta

from django.test import TestCase
from django.utils import timezone

from notifications.models import Notification, NotificationRead, StudentAnnouncement


class NotificationTestBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        from accounts.models import User
        from academics.models import Course, Department

        cls.admin = User.objects.create_superuser(
            username="notif_admin", password="x", role=User.Role.ADMIN
        )
        cls.staff = User.objects.create_user(
            username="notif_staff", password="x", role=User.Role.STAFF, is_staff=True
        )
        cls.department = Department.objects.create(code="CSE", name="Computer Science")
        cls.course = Course.objects.create(
            code="BTCS", name="B.Tech CS", department=cls.department, total_semesters=8
        )

    def notify(self, **kwargs):
        kwargs.setdefault("title", f"Notice {timezone.now().timestamp()}")
        kwargs.setdefault("body", "Body text")
        kwargs.setdefault("created_by", self.admin)
        return Notification.objects.create(**kwargs)


class ActiveScopeTests(NotificationTestBase):
    def test_expired_notifications_are_hidden(self):
        expired = self.notify(expires_at=timezone.now() - timedelta(days=1))
        fresh = self.notify(expires_at=timezone.now() + timedelta(days=1))
        active_ids = list(Notification.objects.active().values_list("id", flat=True))
        self.assertNotIn(expired.pk, active_ids)
        self.assertIn(fresh.pk, active_ids)

    def test_inactive_notifications_are_hidden(self):
        hidden = self.notify(is_active=False)
        self.assertNotIn(hidden.pk, Notification.objects.active().values_list("id", flat=True))

    def test_notice_without_expiry_stays_active(self):
        notice = self.notify(expires_at=None)
        self.assertIn(notice.pk, Notification.objects.active().values_list("id", flat=True))


class VisibilityTests(NotificationTestBase):
    def test_anonymous_users_see_nothing(self):
        self.notify(audience=Notification.Audience.ALL)

        class Anonymous:
            is_authenticated = False

        self.assertEqual(Notification.objects.visible_to(Anonymous()).count(), 0)

    def test_internal_users_see_staff_and_admin_notices(self):
        self.notify(audience=Notification.Audience.ALL)
        self.notify(audience=Notification.Audience.STAFF)
        self.notify(audience=Notification.Audience.ADMIN)
        titles = set(
            Notification.objects.visible_to(self.staff).values_list("audience", flat=True)
        )
        self.assertIn(Notification.Audience.STAFF, titles)
        self.assertIn(Notification.Audience.ALL, titles)
        self.assertIn(Notification.Audience.ADMIN, titles)


class ReadTrackingTests(NotificationTestBase):
    def test_mark_all_read_creates_one_read_row(self):
        first = self.notify(audience=Notification.Audience.ALL)
        second = self.notify(audience=Notification.Audience.ALL)
        created = Notification.objects.mark_all_read(self.staff)
        self.assertEqual(created, 2)
        self.assertEqual(
            NotificationRead.objects.filter(user=self.staff).count(), 2
        )
        self.assertEqual(Notification.objects.unread_for(self.staff).count(), 0)
        first.refresh_from_db()
        second.refresh_from_db()
        self.assertEqual(first.read_count, 1)
        self.assertEqual(second.read_count, 1)

    def test_mark_all_read_is_idempotent(self):
        self.notify(audience=Notification.Audience.ALL)
        Notification.objects.mark_all_read(self.staff)
        self.assertEqual(Notification.objects.mark_all_read(self.staff), 0)


class StudentAnnouncementTests(NotificationTestBase):
    def make_student(self, email="diya@example.com", phone="9812300040"):
        from academics.models import Batch, Semester
        from students.models import Student

        batch, _ = Batch.objects.get_or_create(
            name="2023-2027",
            defaults={"start_year": 2023, "end_year": 2027, "department": self.department},
        )
        semester, _ = Semester.objects.get_or_create(number=1, defaults={"name": "Semester 1"})
        return Student.objects.create(
            first_name="Diya",
            email=email,
            phone=phone,
            date_of_birth=date(2004, 6, 6),
            admission_date=date(2023, 7, 1),
            department=self.department,
            course=self.course,
            batch=batch,
            semester=semester,
            created_by=self.admin,
        )

    def test_announcement_is_visible_to_its_student(self):
        student = self.make_student()
        announcement = StudentAnnouncement.objects.create(
            student=student,
            title="Holiday notice",
            message="School closed on Monday.",
            created_by=self.admin,
        )
        visible = StudentAnnouncement.objects.filter(student=student)
        self.assertIn(announcement, visible)

    def test_students_do_not_see_other_students_announcements(self):
        first = self.make_student()
        other = self.make_student(email="other@example.com", phone="9812300041")
        StudentAnnouncement.objects.create(
            student=first, title="Private", message="Only for me", created_by=self.admin
        )
        visible = StudentAnnouncement.objects.filter(student=other)
        self.assertEqual(visible.count(), 0)

    def test_notify_student_pins_notice_to_profile(self):
        from notifications.services import notify_student

        student = self.make_student()
        announcement = notify_student(
            student, "Exam schedule", "Starts Monday.", created_by=self.admin
        )
        self.assertEqual(announcement.student, student)
        self.assertTrue(
            StudentAnnouncement.objects.filter(student=student, title="Exam schedule").exists()
        )

    def test_broadcast_copies_notice_to_target_students(self):
        from notifications.services import broadcast

        student = self.make_student()
        notice = self.notify(
            title="College closed",
            body="Due to weather.",
            audience=Notification.Audience.STUDENT,
        )
        created = broadcast(notice)
        self.assertEqual(created, 1)
        self.assertTrue(
            StudentAnnouncement.objects.filter(student=student, notification=notice).exists()
        )

    def test_broadcast_skips_staff_only_notices(self):
        from notifications.services import broadcast

        notice = self.notify(
            title="Staff meeting", body="Only staff.", audience=Notification.Audience.STAFF
        )
        self.assertEqual(broadcast(notice), 0)