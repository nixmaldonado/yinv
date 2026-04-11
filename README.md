# yinv

CLI to generate monthly consulting invoices as PDFs. You edit a YAML draft in
your `$EDITOR`, save, and get a PDF that matches a consistent template.

## Install (dev)

```sh
brew install pango gdk-pixbuf libffi
uv tool install .   # or: pipx install .
```

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
placeholder YAML into the correct path and opens it in `$EDITOR`. Fill in the
placeholders (name, address, bank details, line items), save, then:

```sh
yinv render ~/Documents/Invoices/<client>/2026/<Month><Year>.yaml
```

to generate the PDF.

### Monthly

```sh
yinv new
```

Forks the latest invoice, increments the number, rolls the month forward
(updating dates and `Month YYYY` tokens in line items), opens in `$EDITOR` for
review, and renders the PDF on save.

`yinv new --month 2026-07` targets a specific month (skip ahead / regenerate).
`yinv new --force` overwrites an existing target.

### Re-render

```sh
yinv render <file.yaml>
```

Writes a fresh PDF next to the YAML. Useful after manually editing a YAML.

## Commands (v0.1)

| Command | Purpose |
|---|---|
| `yinv new [--month YYYY-MM] [--force]` | First-run bootstrap or monthly fork. |
| `yinv render <file.yaml>` | Render one YAML to PDF. |
| `yinv config set <key> <value>` | Write a config key. |
| `yinv config get <key>` | Read a config key. |

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

## License

MIT. See `LICENSE`.
