"""Tests for yinv.data — schema, find-latest, fork-next."""

from datetime import date
from pathlib import Path

import pytest
import yaml

from yinv.data import (
    ValidationError,
    client_dir,
    find_latest,
    fork_next,
    load_invoice,
    load_seed_template,
    save_invoice,
    substitute_month_tokens,
    target_path_for_service_month,
    validate_invoice,
)


# --------------------------------------------------------------------------
# Fixtures
# --------------------------------------------------------------------------


def _base_invoice(**overrides):
    """Return a minimal synthetic-but-valid invoice dict."""
    invoice = {
        "client": "Acme",
        "invoice_number": "000006",
        "service_month": "2026-03",
        "date_of_issue": date(2026, 3, 31),
        "due_date": date(2026, 4, 15),
        "billed_to": {
            "name": "Acme Corp",
            "address": ["123 Example Ave", "Somewhere, CA 90000"],
        },
        "from": {
            "name": "Jane Doe",
            "address": ["45 Placeholder St", "Anytown", "00000"],
        },
        "purchase_order": None,
        "line_items": [
            {"description": "Consulting fees for March 2026", "unit_cost": 6000, "qty": 1},
            {"description": "Tech Allowance March 2026", "unit_cost": 50, "qty": 1},
        ],
        "terms": "Thank you!",
        "tax_rate": 0,
        "shipping": 0,
        "currency": "USD",
        "bank_details": {
            "name": "Jane Doe",
            "account_number": "0000000000",
            "account_type": "Checking",
            "routing_number": "000000000",
            "swift_bic": "TESTUS00",
            "bank_name": "Test Bank",
            "bank_address": ["1 Bank Plaza", "Anytown, 00000"],
        },
    }
    invoice.update(overrides)
    return invoice


@pytest.fixture
def invoices_dir(tmp_path):
    return tmp_path / "Invoices"


