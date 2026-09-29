"""HTML + CSS → PDF rendering via Jinja2 + WeasyPrint."""

from __future__ import annotations

import calendar
from datetime import date
from decimal import Decimal
from importlib import resources
from pathlib import Path
from typing import Any

from jinja2 import Environment, StrictUndefined

from yinv.data import load_invoice, validate_invoice
from yinv.dates import last_day_of_service_month, parse_service_month


# Symbols for line-item and subtotal amounts ("$1,250.00"). Totals always use
# the ISO code instead ("USD 1,250.00"). Unknown codes fall back to code + space.
_CURRENCY_SYMBOLS = {
    "USD": "$",
    "EUR": "€",
    "GBP": "£",
    "ARS": "AR$",
}


def _format_date(value: date) -> str:
    """``Sep 30, 2026`` — month spelled out so day/month order can't be misread."""
    if not isinstance(value, date):
        raise TypeError(f"expected date, got {type(value).__name__}")
    return f"{calendar.month_abbr[value.month]} {value.day}, {value.year}"


def _format_service_period(service_month: str) -> str:
    """``Sep 1 – 30, 2026`` for a ``YYYY-MM`` service month."""
    year, month = parse_service_month(service_month)
    last = last_day_of_service_month((year, month)).day
    return f"{calendar.month_abbr[month]} 1 – {last}, {year}"


def _format_number(value: int | float) -> str:
    """Integer-looking values render without decimals; floats get 2 digits."""
    if isinstance(value, bool):
        raise TypeError("bool is not a valid invoice number")
    if isinstance(value, int) or (isinstance(value, float) and value.is_integer()):
        return f"{int(value):,}"
    return f"{value:,.2f}"


def _format_money(value: int | float, currency: str, with_code: bool = False) -> str:
    """``$1,250.00`` for amounts, ``USD 1,250.00`` for totals (``with_code``)."""
    if isinstance(value, bool):
        raise TypeError("bool is not a valid amount")
    prefix = f"{currency} " if with_code else _CURRENCY_SYMBOLS.get(currency, currency + " ")
    return f"{prefix}{value:,.2f}"


def _compute_totals(invoice: dict[str, Any]) -> tuple[float, float, float]:
    """Return ``(subtotal, tax, total)`` in the invoice's native numeric type.

    Uses Decimal internally to avoid float-rounding surprises on the grand
    total line, but returns floats (or ints) so Jinja formatting stays simple.
    """
    subtotal = Decimal("0")
    for item in invoice["line_items"]:
        subtotal += Decimal(str(item["unit_cost"])) * Decimal(str(item["qty"]))
    tax_rate = Decimal(str(invoice["tax_rate"]))
    shipping = Decimal(str(invoice["shipping"]))
    tax = subtotal * tax_rate / Decimal("100")
    total = subtotal + tax + shipping
    return _to_number(subtotal), _to_number(tax), _to_number(total)


def _to_number(d: Decimal) -> int | float:
    """Return ``int`` when ``d`` is integral, otherwise ``float``."""
    if d == d.to_integral_value():
        return int(d)
    return float(d)


def _load_template_text(filename: str) -> str:
    ref = resources.files("yinv").joinpath("templates", filename)
    return ref.read_text(encoding="utf-8")


def render_html(invoice: dict[str, Any]) -> str:
    """Render the Jinja template against ``invoice`` and return the HTML string.

    Separated from :func:`render` so tests can exercise the template pipeline
    without invoking WeasyPrint.
    """
    validate_invoice(invoice)
    env = Environment(
        autoescape=True,
        undefined=StrictUndefined,
        trim_blocks=True,
        lstrip_blocks=True,
    )
    template_text = _load_template_text("invoice.html.jinja")
    template = env.from_string(template_text)

    subtotal, tax, total = _compute_totals(invoice)
    css = _load_template_text("invoice.css")
    html = template.render(
        invoice=invoice,
        subtotal=subtotal,
        tax=tax,
        total=total,
        format_date=_format_date,
        format_service_period=_format_service_period,
        format_number=_format_number,
        format_money=_format_money,
    )
    # Inline the stylesheet so WeasyPrint doesn't need base_url resolution.
    html = html.replace(
        '<link rel="stylesheet" href="invoice.css">',
        f"<style>{css}</style>",
    )
    return html


def render(yaml_path: Path) -> Path:
    """Load ``yaml_path``, render, and write ``<same-stem>.pdf``. Return the PDF path."""
    yaml_path = Path(yaml_path)
    invoice = load_invoice(yaml_path)
    html = render_html(invoice)

    # Import WeasyPrint lazily so test modules that only touch pure logic
    # don't need it installed.
    from weasyprint import HTML  # noqa: PLC0415

    pdf_path = yaml_path.with_suffix(".pdf")
    HTML(string=html).write_pdf(str(pdf_path))
    return pdf_path
