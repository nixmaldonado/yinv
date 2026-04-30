"""Config read/write for yinv.

Backed by a TOML file at ``~/.config/yinv/config.toml``. Keys are dotted
(e.g. ``invoices.dir``, ``client.default``) and map to a nested TOML structure.

A fixed whitelist of known keys is enforced so typos fail loudly rather than
silently persisting into the config file.
"""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# Sentinel unique enough not to collide with any real default.
_MISSING = object()


@dataclass(frozen=True)
class _KeySpec:
    """Specification for a known config key."""

    default: Any
    coerce: type | None = None  # if set, values are coerced through this callable
    description: str = ""


# Whitelisted keys. Adding a new key here is how we grow the config surface.
_KEYS: dict[str, _KeySpec] = {
    "invoices.dir": _KeySpec(
        default=None,
        coerce=str,
        description="Parent directory containing one subdir per client.",
    ),
    "client.default": _KeySpec(
        default=None,
        coerce=str,
        description="Client subdirectory to use when running `yinv new`.",
    ),
    "editor": _KeySpec(
        default=None,
        coerce=str,
        description="Command used to open YAML drafts (default: $VISUAL / $EDITOR / vi).",
    ),
    "currency": _KeySpec(
        default="USD",
        coerce=str,
        description="Currency code used in invoices (default: USD).",
    ),
    "invoice_number.width": _KeySpec(
        default=6,
        coerce=int,
        description="Minimum zero-padded width for invoice numbers (default: 6).",
    ),
}


def format_known_keys() -> str:
    """Return a multi-line, human-readable listing of known config keys.

    Used as the ``--help`` epilog for the ``config`` subcommands so users
    can discover which keys are actually configurable without leaving the
    terminal.
    """
    width = max(len(k) for k in _KEYS)
    lines = ["Configurable keys:"]
    for key, spec in _KEYS.items():
        lines.append(f"  {key:<{width}}  {spec.description}")
    lines.append("")
    lines.append(f"Config file: {default_config_path()}")
    return "\n".join(lines)


def default_config_path() -> Path:
    """Return the default config path: ``~/.config/yinv/config.toml``."""
    xdg = os.environ.get("XDG_CONFIG_HOME")
    base = Path(xdg) if xdg else Path.home() / ".config"
    return base / "yinv" / "config.toml"


class UnknownConfigKey(KeyError):
    """Raised when a dotted key is not in the whitelist."""


class Config:
    """A simple TOML-backed config with dotted-key access."""

    def __init__(self, path: Path | None = None) -> None:
        self._path = path or default_config_path()

    @property
    def path(self) -> Path:
        return self._path

    def known_keys(self) -> list[str]:
        return list(_KEYS.keys())

    def get(self, key: str) -> Any:
        spec = self._spec(key)
        data = self._load()
        value = _get_nested(data, key, _MISSING)
        if value is _MISSING:
            return spec.default
        if spec.coerce is not None and not isinstance(value, spec.coerce):
            try:
                value = spec.coerce(value)
            except (TypeError, ValueError) as exc:
                raise ValueError(
                    f"config key {key!r} has value {value!r} which cannot be "
                    f"coerced to {spec.coerce.__name__}"
                ) from exc
        return value

    def set(self, key: str, value: Any) -> None:
        spec = self._spec(key)
        if spec.coerce is not None:
            try:
                value = spec.coerce(value)
            except (TypeError, ValueError) as exc:
                raise ValueError(
                    f"config key {key!r} expects {spec.coerce.__name__}, "
                    f"could not coerce {value!r}"
                ) from exc
        data = self._load()
        _set_nested(data, key, value)
        self._save(data)

    # ------------------------------------------------------------------

    def _spec(self, key: str) -> _KeySpec:
        try:
            return _KEYS[key]
        except KeyError as exc:
            known = ", ".join(sorted(_KEYS))
            raise UnknownConfigKey(
                f"unknown config key {key!r}. Known keys: {known}"
            ) from exc

    def _load(self) -> dict[str, Any]:
        if not self._path.exists():
            return {}
        with self._path.open("rb") as fh:
            return tomllib.load(fh)

    def _save(self, data: dict[str, Any]) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(_dump_toml(data))


# --- helpers ---------------------------------------------------------------


def _get_nested(data: dict[str, Any], dotted: str, default: Any) -> Any:
    cursor: Any = data
    for part in dotted.split("."):
        if not isinstance(cursor, dict) or part not in cursor:
            return default
        cursor = cursor[part]
    return cursor


def _set_nested(data: dict[str, Any], dotted: str, value: Any) -> None:
    parts = dotted.split(".")
    cursor = data
    for part in parts[:-1]:
        node = cursor.get(part)
        if not isinstance(node, dict):
            node = {}
            cursor[part] = node
        cursor = node
    cursor[parts[-1]] = value


def _dump_toml(data: dict[str, Any]) -> str:
    """Tiny TOML writer covering the shapes we actually persist.

    stdlib ships ``tomllib`` (read-only) but no writer. Our config is a shallow
    nested dict of primitive values (str, int), so a hand-rolled dumper is
    simpler than adding ``tomli-w`` as a runtime dependency.
    """
    lines: list[str] = []
    _emit_section(data, prefix=(), lines=lines)
    return "\n".join(lines) + ("\n" if lines else "")


def _emit_section(
    data: dict[str, Any], prefix: tuple[str, ...], lines: list[str]
) -> None:
    # Emit scalar keys first, then nested tables.
    scalars = [(k, v) for k, v in data.items() if not isinstance(v, dict)]
    tables = [(k, v) for k, v in data.items() if isinstance(v, dict)]
    if scalars:
        if prefix:
            if lines:
                lines.append("")
            lines.append(f"[{'.'.join(prefix)}]")
        for k, v in scalars:
            lines.append(f"{k} = {_format_toml_value(v)}")
    for k, v in tables:
        _emit_section(v, prefix + (k,), lines)


def _format_toml_value(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, str):
        escaped = value.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'
    raise TypeError(f"unsupported config value type: {type(value).__name__}")
