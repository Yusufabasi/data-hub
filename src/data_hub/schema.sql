-- Plain SQL so it ports to Postgres with type tweaks (INTEGER PRIMARY KEY -> SERIAL, etc).
CREATE TABLE customers (
    id        INTEGER PRIMARY KEY,
    name      TEXT NOT NULL,
    phone     TEXT NOT NULL,
    site      TEXT NOT NULL,
    plan      TEXT NOT NULL CHECK (plan IN ('basic', 'standard', 'business')),
    joined_on TEXT NOT NULL
);

CREATE TABLE meters (
    id               INTEGER PRIMARY KEY,
    customer_id      INTEGER NOT NULL REFERENCES customers (id),
    site             TEXT NOT NULL,
    status           TEXT NOT NULL CHECK (status IN ('online', 'offline')),
    installed_on     TEXT NOT NULL,
    last_reading_kwh REAL NOT NULL
);

CREATE TABLE invoices (
    id          INTEGER PRIMARY KEY,
    customer_id INTEGER NOT NULL REFERENCES customers (id),
    period      TEXT NOT NULL,          -- YYYY-MM
    amount_usd  REAL NOT NULL,
    status      TEXT NOT NULL CHECK (status IN ('paid', 'unpaid')),
    issued_on   TEXT NOT NULL           -- YYYY-MM-DD
);

CREATE TABLE payments (
    id          INTEGER PRIMARY KEY,
    invoice_id  INTEGER NOT NULL REFERENCES invoices (id),
    customer_id INTEGER NOT NULL REFERENCES customers (id),
    amount_usd  REAL NOT NULL,
    method      TEXT NOT NULL CHECK (method IN ('mobile_money', 'cash', 'bank')),
    paid_on     TEXT NOT NULL           -- YYYY-MM-DD
);

CREATE TABLE suppliers (
    id            INTEGER PRIMARY KEY,
    name          TEXT NOT NULL,
    category      TEXT NOT NULL,
    contact_email TEXT NOT NULL,
    balance_usd   REAL NOT NULL
);

-- Written by the service, never queryable through the question box (no role is granted it).
CREATE TABLE audit_log (
    id        INTEGER PRIMARY KEY,
    ts        TEXT NOT NULL,
    user      TEXT NOT NULL,
    role      TEXT NOT NULL,
    question  TEXT NOT NULL,
    sql       TEXT,
    ok        INTEGER NOT NULL,
    error     TEXT,
    row_count INTEGER NOT NULL DEFAULT 0
);
