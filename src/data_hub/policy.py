"""Who may see what. The single place roles and their data access are defined."""

from __future__ import annotations

FULL_SCHEMA: dict[str, dict[str, str]] = {
    "customers": {
        "id": "int",
        "name": "text",
        "phone": "text",
        "site": "text",
        "plan": "text",
        "joined_on": "text",
    },
    "meters": {
        "id": "int",
        "customer_id": "int",
        "site": "text",
        "status": "text",
        "installed_on": "text",
        "last_reading_kwh": "real",
    },
    "invoices": {
        "id": "int",
        "customer_id": "int",
        "period": "text",
        "amount_usd": "real",
        "status": "text",
        "issued_on": "text",
    },
    "payments": {
        "id": "int",
        "invoice_id": "int",
        "customer_id": "int",
        "amount_usd": "real",
        "method": "text",
        "paid_on": "text",
    },
    "suppliers": {
        "id": "int",
        "name": "text",
        "category": "text",
        "contact_email": "text",
        "balance_usd": "real",
    },
}

ROLES = ("admin", "finance", "operations", "viewer")

# role -> table -> allowed columns. audit_log is deliberately absent for every role.
ALLOWED: dict[str, dict[str, tuple[str, ...]]] = {
    "admin": {table: tuple(cols) for table, cols in FULL_SCHEMA.items()},
    "finance": {
        "customers": ("id", "name", "site", "plan"),
        "invoices": tuple(FULL_SCHEMA["invoices"]),
        "payments": tuple(FULL_SCHEMA["payments"]),
        "suppliers": tuple(FULL_SCHEMA["suppliers"]),
    },
    "operations": {
        "customers": ("id", "site", "plan", "joined_on"),
        "meters": tuple(FULL_SCHEMA["meters"]),
    },
    "viewer": {
        "meters": ("id", "site", "status"),
    },
}

# SQL functions a question may use. Anything else is rejected by the guard and the engine.
ALLOWED_FUNCTIONS = frozenset(
    {
        "count",
        "sum",
        "avg",
        "min",
        "max",
        "total",
        "round",
        "abs",
        "coalesce",
        "ifnull",
        "nullif",
        "lower",
        "upper",
        "length",
        "substr",
        "trim",
        "instr",
        "like",
        "glob",
        "strftime",
        "date",
        "datetime",
        "julianday",
        "printf",
        "group_concat",
    }
)


def allowed_columns(role: str) -> dict[str, tuple[str, ...]]:
    """Tables and columns the role may read. Unknown roles get nothing."""
    return ALLOWED.get(role, {})


def schema_for(role: str) -> dict[str, dict[str, str]]:
    """The role's view of the schema, in the shape sqlglot expects."""
    return {
        table: {col: FULL_SCHEMA[table][col] for col in cols}
        for table, cols in allowed_columns(role).items()
    }
