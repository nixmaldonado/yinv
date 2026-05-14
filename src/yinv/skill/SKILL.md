---
name: yinv-invoicing
description: Use when the user wants to generate, edit, or re-render a monthly consulting invoice with yinv. Triggers on phrases like "generate this month's invoice", "create May's invoice for Acme", "re-render the PDF", "add a line item to my invoice", or any task involving the yinv CLI.
---

# yinv-invoicing

`yinv` is an opinionated CLI for monthly consulting invoices. A YAML file is
the source of truth; the PDF is generated from it. Each client has its own
subdirectory under `invoices.dir`, and invoice numbers are independent per
client.

This skill wraps the `yinv` CLI. You generate, edit, and re-render invoices
by running `yinv` commands and editing YAML files directly. Always use the
non-interactive flag `--no-edit` so you control the YAML before the PDF is
rendered.

## Prerequisites — run these checks first

Before any other step:

1. `yinv --version` — if the command is not found, the user needs to install
   yinv. Direct them to:
   ```sh
   brew tap nixmaldonado/yinv
   brew install -v yinv
   ```
   Then stop and ask them to re-run their request after install.

2. `yinv config get invoices.dir` — if empty, prompt the user for a parent
   directory for invoices and run:
   ```sh
   yinv config set invoices.dir <path>
   ```

3. `yinv config get client.default` is optional. If empty, you must name a
   client explicitly with `--client <name>` on every command.

## Generate next month's invoice

The default flow when the user says "generate this month's invoice", "create
May's invoice", "make next month's invoice for Acme", etc.

1. Identify the target client. If the user names one, use it. Otherwise use
   `client.default`.

2. Fork the next invoice without opening an editor:
   ```sh
   yinv new --client <name> --no-edit
   ```
   Add `--month YYYY-MM` if the user named a specific month. Add `--force`
   only if the target file already exists and the user confirms overwrite.

   The command prints `wrote <yaml_path>` on success. Parse that path.

3. Read the YAML file. Compute and summarize for the user:
   - Invoice number
   - Service month
   - Currency and grand total: `sum(line_items[].unit_cost * line_items[].qty) + tax + shipping`
     where `tax = subtotal * tax_rate / 100`.
   - Brief list of line items (description + amount).

   Example summary:
   > Forked invoice #000008 for Acme, service month May 2026, total USD
   > 6,050 (Consulting fees + Tech Allowance). Want any changes before I
   > render the PDF?

4. Wait for the user to confirm or request changes. **Do not render until
   the user confirms.** If they request changes, apply them to the YAML in
   place (see "Edit recipes" below), re-summarize, and ask again.

5. Render the PDF:
   ```sh
   yinv render <yaml_path>
   ```
   Report the resulting PDF path and the total.

## Edit recipes

Always read the YAML before editing so you know the current state. Common
requests map to these fields:

- **"Change my rate to $X"** — edit `line_items[].unit_cost` for the
  relevant line. If multiple line items exist, ask which one.

- **"Add a line item"** — append to `line_items`. For a tech allowance,
  follow the existing convention: `description: "Tech Allowance <Month
  YYYY>"`.

- **"Change the due date"** — edit `due_date` (format `YYYY-MM-DD`).

- **"Change the date of issue"** — edit `date_of_issue` (format
  `YYYY-MM-DD`).

- **"Bill 1.5 weeks instead of full month"** — adjust `qty` or `unit_cost`
  on the consulting line. If the math is not obvious (rate is monthly vs.
  hourly vs. weekly), ask the user to specify the amount they want billed
  rather than guessing.

- **"Change the service month"** — edit `service_month` (format
  `YYYY-MM`). The YAML's filename will NOT auto-rename on `yinv render`.
  If the user wants the filename to match the new month, rename the YAML
  yourself before rendering, or re-run `yinv new --month <new>` to start
  fresh. Mention this trade-off so they can choose.

- **"Add a purchase order number"** — edit `purchase_order` (string or
  null).

