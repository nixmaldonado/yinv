"""Tests for yinv.dates — pure date arithmetic."""

from datetime import date

import pytest

from yinv.dates import (
    due_date_for_service_month,
    last_day_of_service_month,
    month_name,
    next_service_month,
    parse_service_month,
)


class TestParseServiceMonth:
    def test_valid(self):
        assert parse_service_month("2026-04") == (2026, 4)

    def test_january(self):
        assert parse_service_month("2026-01") == (2026, 1)

    def test_december(self):
        assert parse_service_month("2026-12") == (2026, 12)

    def test_rejects_missing_month(self):
        with pytest.raises(ValueError):
            parse_service_month("2026")

    def test_rejects_out_of_range_month(self):
        with pytest.raises(ValueError):
            parse_service_month("2026-13")
        with pytest.raises(ValueError):
            parse_service_month("2026-00")

    def test_rejects_non_string(self):
        # date objects come through from YAML parsing — must reject
        with pytest.raises(ValueError):
            parse_service_month(date(2026, 4, 1))  # type: ignore[arg-type]


class TestNextServiceMonth:
    def test_middle_of_year(self):
        assert next_service_month((2026, 4)) == (2026, 5)

    def test_year_rollover(self):
        assert next_service_month((2026, 12)) == (2027, 1)

    def test_january(self):
        assert next_service_month((2026, 1)) == (2026, 2)


class TestLastDayOfServiceMonth:
    def test_31_day_month(self):
        assert last_day_of_service_month((2026, 3)) == date(2026, 3, 31)

    def test_30_day_month(self):
        assert last_day_of_service_month((2026, 4)) == date(2026, 4, 30)

    def test_february_common_year(self):
        assert last_day_of_service_month((2026, 2)) == date(2026, 2, 28)

    def test_february_leap_year(self):
        assert last_day_of_service_month((2028, 2)) == date(2028, 2, 29)

    def test_december(self):
        assert last_day_of_service_month((2026, 12)) == date(2026, 12, 31)


class TestDueDateForServiceMonth:
    def test_april_service_month(self):
        # April service -> due on May 15
        assert due_date_for_service_month((2026, 4)) == date(2026, 5, 15)

    def test_march_service_month(self):
        # March service -> due on April 15 (matches the real invoice pattern)
        assert due_date_for_service_month((2026, 3)) == date(2026, 4, 15)

    def test_december_service_month_rolls_year(self):
        # December service -> due on January 15 of the following year
        assert due_date_for_service_month((2026, 12)) == date(2027, 1, 15)


class TestMonthName:
    def test_january(self):
        assert month_name(1) == "January"

    def test_december(self):
        assert month_name(12) == "December"

    def test_april(self):
        assert month_name(4) == "April"

    def test_rejects_out_of_range(self):
        with pytest.raises(ValueError):
            month_name(0)
        with pytest.raises(ValueError):
            month_name(13)