def _write(path: Path, invoice: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    save_invoice(invoice, path)
    return path


# --------------------------------------------------------------------------
# validate_invoice
# --------------------------------------------------------------------------


class TestValidate:
    def test_accepts_minimal_valid(self):
        validate_invoice(_base_invoice())  # no exception

    def test_rejects_missing_required(self):
        inv = _base_invoice()
        del inv["invoice_number"]
        with pytest.raises(ValidationError, match="invoice_number"):
            validate_invoice(inv)

    def test_rejects_bad_service_month(self):
        inv = _base_invoice(service_month="not-a-date")
        with pytest.raises(ValidationError, match="service_month"):
            validate_invoice(inv)

    def test_rejects_non_numeric_unit_cost(self):
        inv = _base_invoice()
        inv["line_items"][0]["unit_cost"] = "six thousand"
        with pytest.raises(ValidationError, match="unit_cost"):
            validate_invoice(inv)

    def test_rejects_empty_line_items(self):
        inv = _base_invoice(line_items=[])
        with pytest.raises(ValidationError, match="line_items"):
            validate_invoice(inv)


# --------------------------------------------------------------------------
# load / save round-trip
# --------------------------------------------------------------------------


class TestLoadSave:
    def test_roundtrip_preserves_fields(self, tmp_path):
        path = tmp_path / "March2026.yaml"
        save_invoice(_base_invoice(), path)
        loaded = load_invoice(path)
        assert loaded["invoice_number"] == "000006"
        assert loaded["service_month"] == "2026-03"
        assert loaded["line_items"][0]["description"] == "Consulting fees for March 2026"

    def test_save_preserves_invoice_number_leading_zeros(self, tmp_path):
        path = tmp_path / "test.yaml"
        save_invoice(_base_invoice(invoice_number="000007"), path)
        # Must remain a quoted string, not silently become the int 7
        text = path.read_text()
        assert '"000007"' in text or "'000007'" in text


# --------------------------------------------------------------------------
# substitute_month_tokens
# --------------------------------------------------------------------------


class TestSubstituteMonthTokens:
    def test_exact_match(self):
        out = substitute_month_tokens(
            "Consulting fees for March 2026", "March", 2026, "April", 2026
        )
        assert out == "Consulting fees for April 2026"

    def test_case_insensitive(self):
        out = substitute_month_tokens(
            "MARCH 2026 retainer", "March", 2026, "April", 2026
        )
        assert out == "April 2026 retainer"

    def test_no_match_left_alone(self):
        # No "March 2026" token present — returned unchanged
        out = substitute_month_tokens(
            "Custom consulting", "March", 2026, "April", 2026
        )
        assert out == "Custom consulting"

    def test_does_not_match_partial_month_name(self):
        # "Marching orders" must not be rewritten
        out = substitute_month_tokens(
            "Marching orders for 2026", "March", 2026, "April", 2026
        )
        assert out == "Marching orders for 2026"

    def test_does_not_match_wrong_year(self):
        # "March 2025" is not the token we're replacing
        out = substitute_month_tokens(
            "March 2025 work", "March", 2026, "April", 2026
        )
        assert out == "March 2025 work"

    def test_multiple_occurrences(self):
        out = substitute_month_tokens(
            "March 2026 and also March 2026 again",
            "March",
            2026,
            "April",
            2026,
        )
        assert out == "April 2026 and also April 2026 again"


# --------------------------------------------------------------------------
# target_path_for_service_month
# --------------------------------------------------------------------------


class TestTargetPath:
    def test_within_client_dir(self, invoices_dir):
        cdir = client_dir(invoices_dir, "Acme")
        p = target_path_for_service_month(cdir, (2026, 4))
        assert p == cdir / "2026" / "April2026.yaml"

    def test_december(self, invoices_dir):
        cdir = client_dir(invoices_dir, "Acme")
        p = target_path_for_service_month(cdir, (2026, 12))
        assert p == cdir / "2026" / "December2026.yaml"


# --------------------------------------------------------------------------
# find_latest — the multi-client-scoping proof
# --------------------------------------------------------------------------


class TestFindLatest:
    def test_none_when_empty(self, invoices_dir):
        cdir = client_dir(invoices_dir, "Acme")
        cdir.mkdir(parents=True)
        assert find_latest(cdir) is None

    def test_none_when_dir_missing(self, invoices_dir):
        cdir = client_dir(invoices_dir, "Acme")
        assert find_latest(cdir) is None

    def test_picks_latest_by_service_month(self, invoices_dir):
        cdir = client_dir(invoices_dir, "Acme")
        _write(cdir / "2026" / "January2026.yaml", _base_invoice(
            invoice_number="000001", service_month="2026-01",
            date_of_issue=date(2026, 1, 31), due_date=date(2026, 2, 15),
        ))
        _write(cdir / "2026" / "March2026.yaml", _base_invoice(
            invoice_number="000003", service_month="2026-03",
            date_of_issue=date(2026, 3, 31), due_date=date(2026, 4, 15),
        ))
        _write(cdir / "2026" / "February2026.yaml", _base_invoice(
            invoice_number="000002", service_month="2026-02",
            date_of_issue=date(2026, 2, 28), due_date=date(2026, 3, 15),
        ))
        latest = find_latest(cdir)
        assert latest is not None
        path, invoice = latest
        assert path.name == "March2026.yaml"
        assert invoice["invoice_number"] == "000003"

    def test_skips_newer_invalid_invoice(self, invoices_dir):
        cdir = client_dir(invoices_dir, "Acme")
        _write(cdir / "2026" / "February2026.yaml", _base_invoice(
            invoice_number="000002", service_month="2026-02",
            date_of_issue=date(2026, 2, 28), due_date=date(2026, 3, 15),
        ))
        broken = _base_invoice(
            invoice_number="000003", service_month="2026-03",
            date_of_issue=date(2026, 3, 31), due_date=date(2026, 4, 15),
        )
        del broken["invoice_number"]
        _write(cdir / "2026" / "March2026.yaml", broken)

        latest = find_latest(cdir)

        assert latest is not None
        path, invoice = latest
        assert path.name == "February2026.yaml"
        assert invoice["service_month"] == "2026-02"

    def test_scoped_per_client_isolation(self, invoices_dir):
        """Multi-client isolation proof: two clients, independent sequences."""
        acme = client_dir(invoices_dir, "Acme")
        widget = client_dir(invoices_dir, "WidgetCo")

        _write(acme / "2026" / "March2026.yaml", _base_invoice(
            client="Acme", invoice_number="000006", service_month="2026-03",
            date_of_issue=date(2026, 3, 31), due_date=date(2026, 4, 15),
        ))
        _write(widget / "2026" / "January2026.yaml", _base_invoice(
            client="WidgetCo", invoice_number="000001", service_month="2026-01",
            date_of_issue=date(2026, 1, 31), due_date=date(2026, 2, 15),
        ))

        # Each client sees only its own "latest"
        acme_latest = find_latest(acme)
        widget_latest = find_latest(widget)
        assert acme_latest is not None and widget_latest is not None
        assert acme_latest[1]["invoice_number"] == "000006"
        assert acme_latest[1]["client"] == "Acme"
        assert widget_latest[1]["invoice_number"] == "000001"
        assert widget_latest[1]["client"] == "WidgetCo"


# --------------------------------------------------------------------------
# fork_next — the main business logic
# --------------------------------------------------------------------------


class TestForkNext:
    def test_bumps_invoice_number(self):
        src = _base_invoice(invoice_number="000006")
        out = fork_next(src, target_service_month=(2026, 4), width=6)
        assert out["invoice_number"] == "000007"

    def test_respects_width(self):
        src = _base_invoice(invoice_number="00006")
        out = fork_next(src, target_service_month=(2026, 4), width=5)
        assert out["invoice_number"] == "00007"

    def test_updates_service_month(self):
        src = _base_invoice(service_month="2026-03")
        out = fork_next(src, target_service_month=(2026, 4), width=6)
        assert out["service_month"] == "2026-04"

    def test_updates_date_of_issue_to_last_day(self):
        src = _base_invoice()
        out = fork_next(src, target_service_month=(2026, 4), width=6)
        assert out["date_of_issue"] == date(2026, 4, 30)

    def test_updates_due_date_to_15th_of_next_month(self):
        src = _base_invoice()
        out = fork_next(src, target_service_month=(2026, 4), width=6)
        assert out["due_date"] == date(2026, 5, 15)

    def test_substitutes_month_in_line_items(self):
        src = _base_invoice()
        out = fork_next(src, target_service_month=(2026, 4), width=6)
        assert out["line_items"][0]["description"] == "Consulting fees for April 2026"
        assert out["line_items"][1]["description"] == "Tech Allowance April 2026"

    def test_leaves_non_matching_line_items_alone(self):
        src = _base_invoice()
        src["line_items"].append(
            {"description": "Custom work", "unit_cost": 100, "qty": 1}
        )
        out = fork_next(src, target_service_month=(2026, 4), width=6)
        assert out["line_items"][2]["description"] == "Custom work"

    def test_preserves_client_and_bank_details(self):
        src = _base_invoice()
        out = fork_next(src, target_service_month=(2026, 4), width=6)
        assert out["client"] == "Acme"
        assert out["bank_details"]["account_number"] == "0000000000"
        assert out["billed_to"]["name"] == "Acme Corp"

    def test_december_to_january_rollover(self):
        src = _base_invoice(
            invoice_number="000012",
            service_month="2026-12",
            date_of_issue=date(2026, 12, 31),
            due_date=date(2027, 1, 15),
            line_items=[
                {"description": "Consulting fees for December 2026", "unit_cost": 6000, "qty": 1},
            ],
        )
        out = fork_next(src, target_service_month=(2027, 1), width=6)
        assert out["invoice_number"] == "000013"
        assert out["service_month"] == "2027-01"
        assert out["date_of_issue"] == date(2027, 1, 31)
        assert out["due_date"] == date(2027, 2, 15)
        assert out["line_items"][0]["description"] == "Consulting fees for January 2027"

    def test_source_not_mutated(self):
        src = _base_invoice()
        original_number = src["invoice_number"]
        fork_next(src, target_service_month=(2026, 4), width=6)
        assert src["invoice_number"] == original_number

    def test_uses_service_month_not_date_of_issue(self):
        """Fork arithmetic must use service_month, not date_of_issue.

        An invoice issued late (e.g. April 2 for March work) still has
        service_month=2026-03, and fork should produce a 2026-04 invoice.
        """
        src = _base_invoice(
            service_month="2026-03",
            date_of_issue=date(2026, 4, 2),  # late issuance
        )
        out = fork_next(src, target_service_month=(2026, 4), width=6)
        assert out["service_month"] == "2026-04"


# --------------------------------------------------------------------------
# load_seed_template
# --------------------------------------------------------------------------


class TestSeedTemplate:
    def test_loads_and_parses(self):
        seed = load_seed_template()
        # The seed must itself be a valid schema (sanity check on the shipped file)
        validate_invoice(seed)

    def test_contains_obvious_placeholders(self):
        seed = load_seed_template()
        # Contract: user must be able to eyeball the placeholders
        blob = yaml.safe_dump(seed)
        assert "YOUR NAME" in blob or "Your Name" in blob


# --------------------------------------------------------------------------
# Synthetic fixture — proves example.yaml stays schema-valid
# --------------------------------------------------------------------------


class TestExampleFixture:
    def test_example_yaml_is_valid(self):
        fixture = Path(__file__).parent / "fixtures" / "example.yaml"
        invoice = load_invoice(fixture)
        validate_invoice(invoice)
