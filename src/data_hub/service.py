"""Ask a question as a user with a role: generate, guard, run read-only, audit."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from data_hub.db import QueryError, run_readonly
from data_hub.generate import CannotAnswer, SqlGenerator
from data_hub.guard import SqlRejected, validate_sql
from data_hub.policy import schema_for

MAX_QUESTION_CHARS = 500
# One wording for every refusal, so an answer never reveals whether a hidden column exists.
REFUSAL = (
    "I can't answer that with the data your role can access, "
    "or I couldn't turn it into a safe query."
)
UNKNOWN = (
    "I couldn't understand that question. Try asking about revenue, customers, invoices, "
    "meters or suppliers."
)


@dataclass(frozen=True)
class Answer:
    ok: bool
    sql: str | None  # the exact SQL that ran; None when nothing ran
    columns: list[str] = field(default_factory=list)
    rows: list[list] = field(default_factory=list)
    truncated: bool = False
    error: str | None = None


def _audit(
    db_path: Path,
    user: str,
    role: str,
    question: str,
    sql: str | None,
    ok: bool,
    error: str | None,
    row_count: int,
) -> None:
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            "INSERT INTO audit_log (ts, user, role, question, sql, ok, error, row_count) "
            "VALUES (?,?,?,?,?,?,?,?)",
            (
                datetime.now(UTC).isoformat(timespec="seconds"),
                user,
                role,
                question,
                sql,
                int(ok),
                error,
                row_count,
            ),
        )
        conn.commit()
    finally:
        conn.close()


def ask(
    question: str, role: str, user: str, db_path: Path, generator: SqlGenerator, limit: int = 200
) -> Answer:
    """Answer a question. Every call is audited; if the audit write fails the call fails."""
    question = question.strip()
    if not question or len(question) > MAX_QUESTION_CHARS:
        answer = Answer(ok=False, sql=None, error=UNKNOWN)
        _audit(db_path, user, role, question[:MAX_QUESTION_CHARS], None, False, "bad question", 0)
        return answer

    generated: str | None = None
    try:
        generated = generator.generate(question, schema_for(role))
        safe_sql = validate_sql(generated, role)
        result = run_readonly(db_path, safe_sql, role, limit=limit)
    except CannotAnswer:
        _audit(db_path, user, role, question, None, False, "generator could not answer", 0)
        return Answer(ok=False, sql=None, error=UNKNOWN)
    except (SqlRejected, QueryError) as reason:
        _audit(db_path, user, role, question, generated, False, f"rejected: {reason}", 0)
        return Answer(ok=False, sql=None, error=REFUSAL)

    _audit(db_path, user, role, question, safe_sql, True, None, len(result.rows))
    return Answer(
        ok=True,
        sql=safe_sql,
        columns=result.columns,
        rows=[list(row) for row in result.rows],
        truncated=result.truncated,
    )


def read_audit(db_path: Path, limit: int = 50) -> list[dict]:
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute("SELECT * FROM audit_log ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()
