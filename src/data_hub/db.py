"""Read-only execution: the second and third walls.

Wall 2: the connection is opened read-only at the file level.
Wall 3: a SQLite authorizer allows only SELECT, only the role's tables and columns, and only
        allow-listed functions, even if the guard were bypassed. A time limit stops runaway
        queries.
"""

from __future__ import annotations

import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path

from data_hub.policy import ALLOWED_FUNCTIONS, allowed_columns


class QueryError(Exception):
    """Execution failed (denied by the engine, timed out, or invalid)."""


@dataclass(frozen=True)
class Result:
    columns: list[str]
    rows: list[tuple]
    truncated: bool


def _authorizer(role: str):
    allowed = {t: set(cols) for t, cols in allowed_columns(role).items()}

    def check(action, arg1, arg2, _db, _source):
        if action == sqlite3.SQLITE_SELECT:
            return sqlite3.SQLITE_OK
        if action == sqlite3.SQLITE_READ:
            # arg1 = table, arg2 = column ("" for count(*)-style reads with no column)
            if arg1 in allowed and (arg2 == "" or arg2 in allowed[arg1]):
                return sqlite3.SQLITE_OK
            return sqlite3.SQLITE_DENY
        if action == sqlite3.SQLITE_FUNCTION:
            return (
                sqlite3.SQLITE_OK
                if (arg2 or "").lower() in ALLOWED_FUNCTIONS
                else sqlite3.SQLITE_DENY
            )
        if action == sqlite3.SQLITE_RECURSIVE:
            return sqlite3.SQLITE_OK
        return sqlite3.SQLITE_DENY

    return check


def run_readonly(
    db_path: Path, sql: str, role: str, limit: int = 200, timeout_s: float = 2.0
) -> Result:
    """Run already-validated SQL. Returns at most `limit` rows and says if it cut the rest."""
    if not allowed_columns(role):
        raise QueryError("role has no data access")
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        deadline = time.monotonic() + timeout_s
        conn.set_progress_handler(lambda: 1 if time.monotonic() > deadline else 0, 10_000)
        conn.set_authorizer(_authorizer(role))
        try:
            cursor = conn.execute(sql)
            rows = cursor.fetchmany(limit + 1)
            columns = [d[0] for d in cursor.description or []]
        except sqlite3.Error as error:
            raise QueryError(str(error)) from error
        return Result(columns=columns, rows=rows[:limit], truncated=len(rows) > limit)
    finally:
        conn.close()
