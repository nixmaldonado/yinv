"""Tests for yinv.render — formatters and the HTML template (no WeasyPrint)."""

from datetime import date
from pathlib import Path

import pytest

from yinv.data import ValidationError, load_invoice
from yinv.render import (
    _format_date,
    _format_money,
    _format_service_period,
    render_html,
)


FIXTURE = Path(__file__).parent / "fixtures" / "example.yaml"


@pytest.fixture
def invoice():
    return load_invoice(FIXTURE)


# --------------------------------------------------------------------------
# Formatters
# --------------------------------------------------------------------------


class TestFormatDate:
    def test_spells_out_month(self):
        assert _format_date(date(2026, 9, 30)) == "Sep 30, 2026"

    def test_single_digit_day_is_not_padded(self):
        assert _format_date(date(2026, 10, 5)) == "Oct 5, 2026"

    def test_rejects_non_date(self):
        with pytest.raises(TypeError):
            _format_date("2026-09-30")


class TestFormatServicePeriod:
    def test_thirty_day_month(self):
        assert _format_service_period("2026-09") == "Sep 1 – 30, 2026"

    def test_leap_february(self):
        assert _format_service_period("2028-02") == "Feb 1 – 29, 2028"


class TestFormatMoney:
    def test_symbol_with_cents(self):
        assert _format_money(1250, "USD") == "$1,250.00"

    def test_with_code_uses_iso_code(self):
        assert _format_money(1250, "USD", with_code=True) == "USD 1,250.00"

    def test_rounds_fractional_amounts(self):
        assert _format_money(1234.5, "EUR") == "€1,234.50"

    def test_unknown_currency_falls_back_to_code(self):
        assert _format_money(10, "CHF") == "CHF 10.00"

    def test_rejects_bool(self):
        with pytest.raises(TypeError):
            _format_money(True, "USD")


# --------------------------------------------------------------------------
# Template
# --------------------------------------------------------------------------


class TestRenderHtml:
    def test_shows_amount_due_and_dates(self, invoice):
        html = render_html(invoice)
        assert "USD 6,050.00" in html
        assert "Apr 30, 2026" in html
        assert "May 15, 2026" in html
        assert "Apr 1 – 30, 2026" in html

    def test_hides_zero_tax_shipping_and_empty_po(self, invoice):
        html = render_html(invoice)
        assert "Tax (" not in html
        assert "Shipping" not in html
        assert "PO number" not in html

    def test_shows_tax_shipping_and_po_when_set(self, invoice):
        invoice.update(tax_rate=10, shipping=25, purchase_order="PO-42")
        html = render_html(invoice)
        assert "Tax (10%)" in html
        assert "$605.00" in html
        assert "Shipping" in html
        assert "PO-42" in html
        assert "USD 6,680.00" in html

    def test_renders_without_purchase_order_key(self, invoice):
        del invoice["purchase_order"]
        assert "PO number" not in render_html(invoice)

    def test_email_is_optional(self, invoice):
        assert "jane@example.com" not in render_html(invoice)
        invoice["from"]["email"] = "jane@example.com"
        assert "jane@example.com" in render_html(invoice)

    def test_empty_email_is_rejected(self, invoice):
        invoice["from"]["email"] = ""
        with pytest.raises(ValidationError, match="from.email"):
            render_html(invoice)

    def test_terms_shown_only_when_set(self, invoice):
        assert "Thank you!" in render_html(invoice)
        invoice["terms"] = ""
        assert "Thank you!" not in render_html(invoice)

    def test_stylesheet_is_inlined_unescaped(self, invoice):
        html = render_html(invoice)
        assert '<link rel="stylesheet"' not in html
        assert '"Helvetica Neue"' in html
