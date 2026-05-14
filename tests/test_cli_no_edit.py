"""Tests for `yinv new --no-edit` and `yinv new --client <name>`.

These guard the CLI contract that the bundled AI skill depends on:
- `--no-edit` must skip $EDITOR and skip auto-render.
- `--client` must override `client.default` per-command without mutating config.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from yinv.cli import main
from yinv.data import load_invoice


@pytest.fixture
def home(tmp_path, monkeypatch):
    """Isolate HOME so we don't read or write the user's real config."""
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(home / ".config"))
    return home


@pytest.fixture
def invoices_dir(tmp_path):
    d = tmp_path / "Invoices"
    d.mkdir()
    return d


@pytest.fixture
def configured(home, invoices_dir):
    """yinv config with invoices.dir set, no client.default."""
    main(["config", "set", "invoices.dir", str(invoices_dir)])
    return None


def _fail_editor(*_args, **_kwargs):
    raise AssertionError("editor was opened — --no-edit failed to suppress it")


def _fail_render(*_args, **_kwargs):
    raise AssertionError("render was called — --no-edit failed to suppress it")


class TestNoEditBootstrap:
    """First-time client with --no-edit: writes seed, no editor, no render."""

    def test_writes_seed_yaml_without_opening_editor(
        self, configured, invoices_dir, monkeypatch
    ):
        monkeypatch.setattr("yinv.cli._open_in_editor", _fail_editor)

        exit_code = main(
            ["new", "--client", "Acme", "--month", "2026-04", "--no-edit"]
        )

        assert exit_code == 0
        yaml_path = invoices_dir / "Acme" / "2026" / "April2026.yaml"
        assert yaml_path.exists()

    def test_does_not_render_pdf(self, configured, invoices_dir, monkeypatch):
        monkeypatch.setattr("yinv.cli._open_in_editor", _fail_editor)
        monkeypatch.setattr("yinv.render.render", _fail_render)

        exit_code = main(
            ["new", "--client", "Acme", "--month", "2026-04", "--no-edit"]
        )

        assert exit_code == 0
        pdf_path = invoices_dir / "Acme" / "2026" / "April2026.pdf"
        assert not pdf_path.exists()

    def test_prints_wrote_yaml_path(
        self, configured, invoices_dir, monkeypatch, capsys
    ):
        monkeypatch.setattr("yinv.cli._open_in_editor", _fail_editor)

        main(["new", "--client", "Acme", "--month", "2026-04", "--no-edit"])

        captured = capsys.readouterr()
        expected_path = invoices_dir / "Acme" / "2026" / "April2026.yaml"
        assert f"wrote {expected_path}" in captured.out


class TestNoEditFork:
    """Subsequent month with --no-edit: forks from latest, no editor, no render."""

    def _seed_april(self, configured, invoices_dir, monkeypatch):
        monkeypatch.setattr("yinv.cli._open_in_editor", _fail_editor)
        main(["new", "--client", "Acme", "--month", "2026-04", "--no-edit"])
        # Fill in something resembling a real invoice so the next fork has a
        # valid source to roll forward.
        april_path = invoices_dir / "Acme" / "2026" / "April2026.yaml"
        invoice = load_invoice(april_path)
        invoice["invoice_number"] = "000007"
        from yinv.data import save_invoice  # noqa: PLC0415

        save_invoice(invoice, april_path)
        return april_path

    def test_forks_next_month_without_editor(
        self, configured, invoices_dir, monkeypatch
    ):
        self._seed_april(configured, invoices_dir, monkeypatch)

        exit_code = main(
            ["new", "--client", "Acme", "--month", "2026-05", "--no-edit"]
        )

        assert exit_code == 0
        may_path = invoices_dir / "Acme" / "2026" / "May2026.yaml"
        assert may_path.exists()
        forked = load_invoice(may_path)
        assert forked["invoice_number"] == "000008"
        assert forked["service_month"] == "2026-05"

    def test_does_not_render_pdf_when_forking(
        self, configured, invoices_dir, monkeypatch
    ):
        self._seed_april(configured, invoices_dir, monkeypatch)
        monkeypatch.setattr("yinv.render.render", _fail_render)

        exit_code = main(
            ["new", "--client", "Acme", "--month", "2026-05", "--no-edit"]
        )

        assert exit_code == 0
        may_pdf = invoices_dir / "Acme" / "2026" / "May2026.pdf"
        assert not may_pdf.exists()


class TestClientFlag:
    """--client overrides client.default per-command."""

    def test_uses_client_flag_when_default_unset(
        self, configured, invoices_dir, monkeypatch
    ):
        monkeypatch.setattr("yinv.cli._open_in_editor", _fail_editor)

        # No client.default set, but --client is sufficient.
        exit_code = main(
            ["new", "--client", "Spiff Co", "--month", "2026-04", "--no-edit"]
        )

        assert exit_code == 0
        assert (
            invoices_dir / "Spiff Co" / "2026" / "April2026.yaml"
        ).exists()

    def test_creates_brand_new_client_dir(
        self, configured, invoices_dir, monkeypatch
    ):
        monkeypatch.setattr("yinv.cli._open_in_editor", _fail_editor)

        main(
            ["new", "--client", "BrandNewClient", "--month", "2026-04", "--no-edit"]
        )

        # Brand-new client routes through the bootstrap path automatically.
        new_dir = invoices_dir / "BrandNewClient"
        assert new_dir.is_dir()
        assert (new_dir / "2026" / "April2026.yaml").exists()

    def test_overrides_client_default(
        self, configured, invoices_dir, monkeypatch
    ):
        monkeypatch.setattr("yinv.cli._open_in_editor", _fail_editor)
        main(["config", "set", "client.default", "Acme"])

        main(["new", "--client", "Spiff Co", "--month", "2026-04", "--no-edit"])

        # Should write to Spiff Co, NOT Acme.
        assert (
            invoices_dir / "Spiff Co" / "2026" / "April2026.yaml"
        ).exists()
        assert not (invoices_dir / "Acme").exists()

    def test_does_not_mutate_client_default_config(
        self, configured, invoices_dir, monkeypatch, capsys
    ):
        monkeypatch.setattr("yinv.cli._open_in_editor", _fail_editor)
        main(["config", "set", "client.default", "Acme"])
        capsys.readouterr()  # drop the "set" output

        main(["new", "--client", "Spiff Co", "--month", "2026-04", "--no-edit"])
        capsys.readouterr()

        main(["config", "get", "client.default"])
        captured = capsys.readouterr()
        assert captured.out.strip() == "Acme"

    def test_errors_when_both_client_default_and_flag_unset(
        self, configured, invoices_dir, monkeypatch, capsys
    ):
        monkeypatch.setattr("yinv.cli._open_in_editor", _fail_editor)

        exit_code = main(["new", "--month", "2026-04", "--no-edit"])

        assert exit_code == 1
        err = capsys.readouterr().err
        assert "client.default" in err
