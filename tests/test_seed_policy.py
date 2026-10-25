import sqlite3

from conftest import TODAY
from data_hub.policy import ALLOWED, ROLES, allowed_columns, schema_for
from data_hub.seed import build_database


def _dump(path, table):
    conn = sqlite3.connect(path)
    try:
        return conn.execute(f"SELECT * FROM {table} ORDER BY id").fetchall()
    finally:
        conn.close()


def test_row_counts_are_stable(db):
    assert len(_dump(db, "customers")) == 60
    assert len(_dump(db, "meters")) == 60
    assert len(_dump(db, "invoices")) == 240
    assert len(_dump(db, "suppliers")) == 8


def test_same_seed_same_data_different_seed_different_data(db, tmp_path):
    same = tmp_path / "same.db"
    other = tmp_path / "other.db"
    build_database(same, seed=7, today=TODAY)
    build_database(other, seed=8, today=TODAY)

    assert _dump(same, "payments") == _dump(db, "payments")
    assert _dump(other, "payments") != _dump(db, "payments")


def test_every_reference_points_at_a_real_row(db):
    conn = sqlite3.connect(db)
    try:
        orphans = conn.execute(
            "SELECT (SELECT COUNT(*) FROM invoices WHERE customer_id NOT IN (SELECT id FROM customers))"
            " + (SELECT COUNT(*) FROM payments WHERE invoice_id NOT IN (SELECT id FROM invoices))"
            " + (SELECT COUNT(*) FROM meters WHERE customer_id NOT IN (SELECT id FROM customers))"
        ).fetchone()[0]
    finally:
        conn.close()

    assert orphans == 0


def test_paid_invoices_have_exactly_one_payment_for_the_same_amount(db):
    conn = sqlite3.connect(db)
    try:
        bad = conn.execute(
            "SELECT COUNT(*) FROM invoices i LEFT JOIN payments p ON p.invoice_id = i.id "
            "WHERE (i.status = 'paid' AND (p.id IS NULL OR p.amount_usd != i.amount_usd)) "
            "OR (i.status = 'unpaid' AND p.id IS NOT NULL)"
        ).fetchone()[0]
    finally:
        conn.close()

    assert bad == 0


def test_viewer_sees_no_money_or_personal_columns():
    columns = {c for cols in schema_for("viewer").values() for c in cols}

    assert columns == {"id", "site", "status"}


def test_operations_cannot_see_names_or_phones():
    columns = {c for cols in schema_for("operations").values() for c in cols}

    assert not columns & {"name", "phone", "amount_usd", "balance_usd", "contact_email"}


def test_unknown_role_gets_nothing():
    assert schema_for("intern") == {}
    assert allowed_columns("") == {}


def test_no_role_can_read_the_audit_log():
    assert all("audit_log" not in ALLOWED[role] for role in ROLES)
