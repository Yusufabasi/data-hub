import pytest

from data_hub.guard import SqlRejected, validate_sql


@pytest.mark.parametrize(
    ("role", "sql"),
    [
        ("finance", "SELECT SUM(amount_usd) FROM payments WHERE paid_on >= '2026-09-01'"),
        ("viewer", "SELECT site, COUNT(*) FROM meters WHERE status = 'offline' GROUP BY site"),
        (
            "operations",
            "SELECT c.site, COUNT(*) FROM customers c JOIN meters m ON m.customer_id = c.id GROUP BY c.site",
        ),
        ("admin", "SELECT name, phone FROM customers"),
        ("finance", "WITH p AS (SELECT * FROM payments) SELECT SUM(amount_usd) FROM p"),
        ("finance", "SELECT name FROM customers UNION SELECT name FROM suppliers"),
        (
            "finance",
            "SELECT strftime('%Y-%m', paid_on) m, SUM(amount_usd) FROM payments GROUP BY m",
        ),
    ],
)
def test_allowed_queries_pass(role, sql):
    assert validate_sql(sql, role).upper().startswith(("SELECT", "WITH"))


@pytest.mark.parametrize(
    "sql",
    [
        "DROP TABLE customers",
        "UPDATE customers SET name = 'x'",
        "INSERT INTO customers VALUES (1,1,1,1,1,1)",
        "DELETE FROM customers",
        "ATTACH DATABASE 'other.db' AS o",
        "PRAGMA table_info(customers)",
        "SELECT 1; SELECT 2",
        "SELECT 1 /* harmless */; DROP TABLE customers",
        "SELECT * FROM sqlite_master",
        "SELECT * FROM audit_log",
        "SELECT * FROM [audit_log]",
        'SELECT * FROM "audit_log"',
        "SELECT * FROM `audit_log`",
        "SELECT * FROM pragma_table_info('customers')",
        "SELECT load_extension('evil')",
        "SELECT readfile('/etc/passwd')",
        "SELECT * FROM main.customers",
        "SELECT ?",
        "",
        "not sql at all",
    ],
)
def test_dangerous_or_foreign_sql_is_rejected_even_for_admin(sql):
    with pytest.raises(SqlRejected):
        validate_sql(sql, "admin")


def test_select_star_expands_to_allowed_columns_only():
    rendered = validate_sql("SELECT * FROM customers", "operations").lower()

    assert "site" in rendered and "joined_on" in rendered
    assert "name" not in rendered and "phone" not in rendered


@pytest.mark.parametrize(
    ("role", "sql"),
    [
        ("finance", "SELECT phone FROM customers"),
        ("finance", 'SELECT "phone" FROM customers'),
        ("finance", "SELECT Phone FROM CUSTOMERS"),
        (
            "finance",
            "SELECT name FROM customers WHERE id IN (SELECT id FROM customers WHERE phone LIKE '+243%')",
        ),
        ("finance", "SELECT name, (SELECT MAX(phone) FROM customers) FROM customers"),
        ("finance", "SELECT c.phone FROM customers AS c"),
        ("operations", "SELECT name FROM customers"),
        ("operations", "SELECT amount_usd FROM invoices"),
        ("viewer", "SELECT * FROM customers"),
        ("viewer", "SELECT site FROM meters UNION SELECT method FROM payments"),
        ("viewer", "WITH x AS (SELECT * FROM payments) SELECT * FROM x"),
        ("viewer", "SELECT last_reading_kwh FROM meters"),
        ("viewer", "SELECT m.* FROM meters m JOIN customers c ON c.id = m.customer_id"),
    ],
)
def test_hidden_columns_and_tables_are_rejected_wherever_they_hide(role, sql):
    with pytest.raises(SqlRejected):
        validate_sql(sql, role)


def test_unknown_role_is_rejected():
    with pytest.raises(SqlRejected):
        validate_sql("SELECT 1", "intern")


def test_comments_are_stripped_from_what_will_run():
    rendered = validate_sql("SELECT site FROM meters -- ; DROP TABLE meters", "viewer")

    assert "--" not in rendered and "drop" not in rendered.lower()


def test_overlong_sql_is_rejected():
    with pytest.raises(SqlRejected):
        validate_sql("SELECT site FROM meters WHERE " + " OR ".join(["site = 'a'"] * 400), "viewer")


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT site FROM meters -- x */ ; DROP TABLE meters ; /*",
        "SELECT site FROM meters /* a */ WHERE status = 'online' -- trailing",
    ],
)
def test_comment_text_never_reaches_the_executed_sql(sql):
    try:
        rendered = validate_sql(sql, "viewer")
    except SqlRejected:
        return  # also acceptable: refusing is safe
    assert "/*" not in rendered and "--" not in rendered and "drop" not in rendered.lower()
