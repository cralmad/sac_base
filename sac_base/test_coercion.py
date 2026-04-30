from datetime import date
from decimal import Decimal

from django.test import SimpleTestCase
from django.utils import timezone

from sac_base.coercion import parse_date, parse_datetime, parse_decimal, parse_int


class CoercionTests(SimpleTestCase):
    def test_parse_int_form(self):
        self.assertIsNone(parse_int(None))
        self.assertIsNone(parse_int(""))
        self.assertEqual(parse_int("42"), 42)
        self.assertIsNone(parse_int("x"))

    def test_parse_int_csv(self):
        self.assertIsNone(parse_int("", context="csv"))
        self.assertIsNone(parse_int("  ", context="csv"))
        self.assertEqual(parse_int("10.0", context="csv"), 10)

    def test_parse_date(self):
        self.assertIsNone(parse_date(""))
        self.assertEqual(parse_date("2024-03-15"), date(2024, 3, 15))
        self.assertIsNone(parse_date("bad"))

    def test_parse_decimal_form(self):
        self.assertIsNone(parse_decimal(""))
        self.assertEqual(parse_decimal("1,5"), Decimal("1.5"))

    def test_parse_datetime_form_local(self):
        dt = parse_datetime("2024-06-01T14:30", context="form")
        self.assertIsNotNone(dt)
        self.assertTrue(timezone.is_aware(dt))

    def test_parse_datetime_csv(self):
        dt = parse_datetime("2024-06-01 08:00:00", context="csv")
        self.assertIsNotNone(dt)
        self.assertTrue(timezone.is_aware(dt))
        dt_day = parse_datetime("2024-06-01", context="csv")
        self.assertIsNotNone(dt_day)
