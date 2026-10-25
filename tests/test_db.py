import pytest

from data_hub.db import QueryError, run_readonly


def test_returns_columns_and_rows(db):
    result = run_readonly(db, "SELECT site, COUNT(*) AS n FROM meters GROUP BY site", "viewer")

    assert result.columns == ["site", "n"]
    assert sum(n for _, n in result.rows) == 60
    assert result.truncated is False


def test_row_limit_truncates_and_says_so(db):
    result = run_readonly(db, "SELECT id FROM payments", "admin", limit=5)

    assert len(result.rows) == 5
    assert result.truncated is True


@pytest.mark.parametrize(
    ("role", "sql"),
    [
        ("finance", "SELECT phone FROM customers"),
        ("viewer", "SELECT amount_usd FROM payments"),
        ("admin", "SELECT * FROM audit_log"),
        ("admin", "SELECT * FROM sqlite_master"),
        ("admin", "INSERT INTO customers VALUES (999,'x','x','x','basic','2026-01-01')"),
        ("admin", "UPDATE customers SET name = 'x'"),
        ("admin", "DROP TABLE customers"),
        ("admin", "SELECT load_extension('x')"),
        ("admin", "SELECT readfile('/etc/passwd')"),
    ],
)
def test_the_engine_refuses_even_if_the_guard_is_bypassed(db, role, sql):
    with pytest.raises(QueryError):
        run_readonly(db, sql, role)


def test_a_runaway_query_is_stopped(db):
    bomb = "SELECT COUNT(*) FROM " + ", ".join(f"payments p{i}" for i in range(6))

    with pytest.raises(QueryError):
        run_readonly(db, bomb, "admin", timeout_s=0.3)


def test_unknown_role_cannot_run_anything(db):
    with pytest.raises(QueryError):
        run_readonly(db, "SELECT 1", "intern")


def test_data_is_unchanged_after_all_that(db):
    for sql in ("DELETE FROM customers", "DROP TABLE payments"):
        with pytest.raises(QueryError):
            run_readonly(db, sql, "admin")

    assert run_readonly(db, "SELECT COUNT(*) FROM customers", "admin").rows == [(60,)]
