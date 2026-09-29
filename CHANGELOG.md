# Changelog

All notable changes to yinv will be documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.2.0] - 2026-09-29

### Added
- Optional `from.email` field, printed under your address in the header.

### Changed
- Redesigned PDF layout: issuer masthead, highlighted amount due, service
  period, ruled line-item table, and bank details as a label/value grid.
  Footer shows the invoice number and page count.
- Dates render as `Sep 30, 2026` instead of `30/09/2026` so day/month order
  can't be misread.
- Amounts always show cents (`$1,250.00`); totals use the ISO code
  (`USD 1,250.00`) instead of `US$`.
- Tax, shipping and purchase-order rows are hidden when zero or empty.
- `terms` renders as a closing note without a heading, and only when set.

## [0.1.2] - 2026-05-15

### Added
- `yinv skill install`: installs the bundled AI skill to
  `~/.claude/skills/yinv/SKILL.md` by default. `--dest <path>` redirects to
  an arbitrary file or directory; `--print` writes the skill to stdout
  instead; `--force` overwrites an existing file.
- `yinv new --no-edit`: writes the YAML without opening `$EDITOR` and skips
  the auto-render step — meant for agents and scripting.
- `yinv new --client NAME`: per-invocation override for the default client.
- Bundled `src/yinv/skill/SKILL.md` describing the AI-driven workflow.

## [0.1.1] - 2026-04-30

### Fixed
- `yinv new`: when `service_month` is edited in the YAML draft, the YAML
  and rendered PDF are renamed to match the edited month so the file on
  disk reflects the date you actually billed for.

### Changed
- `yinv config --help` (and the `set`/`get` subcommands) now list the
  configurable keys with descriptions and the path to the config file.

## [0.1.0] - 2026-04-12

### Added
- Initial implementation: `yinv new`, `yinv render`, `yinv config set/get`.
- YAML schema with explicit `service_month`, `client`, line-item descriptions.
- Bundled `seed.yaml` placeholder for first-run bootstrap.
- HTML/CSS → PDF rendering via WeasyPrint.
- Multi-client-ready data layout and config shape (single-client CLI in v0.1).
