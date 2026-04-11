"""Pure date arithmetic for yinv.

All functions operate on (year, month) tuples we call a "service month" — the
canonical "which month is this invoice for" identifier stored in each YAML.
"""

from __future__ import annotations

import calendar
from datetime import date

ServiceMonth = tuple[int, int]

_MONTH_NAMES = (
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
)


def parse_service_month(value: str) -> ServiceMonth:
    """Parse a ``YYYY-MM`` string into ``(year, month)``.

    Rejects non-strings (guards against YAML auto-parsing ``2026-04`` as a date
    object) and out-of-range months.
    """
    if not isinstance(value, str):
        raise ValueError(
            f"service_month must be a 'YYYY-MM' string, got {type(value).__name__}. "
            f"Quote the value in YAML, e.g. service_month: \"2026-04\"."
        )
    parts = value.split("-")
    if len(parts) != 2:
        raise ValueError(f"service_month must be 'YYYY-MM', got {value!r}")
    year_str, month_str = parts
    if len(year_str) != 4 or len(month_str) != 2:
        raise ValueError(f"service_month must be 'YYYY-MM', got {value!r}")
    try:
        year = int(year_str)
        month = int(month_str)
    except ValueError as exc:
        raise ValueError(f"service_month must be 'YYYY-MM', got {value!r}") from exc
    if not (1 <= month <= 12):
        raise ValueError(f"service_month month out of range 1..12, got {value!r}")
    return year, month


def format_service_month(sm: ServiceMonth) -> str:
    """Render ``(year, month)`` back to a ``YYYY-MM`` string."""
    year, month = sm
    return f"{year:04d}-{month:02d}"


def next_service_month(sm: ServiceMonth) -> ServiceMonth:
    """Return the service month one month after ``sm``, handling year rollover."""
    year, month = sm
    if month == 12:
        return year + 1, 1
    return year, month + 1


def last_day_of_service_month(sm: ServiceMonth) -> date:
    """Return the last calendar day of ``sm`` as a ``date``."""
    year, month = sm
    _, last = calendar.monthrange(year, month)
    return date(year, month, last)


def due_date_for_service_month(sm: ServiceMonth) -> date:
    """Return the 15th of the month *after* ``sm``."""
    next_year, next_month = next_service_month(sm)
    return date(next_year, next_month, 15)


def month_name(month: int) -> str:
    """Return the English name of ``month`` (1..12)."""
    if not (1 <= month <= 12):
        raise ValueError(f"month out of range 1..12, got {month}")
    return _MONTH_NAMES[month - 1]