- **"Change bank details"** — edit fields under `bank_details`. Confirm
  each value with the user; do not invent account numbers.

After any edit, re-summarize and ask for confirmation before rendering.

## Multi-client

If the user names a client other than `client.default` (e.g. "generate an
invoice for Spiff Co"), pass `--client "Spiff Co"` on every command for that
flow.

A brand-new client name routes through yinv's bootstrap path automatically.
After `yinv new --client NewClient --no-edit`, the YAML will contain
placeholder values for `billed_to`, `from`, `bank_details`, and one
placeholder line item. Tell the user this:

> Bootstrapped a new client folder. The YAML has placeholder values for
> billed_to / from / bank_details / line items. I can fill these in if you
> tell me the details, or you can edit the YAML yourself.

Do not render a bootstrap YAML with placeholders still in it — the PDF will
contain `YOUR NAME` and `0000000000` literally. Always confirm placeholders
are replaced first.

## Re-render an existing invoice

For "re-render", "regenerate the PDF", "I edited the YAML manually":

1. Locate the YAML file. Use the client + month from the conversation if
   available, else ask. The path is:
   `<invoices.dir>/<client>/<year>/<MonthName><year>.yaml`
   (e.g. `~/Documents/Invoices/Acme/2026/April2026.yaml`).

2. Run:
   ```sh
   yinv render <yaml_path>
   ```

3. Report the PDF path.

## YAML schema reference

The forked YAML has this shape (types in parens):

| Field | Type | Notes |
|---|---|---|
| `client` | string | Must match the client subdir name. |
| `invoice_number` | string | Zero-padded; **must be quoted** in YAML to preserve leading zeros. |
| `service_month` | string `YYYY-MM` | The month being billed for. |
| `date_of_issue` | date `YYYY-MM-DD` | Usually last day of `service_month`. |
| `due_date` | date `YYYY-MM-DD` | Usually 15th of the month after `service_month`. |
| `billed_to.name` | string | Client's legal name. |
| `billed_to.address` | list of strings | Each entry is one printed line. |
| `from.name` | string | Your name. |
| `from.address` | list of strings | Each entry is one printed line. |
| `purchase_order` | string or null | Optional. |
| `line_items[]` | list of mappings | At least one required. Each has `description`, `unit_cost` (numeric), `qty` (numeric). |
| `terms` | string | Free text shown on the invoice. |
| `tax_rate` | numeric | Percent (e.g. `0`, `7.5`). |
| `shipping` | numeric | Flat amount added to total. |
| `currency` | string | E.g. `USD`. |
| `bank_details.name` | string | Account holder name. |
| `bank_details.account_number` | string | Quote to preserve leading zeros. |
| `bank_details.account_type` | string | E.g. `Checking`. |
| `bank_details.routing_number` | string | Quote to preserve leading zeros. |
| `bank_details.swift_bic` | string | |
| `bank_details.bank_name` | string | |
| `bank_details.bank_address` | list of strings | One printed line per entry. |

Grand total formula: `sum(line_items[i].unit_cost * line_items[i].qty) +
(subtotal * tax_rate / 100) + shipping`.

## Failure modes

- `yinv: invoices.dir is not set` — run the bootstrap recipe above.
- `yinv: client.default is not set` — pass `--client <name>` or set the
  config key.
- `--month: invalid format` — re-prompt the user for `YYYY-MM`.
- `<path> already exists (pass --force to overwrite)` — ask the user if
  they want to overwrite. If yes, re-run with `--force`.
- `yinv: invalid invoice: <field>` — read the YAML, identify the offending
  field from the error, surface the line to the user with the specific
  validation failure.

## Don'ts

- Don't run `yinv new` without `--no-edit` — that opens an interactive
  editor and blocks the agent.
- Don't render before the user confirms the YAML looks right (except for
  explicit "re-render" requests).
- Don't invent values for `bank_details`, `from`, or `billed_to`. Ask the
  user.
- Don't edit `invoice_number` directly — let `yinv new` increment it.
