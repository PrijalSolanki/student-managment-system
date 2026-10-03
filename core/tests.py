"""Tests for shared helpers, settings singleton and code generation."""

from datetime import date

from django.test import RequestFactory, TestCase

from core.models import AuditLog, SiteSetting
from core.utils import (
    build_query_string,
    generate_code,
    month_bounds,
    parse_date,
    percent,
    rows_to_csv,
)


class SiteSettingTests(TestCase):
    def test_load_is_a_singleton(self):
        first = SiteSetting.load()
        second = SiteSetting.load()
        self.assertEqual(first.pk, 1)
        self.assertEqual(SiteSetting.objects.count(), 1)
        self.assertEqual(first.pk, second.pk)

    def test_save_forces_pk_one(self):
        row = SiteSetting(institute_name="Demo College")
        row.save()
        self.assertEqual(row.pk, 1)
        self.assertEqual(SiteSetting.objects.count(), 1)


class GenerateCodeTests(TestCase):
    def test_first_code_is_padded(self):
        from accounts.models import User

        self.assertEqual(generate_code("EMP", User, field="username", width=4), "EMP0001")

    def test_codes_increment_from_the_newest_row(self):
        from accounts.models import User

        User.objects.create_user(username="EMP0001", password="x")
        User.objects.create_user(username="EMP0002", password="x")
        self.assertEqual(generate_code("EMP", User, field="username", width=4), "EMP0003")

    def test_non_numeric_existing_code_restarts_at_one(self):
        from accounts.models import User

        User.objects.create_user(username="root", password="x")
        self.assertEqual(generate_code("EMP", User, field="username", width=4), "EMP0001")


class ParseDateTests(TestCase):
    def test_supported_formats(self):
        self.assertEqual(parse_date("2024-05-04"), date(2024, 5, 4))
        self.assertEqual(parse_date("04/05/2024"), date(2024, 5, 4))

    def test_blank_and_garbage_return_none(self):
        self.assertIsNone(parse_date(""))
        self.assertIsNone(parse_date("not-a-date"))


class MonthBoundsTests(TestCase):
    def test_first_and_last_day(self):
        self.assertEqual(month_bounds(2024, 2), (date(2024, 2, 1), date(2024, 2, 29)))
        self.assertEqual(month_bounds(2023, 2), (date(2023, 2, 1), date(2023, 2, 28)))


class PercentTests(TestCase):
    def test_normal(self):
        self.assertEqual(percent(3, 4), 75.0)

    def test_zero_denominator(self):
        self.assertEqual(percent(0, 0), 0.0)


class QueryStringHelperTests(TestCase):
    def test_empty_values_are_dropped(self):
        built = build_query_string({"q": "abc", "status": "", "page": None, "gender": "all"})
        self.assertEqual(built, "q=abc")


class CsvTests(TestCase):
    def test_utf8_bom_and_header(self):
        payload = rows_to_csv(["Name", "Amount"], [["Aarav", 10]])
        self.assertTrue(payload.startswith(b"\xef\xbb\xbf"))
        self.assertIn(b"Name,Amount", payload)


class PaginateTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def test_defaults_to_first_page(self):
        from django.contrib.auth.models import AnonymousUser

        from core.utils import paginate

        request = self.factory.get("/students/")
        request.user = AnonymousUser()
        page = paginate(request, list(range(25)), per_page=10)
        self.assertEqual(page.number, 1)
        self.assertEqual(len(page.object_list), 10)

    def test_out_of_range_page_clamps(self):
        from django.contrib.auth.models import AnonymousUser

        from core.utils import paginate

        request = self.factory.get("/students/?page=99")
        request.user = AnonymousUser()
        page = paginate(request, list(range(25)), per_page=10)
        self.assertEqual(page.number, 3)


class AuditLogTests(TestCase):
    def test_action_choices_available(self):
        self.assertEqual(AuditLog.Action.CREATE, "CREATE")
        self.assertIn("EXPORT", [action for action, _ in AuditLog.Action.choices])