# Changelog

All notable changes to yinv will be documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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
