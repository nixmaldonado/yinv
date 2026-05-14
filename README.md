# yinv

CLI to generate monthly consulting invoices as PDFs. You edit a YAML draft in
your `$EDITOR`, save, and get a PDF that matches a consistent template.

## Install

```sh
brew tap nixmaldonado/yinv
brew install -v yinv
```
First install can take a couple of minutes so use -v to see it's actually progressing.

## Configure

```sh
yinv config set invoices.dir ~/Documents/Invoices
yinv config set client.default <your-client-subdir-name>
```

`invoices.dir` is the parent dir containing one subdir per client. Each
client's invoices live under `{invoices.dir}/{client}/{year}/`.

## Use

### First run

```sh
yinv new
```

If no prior invoice exists for `client.default`, `yinv new` writes a
placeholder YAML into the correct path and opens it in `$EDITOR`.

Fill in the placeholders (name, address, bank details, line items), then save
and exit your editor. `yinv new` will validate the YAML and generate the PDF
automatically after the editor exits successfully.

The seed file still contains placeholder contact, bank, and pricing values,
but the default `Consulting fees for <Month YYYY>` description is adjusted to
the target service month automatically.

### Monthly

```sh
yinv new
```

Forks the latest invoice, increments the number, rolls the month forward
(updating dates and exact `Month YYYY` tokens in line-item descriptions),
opens in `$EDITOR` for review, and renders the PDF after the editor exits
successfully.

Example: if the previous invoice contains `Consulting fees for April 2026`,
the next one will become `Consulting fees for May 2026`.

The month rewrite is intentionally narrow: it only replaces the exact previous
invoice service-month token. If the prior invoice still says `January 2026` or
uses a different format such as `Jan 2026`, that text will be carried forward
unchanged.

`yinv new --month 2026-07` targets a specific month (skip ahead / regenerate).
`yinv new --force` overwrites an existing target.

### Re-render

```sh
yinv render <file.yaml>
```

Writes a fresh PDF next to the YAML. Useful after manually editing a YAML.
This is mainly for re-rendering an existing invoice; `yinv new` already renders
the new month's PDF automatically after a successful editor exit.

## AI-driven workflow

`yinv` ships with a portable AI skill that lets you drive the same workflow
from an agent ("generate May's invoice for Acme", "add a tech allowance
line", "re-render the PDF"). For Claude Code, install it with:

```sh
yinv skill install
```

That copies the bundled skill to `~/.claude/skills/yinv/SKILL.md`. For other
agents, use `--dest <path>` or `--print` to redirect to wherever your tool
expects skills to live.

The skill calls `yinv new --no-edit --client <name>` instead of the
interactive flow, then edits the YAML and runs `yinv render` once you've
confirmed the changes look right.

## Commands (v0.1)

| Command | Purpose |
|---|---|
| `yinv new [--month YYYY-MM] [--client NAME] [--force] [--no-edit]` | First-run bootstrap or monthly fork. `--no-edit` skips `$EDITOR` and auto-render (useful for agents). |
| `yinv render <file.yaml>` | Render one YAML to PDF. |
| `yinv config set <key> <value>` | Write a config key. |
| `yinv config get <key>` | Read a config key. |
| `yinv skill install [--dest PATH] [--print] [--force]` | Install the bundled AI skill (default: `~/.claude/skills/yinv/`). |

## Data layout

```
~/Documents/Invoices/            ← invoices.dir
└── <client>/                    ← one subdir per client
    └── 2026/
        ├── March2026.yaml       ← source of truth
        └── March2026.pdf        ← generated from the YAML
```

Nothing else. No database, no index file. Add another client tomorrow by
creating another subdir.

### Configuration keys

| Key | Default | Description |
|---|---|---|
| `invoices.dir` | — | Parent directory containing one subdir per client. |
| `client.default` | — | Client subdirectory to use when running `yinv new`. |
| `editor` | `$VISUAL` / `$EDITOR` / `vi` | Command used to open YAML drafts for editing. |
| `currency` | `USD` | Currency code used in invoices. |
| `invoice_number.width` | `6` | Minimum zero-padded width for invoice numbers. |

Config is stored in `~/.config/yinv/config.toml`.

## License

MIT. See `LICENSE`.
