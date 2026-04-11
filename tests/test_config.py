"""Tests for yinv.config — TOML-backed config with dotted keys."""

import pytest

from yinv.config import Config, UnknownConfigKey


@pytest.fixture
def config_path(tmp_path):
    return tmp_path / "config.toml"


def test_empty_when_file_missing(config_path):
    c = Config(config_path)
    assert c.get("invoices.dir") is None
    assert c.get("client.default") is None


def test_set_and_get_roundtrip(config_path):
    c = Config(config_path)
    c.set("invoices.dir", "/tmp/invoices")
    c.set("client.default", "Acme")

    # Fresh instance — must read from disk
    c2 = Config(config_path)
    assert c2.get("invoices.dir") == "/tmp/invoices"
    assert c2.get("client.default") == "Acme"


def test_set_creates_parent_dir(tmp_path):
    deep = tmp_path / "nested" / "dir" / "config.toml"
    c = Config(deep)
    c.set("invoices.dir", "/x")
    assert deep.exists()
    assert Config(deep).get("invoices.dir") == "/x"


def test_overwrite(config_path):
    c = Config(config_path)
    c.set("invoices.dir", "/a")
    c.set("invoices.dir", "/b")
    assert Config(config_path).get("invoices.dir") == "/b"


def test_rejects_unknown_key(config_path):
    c = Config(config_path)
    with pytest.raises(UnknownConfigKey):
        c.set("bogus.key", "x")
    with pytest.raises(UnknownConfigKey):
        c.get("bogus.key")


def test_known_keys_listable(config_path):
    c = Config(config_path)
    keys = c.known_keys()
    assert "invoices.dir" in keys
    assert "client.default" in keys
    assert "editor" in keys
    assert "currency" in keys
    assert "invoice_number.width" in keys


def test_defaults_when_unset(config_path):
    c = Config(config_path)
    # Keys with defaults return those defaults
    assert c.get("currency") == "USD"
    assert c.get("invoice_number.width") == 6
    # Keys without defaults return None
    assert c.get("invoices.dir") is None


def test_explicit_set_overrides_default(config_path):
    c = Config(config_path)
    c.set("currency", "EUR")
    assert Config(config_path).get("currency") == "EUR"


def test_invoice_number_width_coerced_to_int(config_path):
    c = Config(config_path)
    c.set("invoice_number.width", "8")
    assert Config(config_path).get("invoice_number.width") == 8
