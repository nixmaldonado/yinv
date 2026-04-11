"""Invoice data: schema validation, YAML I/O, find-latest, fork-next.

One invoice = one YAML file under ``{invoices.dir}/{client}/{year}/``.

The schema is enforced by :func:`validate_invoice` rather than a third-party
validator — it's tight enough that pulling in ``pydantic``/``jsonschema`` would
be dead weight (more brew ``resource`` blocks for no real benefit).
"""

from __future__ import annotations

import copy
import re
from datetime import date
from importlib import resources
from pathlib import Path
from typing import Any

import yaml

from yinv.dates import (
    ServiceMonth,
    due_date_for_service_month,
    format_service_month,
    last_day_of_service_month,
    month_name,
    parse_service_month,
)


class ValidationError(ValueError):
    """Raised when an invoice dict fails schema validation."""


# --------------------------------------------------------------------------
# Path helpers
# --------------------------------------------------------------------------


def client_dir(invoices_dir: Path, client: str) -> Path:
    """Return ``{invoices_dir}/{client}`` as a Path (not created)."""
    return Path(invoices_dir) / client


def target_path_for_service_month(
    client_dir_path: Path, service_month: ServiceMonth
) -> Path:
    """Return the canonical YAML path for a given service month.

    ``{client_dir}/{year}/{MonthName}{year}.yaml``.
    """
    year, month = service_month
    return client_dir_path / str(year) / f"{month_name(month)}{year}.yaml"


# --------------------------------------------------------------------------
# Schema
# --------------------------------------------------------------------------


_REQUIRED_TOP_LEVEL = (
    "client",
    "invoice_number",
    "service_month",
    "date_of_issue",
    "due_date",
    "billed_to",
    "from",
    "line_items",
    "terms",
    "tax_rate",
    "shipping",
    "currency",
    "bank_details",
)

_REQUIRED_BILLED_TO = ("name", "address")
_REQUIRED_FROM = ("name", "address")
_REQUIRED_BANK = (
    "name",
    "account_number",
    "account_type",
    "routing_number",
    "swift_bic",
    "bank_name",
    "bank_address",
)


def validate_invoice(invoice: Any) -> None:
    """Raise :class:`ValidationError` unless ``invoice`` matches the schema."""
    if not isinstance(invoice, dict):
        raise ValidationError(f"invoice must be a mapping, got {type(invoice).__name__}")

    missing = [k for k in _REQUIRED_TOP_LEVEL if k not in invoice]
    if missing:
        raise ValidationError(f"missing required field(s): {', '.join(missing)}")

    if not isinstance(invoice["client"], str) or not invoice["client"]:
        raise ValidationError("client must be a non-empty string")

    if not isinstance(invoice["invoice_number"], str) or not invoice["invoice_number"]:
        raise ValidationError(
            "invoice_number must be a non-empty string (quote it in YAML to "
            "preserve leading zeros)"
        )

    try:
        parse_service_month(invoice["service_month"])
    except ValueError as exc:
        raise ValidationError(f"service_month: {exc}") from exc

    for fld in ("date_of_issue", "due_date"):
        if not isinstance(invoice[fld], date):
            raise ValidationError(
                f"{fld} must be a date (YAML auto-parses YYYY-MM-DD)"
            )

    for section, required in (
        ("billed_to", _REQUIRED_BILLED_TO),
        ("from", _REQUIRED_FROM),
        ("bank_details", _REQUIRED_BANK),
    ):
        block = invoice[section]
        if not isinstance(block, dict):
            raise ValidationError(f"{section} must be a mapping")
        missing = [k for k in required if k not in block]
        if missing:
            raise ValidationError(
                f"{section} missing required field(s): {', '.join(missing)}"
            )

    for section in ("billed_to", "from"):
        addr = invoice[section]["address"]
        if not isinstance(addr, list) or not addr:
            raise ValidationError(f"{section}.address must be a non-empty list")

    if not isinstance(invoice["bank_details"]["bank_address"], list):
        raise ValidationError("bank_details.bank_address must be a list")

    items = invoice["line_items"]
    if not isinstance(items, list) or not items:
        raise ValidationError("line_items must be a non-empty list")
    for idx, item in enumerate(items):
        if not isinstance(item, dict):
            raise ValidationError(f"line_items[{idx}] must be a mapping")
        for fld in ("description", "unit_cost", "qty"):
            if fld not in item:
                raise ValidationError(f"line_items[{idx}] missing {fld}")
        if not isinstance(item["description"], str):
            raise ValidationError(f"line_items[{idx}].description must be a string")
        if not isinstance(item["unit_cost"], (int, float)) or isinstance(
            item["unit_cost"], bool
        ):
            raise ValidationError(f"line_items[{idx}].unit_cost must be numeric")
        if not isinstance(item["qty"], (int, float)) or isinstance(item["qty"], bool):
            raise ValidationError(f"line_items[{idx}].qty must be numeric")

    for fld in ("tax_rate", "shipping"):
        if not isinstance(invoice[fld], (int, float)) or isinstance(invoice[fld], bool):
            raise ValidationError(f"{fld} must be numeric")


# --------------------------------------------------------------------------
# YAML I/O
# --------------------------------------------------------------------------


class _YinvDumper(yaml.SafeDumper):
    """Custom dumper that keeps leading zeros on invoice_number by quoting strings."""


def _str_representer(dumper: yaml.SafeDumper, data: str) -> yaml.ScalarNode:
    # Quote strings that look numeric so e.g. "000007" round-trips.
    if data.isdigit() and data.startswith("0"):
        return dumper.represent_scalar("tag:yaml.org,2002:str", data, style='"')
    return dumper.represent_scalar("tag:yaml.org,2002:str", data)


