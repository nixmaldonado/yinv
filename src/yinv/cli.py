"""yinv command-line entry point."""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from datetime import date
from pathlib import Path
from typing import Any

from yinv import __version__
from yinv.config import Config, UnknownConfigKey
from yinv.data import (
    ValidationError,
    client_dir,
    find_latest,
    fork_next,
    load_invoice,
    load_seed_template,
    save_invoice,
    target_path_for_service_month,
    validate_invoice,
)
from yinv.dates import (
    ServiceMonth,
    due_date_for_service_month,
    format_service_month,
    last_day_of_service_month,
    next_service_month,
    parse_service_month,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="yinv",
        description="Generate monthly consulting invoices as PDFs from YAML.",
    )
    parser.add_argument("--version", action="version", version=f"yinv {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    new = sub.add_parser(
        "new",
        help="Fork the latest invoice for the active client, or bootstrap the first one.",
    )
    new.add_argument(
        "--month",
        metavar="YYYY-MM",
        help="Target service month (default: latest+1, or current month if bootstrapping).",
    )
    new.add_argument(
        "--force",
        action="store_true",
        help="Overwrite an existing target YAML/PDF.",
    )

    render_cmd = sub.add_parser("render", help="Render one YAML file to PDF.")
    render_cmd.add_argument("yaml_path", type=Path)

    cfg = sub.add_parser("config", help="Read or write a config value.")
    cfg_sub = cfg.add_subparsers(dest="config_action", required=True)
    cfg_set = cfg_sub.add_parser("set", help="Write a config key.")
    cfg_set.add_argument("key")
    cfg_set.add_argument("value")
    cfg_get = cfg_sub.add_parser("get", help="Read a config key.")
    cfg_get.add_argument("key")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        if args.command == "new":
            return _cmd_new(args)
        if args.command == "render":
            return _cmd_render(args)
        if args.command == "config":
            return _cmd_config(args)
    except _UserError as exc:
        print(f"yinv: {exc}", file=sys.stderr)
        return exc.exit_code
    except ValidationError as exc:
        print(f"yinv: invalid invoice: {exc}", file=sys.stderr)
        return 2

    parser.error(f"unknown command {args.command!r}")
    return 2  # unreachable; parser.error exits


# --------------------------------------------------------------------------
# Commands
# --------------------------------------------------------------------------


class _UserError(Exception):
    """Expected, user-facing error. Printed without a traceback."""

    def __init__(self, message: str, *, exit_code: int = 1) -> None:
        super().__init__(message)
        self.exit_code = exit_code


def _cmd_config(args: argparse.Namespace) -> int:
    config = Config()
    try:
        if args.config_action == "set":
            config.set(args.key, args.value)
            print(f"{args.key} = {config.get(args.key)}")
            return 0
        if args.config_action == "get":
            value = config.get(args.key)
            if value is None:
                print("")
                return 0
            print(value)
            return 0
    except UnknownConfigKey as exc:
        raise _UserError(str(exc), exit_code=2) from exc
    except ValueError as exc:
        raise _UserError(str(exc), exit_code=2) from exc
    return 2  # unreachable — argparse enforces a subcommand


def _cmd_render(args: argparse.Namespace) -> int:
    # Import render lazily so `yinv --help` / `yinv config` don't need WeasyPrint.
    from yinv.render import render  # noqa: PLC0415

    yaml_path: Path = args.yaml_path
    if not yaml_path.exists():
        raise _UserError(f"{yaml_path}: file not found")

    # Validate before handing to WeasyPrint for a cleaner error message.
    invoice = load_invoice(yaml_path)
    validate_invoice(invoice)

    pdf_path = render(yaml_path)
    print(f"wrote {pdf_path}")
    return 0


