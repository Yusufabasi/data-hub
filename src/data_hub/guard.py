"""SQL guard: the first wall. Accepts one read-only SELECT over the role's allowed data.

Whatever generated the SQL (a rule, a model, an attacker typing into the question box) it is
parsed here, checked against the role's schema, and then re-rendered from the parsed tree.
The caller executes the rendered text, never the original string, so comments and anything the
parser did not understand cannot ride along.
"""

from __future__ import annotations

import sqlglot
from sqlglot import exp
from sqlglot.errors import SqlglotError
from sqlglot.optimizer.qualify import qualify

from data_hub.policy import allowed_columns, schema_for

MAX_SQL_CHARS = 2000
# Functions sqlglot does not know by name arrive as Anonymous; only these may pass.
_ANONYMOUS_OK = frozenset(
    {
        "strftime",
        "date",
        "datetime",
        "julianday",
        "printf",
        "ifnull",
        "nullif",
        "total",
        "group_concat",
        "instr",
        "glob",
    }
)
_QUERY_ROOTS = (exp.Select, exp.SetOperation)


class SqlRejected(Exception):
    """The SQL is not allowed. The message is for the audit log, not for the user."""


def validate_sql(sql: str, role: str) -> str:
    """Return the safe, rendered SQL for `role`, or raise SqlRejected."""
    if not allowed_columns(role):
        raise SqlRejected(f"role {role!r} has no data access")
    if len(sql) > MAX_SQL_CHARS:
        raise SqlRejected("SQL too long")

    try:
        statements = [s for s in sqlglot.parse(sql, dialect="sqlite") if s is not None]
    except SqlglotError as error:
        raise SqlRejected(f"cannot parse: {error}") from error
    if len(statements) != 1:
        raise SqlRejected(f"expected one statement, got {len(statements)}")
    tree = statements[0]
    if not isinstance(tree, _QUERY_ROOTS):
        raise SqlRejected(f"only SELECT is allowed, got {type(tree).__name__}")

    schema = schema_for(role)
    cte_names = {cte.alias_or_name.lower() for cte in tree.find_all(exp.CTE)}
    for table in tree.find_all(exp.Table):
        if table.db or table.catalog:
            raise SqlRejected("qualified table names are not allowed")
        name = table.name.lower()
        if name not in cte_names and name not in schema:
            raise SqlRejected(f"table not allowed: {table.name}")

    for func in tree.find_all(exp.Anonymous):
        if func.name.lower() not in _ANONYMOUS_OK:
            raise SqlRejected(f"function not allowed: {func.name}")
    if any(tree.find_all(exp.Placeholder, exp.Parameter)):
        raise SqlRejected("parameters are not allowed")

    try:
        qualified = qualify(
            tree,
            schema=schema,
            dialect="sqlite",
            validate_qualify_columns=True,
            identify=False,
            quote_identifiers=False,
        )
    except SqlglotError as error:
        raise SqlRejected(f"column or table not allowed: {error}") from error
    return qualified.sql(dialect="sqlite", comments=False)