_YinvDumper.add_representer(str, _str_representer)


def load_invoice(path: Path) -> dict[str, Any]:
    """Load a YAML invoice file as a dict."""
    with Path(path).open("r") as fh:
        data = yaml.safe_load(fh)
    if not isinstance(data, dict):
        raise ValidationError(f"{path}: expected a YAML mapping at top level")
    # Coerce service_month back to string if YAML auto-parsed it as a date.
    # (YAML will not parse "2026-04" as a date — only "2026-04-01" — but guard anyway.)
    if isinstance(data.get("service_month"), date):
        d = data["service_month"]
        data["service_month"] = f"{d.year:04d}-{d.month:02d}"
    return data


def save_invoice(invoice: dict[str, Any], path: Path) -> None:
    """Serialize an invoice dict to YAML at ``path`` (parents created)."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as fh:
        yaml.dump(
            invoice,
            fh,
            Dumper=_YinvDumper,
            sort_keys=False,
            default_flow_style=False,
            allow_unicode=True,
        )


# --------------------------------------------------------------------------
# find_latest
# --------------------------------------------------------------------------


def find_latest(client_dir_path: Path) -> tuple[Path, dict[str, Any]] | None:
    """Return ``(path, invoice)`` with the most-recent ``service_month`` under
    ``client_dir_path``, or ``None`` if no parseable YAML is found.

    Scoped to one client dir: other clients are invisible.
    """
    client_dir_path = Path(client_dir_path)
    if not client_dir_path.is_dir():
        return None

    best: tuple[ServiceMonth, Path, dict[str, Any]] | None = None
    for yaml_path in client_dir_path.rglob("*.yaml"):
        try:
            invoice = load_invoice(yaml_path)
            validate_invoice(invoice)
            sm = parse_service_month(invoice["service_month"])
        except (ValidationError, ValueError, KeyError, yaml.YAMLError):
            continue
        if best is None or sm > best[0]:
            best = (sm, yaml_path, invoice)
    if best is None:
        return None
    return best[1], best[2]


# --------------------------------------------------------------------------
# Month-token substitution — deliberately narrow
# --------------------------------------------------------------------------


def substitute_month_tokens(
    text: str,
    src_month_name: str,
    src_year: int,
    dst_month_name: str,
    dst_year: int,
) -> str:
    """Replace exact ``<SrcMonth> <SrcYear>`` tokens with ``<DstMonth> <DstYear>``.

    - Case-insensitive.
    - Word-boundary aware so ``Marching`` does not match ``March``.
    - Only replaces the literal "<month-name> <year>" pattern. Nothing else.
    """
    pattern = re.compile(
        rf"\b{re.escape(src_month_name)}\s+{src_year}\b",
        flags=re.IGNORECASE,
    )
    return pattern.sub(f"{dst_month_name} {dst_year}", text)


# --------------------------------------------------------------------------
# fork_next
# --------------------------------------------------------------------------


def fork_next(
    source: dict[str, Any],
    target_service_month: ServiceMonth,
    width: int,
) -> dict[str, Any]:
    """Fork ``source`` into the invoice for ``target_service_month``.

    - Bumps ``invoice_number`` by 1, zero-padded to ``width``.
    - Updates ``service_month``, ``date_of_issue`` (last day of target),
      ``due_date`` (15th of month after target).
    - Rewrites exact ``<SourceMonth> <SourceYear>`` tokens in line-item
      descriptions to ``<TargetMonth> <TargetYear>``.
    - Copies all other fields verbatim (including ``client``, ``bank_details``,
      ``billed_to``, ``from``, ``terms``, ``tax_rate``, ``shipping``,
      ``currency``, ``purchase_order``).

    Returns a new dict; does not mutate ``source``.
    """
    src_sm = parse_service_month(source["service_month"])
    src_month_name = month_name(src_sm[1])
    src_year = src_sm[0]
    dst_month_name = month_name(target_service_month[1])
    dst_year = target_service_month[0]

    out = copy.deepcopy(source)

    # Invoice number: bump and re-pad.
    try:
        next_num = int(source["invoice_number"]) + 1
    except (TypeError, ValueError) as exc:
        raise ValidationError(
            f"invoice_number must be numeric to bump, got {source['invoice_number']!r}"
        ) from exc
    out["invoice_number"] = f"{next_num:0{width}d}"

    out["service_month"] = format_service_month(target_service_month)
    out["date_of_issue"] = last_day_of_service_month(target_service_month)
    out["due_date"] = due_date_for_service_month(target_service_month)

    for item in out["line_items"]:
        item["description"] = substitute_month_tokens(
            item["description"], src_month_name, src_year, dst_month_name, dst_year
        )

    return out


# --------------------------------------------------------------------------
# Seed template
# --------------------------------------------------------------------------


def load_seed_template() -> dict[str, Any]:
    """Load the bundled ``seed.yaml`` placeholder as a dict.

    Uses ``importlib.resources`` so it works both from source and from an
    installed wheel.
    """
    ref = resources.files("yinv").joinpath("templates", "seed.yaml")
    with ref.open("r") as fh:
        data = yaml.safe_load(fh)
    if not isinstance(data, dict):
        raise ValidationError("seed.yaml: expected a YAML mapping at top level")
    if isinstance(data.get("service_month"), date):
        d = data["service_month"]
        data["service_month"] = f"{d.year:04d}-{d.month:02d}"
    return data