def _cmd_new(args: argparse.Namespace) -> int:
    config = Config()
    invoices_dir = config.get("invoices.dir")
    client = config.get("client.default")
    if not invoices_dir:
        raise _UserError(
            "invoices.dir is not set. Run: "
            "yinv config set invoices.dir ~/Documents/Invoices"
        )
    if not client:
        raise _UserError(
            "client.default is not set. Run: "
            "yinv config set client.default <your-client-subdir-name>"
        )

    width = int(config.get("invoice_number.width") or 6)
    cdir = client_dir(Path(invoices_dir).expanduser(), client)
    cdir.mkdir(parents=True, exist_ok=True)

    latest = find_latest(cdir)
    explicit_month = _parse_optional_month(args.month)

    if latest is None:
        return _bootstrap_first_invoice(args, cdir, client, explicit_month, config)

    _, source = latest
    src_sm = parse_service_month(source["service_month"])
    target_sm: ServiceMonth = explicit_month or next_service_month(src_sm)
    target_path = target_path_for_service_month(cdir, target_sm)

    if target_path.exists() and not args.force:
        raise _UserError(
            f"{target_path} already exists (pass --force to overwrite)."
        )

    forked = fork_next(source, target_sm, width)
    save_invoice(forked, target_path)

    _open_in_editor(target_path, config)

    edited = load_invoice(target_path)
    validate_invoice(edited)

    # Render the PDF.
    from yinv.render import render  # noqa: PLC0415

    pdf_path = render(target_path)

    total = _grand_total(edited)
    currency = edited.get("currency", "USD")
    print(
        f"wrote {pdf_path} "
        f"(invoice #{edited['invoice_number']}, total {currency} {total:,})"
    )
    return 0


def _bootstrap_first_invoice(
    args: argparse.Namespace,
    cdir: Path,
    client: str,
    explicit_month: ServiceMonth | None,
    config: Config,
) -> int:
    today = date.today()
    target_sm: ServiceMonth = explicit_month or (today.year, today.month)
    target_path = target_path_for_service_month(cdir, target_sm)

    if target_path.exists() and not args.force:
        raise _UserError(
            f"{target_path} already exists (pass --force to overwrite)."
        )

    seed = load_seed_template()
    seed["client"] = client
    seed["service_month"] = format_service_month(target_sm)
    seed["date_of_issue"] = last_day_of_service_month(target_sm)
    seed["due_date"] = due_date_for_service_month(target_sm)
    save_invoice(seed, target_path)

    _open_in_editor(target_path, config)

    print(
        f"Seed written to {target_path}.\n"
        "Edit the placeholders, save, then run "
        f"'yinv render {target_path}' to generate the PDF.\n"
        "Next month, run 'yinv new' to fork from it."
    )
    return 0


def _parse_optional_month(value: str | None) -> ServiceMonth | None:
    if value is None:
        return None
    try:
        return parse_service_month(value)
    except ValueError as exc:
        raise _UserError(f"--month: {exc}", exit_code=2) from exc


def _open_in_editor(path: Path, config: Config) -> None:
    editor_cmd = (
        config.get("editor")
        or os.environ.get("VISUAL")
        or os.environ.get("EDITOR")
        or _default_editor()
    )
    try:
        subprocess.run([*editor_cmd.split(), str(path)], check=True)
    except FileNotFoundError as exc:
        raise _UserError(
            f"could not launch editor {editor_cmd!r}: {exc}. "
            "Set $EDITOR or 'yinv config set editor <cmd>'."
        ) from exc
    except subprocess.CalledProcessError as exc:
        raise _UserError(
            f"editor {editor_cmd!r} exited with status {exc.returncode}. "
            f"YAML left in place at {path}."
        ) from exc


def _default_editor() -> str:
    for candidate in ("vi", "nano"):
        if shutil.which(candidate):
            return candidate
    return "vi"  # fallback, likely present on any POSIX system


def _grand_total(invoice: dict[str, Any]) -> int | float:
    from decimal import Decimal  # noqa: PLC0415

    subtotal = Decimal("0")
    for item in invoice["line_items"]:
        subtotal += Decimal(str(item["unit_cost"])) * Decimal(str(item["qty"]))
    tax = subtotal * Decimal(str(invoice["tax_rate"])) / Decimal("100")
    total = subtotal + tax + Decimal(str(invoice["shipping"]))
    if total == total.to_integral_value():
        return int(total)
    return float(total)


if __name__ == "__main__":
    raise SystemExit(main())
