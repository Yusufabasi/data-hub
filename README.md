# Data Hub

A small internal database with role-based access and a plain-language question box (English
or French). Staff ask "what was revenue last month?" and get a table plus **the exact SQL that
ran**, so every answer can be checked. The AI never writes data and never sees more than the
asking person's role may see.

This is a thin, working slice built to show the design: one source of truth, access controls,
read-only AI querying, and an audit trail. The data is synthetic.

## Why it is safe to let an AI write SQL

Generated SQL is treated as hostile input. It has to get past three independent walls:

| Wall | Where | What it stops |
|------|-------|---------------|
| 1. Guard | `guard.py` | Parses the SQL with sqlglot. Exactly one `SELECT` (or `UNION` of selects), only the role's tables, only the role's columns (`SELECT *` is rewritten to the allowed columns), no unknown functions (`load_extension`, `pragma_*`, `readfile`), no placeholders. The text that runs is **re-rendered from the parse tree**, so comments and anything the parser did not understand cannot ride along. |
| 2. Read-only connection | `db.py` | The database file is opened `mode=ro`; a write cannot succeed even if every check above failed. |
| 3. Engine authorizer | `db.py` | SQLite itself allows only `SELECT`, only the role's columns, only allow-listed functions, and kills queries after 2 seconds. This is tested with the guard bypassed. |

Other controls: refusals use one fixed wording so a response never reveals whether a hidden
column exists; every question (including refused ones) is written to an audit table, and if the
audit write fails the request fails; results are capped at 200 rows; `audit_log` is not
readable through the question box by any role.

## Roles (`policy.py`)

| Role | Can read |
|------|----------|
| `admin` | everything except the audit table (read through `/audit`) |
| `finance` | customers (id, name, site, plan), invoices, payments, suppliers |
| `operations` | customers (id, site, plan, joined_on), meters |
| `viewer` | meters (id, site, status) only |

## Run it

```bash
python3 -m venv .venv && .venv/bin/pip install -e '.[dev]'
.venv/bin/data-hub-seed hub.db                       # synthetic, deterministic data
HUB_DB=hub.db \
HUB_TOKENS='{"demo-finance-1":{"user":"amina","role":"finance"},"demo-viewer-1":{"user":"vera","role":"viewer"}}' \
  .venv/bin/uvicorn --factory data_hub.api:app_from_env --port 8000
# open http://localhost:8000, paste a token, ask a question
.venv/bin/pytest                                     # 95 tests
```

`.env.example` lists every variable the app reads. The demo tokens above are fake and for local
use. Tokens come from the environment and must be
at least 8 characters; this is a demo-grade scheme, and a real deployment would put the
company's single sign-on in front and map identities to roles.

By default questions are answered by an offline rule-based generator (revenue, customers,
unpaid invoices, offline meters, payment methods, supplier balances, in English and French).
Set `HUB_GENERATOR=anthropic` and `ANTHROPIC_API_KEY` to use a model instead; the guard and
the engine apply the same either way.

## Not built, on purpose

- Supplier-invoice PDF extraction with human approval (the stretch goal).
- Charts, and a real identity provider.
- Postgres: `schema.sql` is plain SQL and ports with small type changes; row-level security
  would replace the authorizer wall.
- The model-backed generator has not been run against the live API (needs a key).
