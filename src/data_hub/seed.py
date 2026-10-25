"""Deterministic synthetic data. Nothing here is real: names, phones and emails are made up."""

from __future__ import annotations

import argparse
import random
import sqlite3
from datetime import date, timedelta
from pathlib import Path

SITES = ("Goma-A", "Goma-B", "Goma-C")
PLAN_PRICE = {"basic": 8.0, "standard": 15.0, "business": 60.0}
FIRST = (
    "Amani",
    "Neema",
    "Baraka",
    "Zawadi",
    "Jean",
    "Marie",
    "Patrick",
    "Chantal",
    "Joseph",
    "Esther",
)
LAST = (
    "Mukendi",
    "Kabila",
    "Mbuyi",
    "Tshisekedi",
    "Ilunga",
    "Kasongo",
    "Mwamba",
    "Ngoy",
    "Lumumba",
    "Banza",
)
SUPPLIERS = (
    ("Sunpanel Trading", "panels"),
    ("Battery House", "batteries"),
    ("CableWorks", "cables"),
    ("MeterTech", "meters"),
    ("Inverter Direct", "inverters"),
    ("Safe Transport", "logistics"),
    ("Office Basics", "office"),
    ("FieldGear", "tools"),
)
CUSTOMERS = 60
MONTHS = 4  # current month plus the three before it


def first_of_month(today: date, offset: int = 0) -> date:
    """First day of the month `offset` months from today's month (negative = earlier)."""
    index = today.year * 12 + (today.month - 1) + offset
    return date(index // 12, index % 12 + 1, 1)


def build_database(path: Path, seed: int = 7, today: date | None = None) -> None:
    """Create a fresh database file. Same seed and date always give the same rows."""
    today = today or date.today()
    rng = random.Random(seed)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        path.unlink()
    conn = sqlite3.connect(path)
    try:
        conn.executescript(Path(__file__).with_name("schema.sql").read_text())
        plans = tuple(PLAN_PRICE)

        for cid in range(1, CUSTOMERS + 1):
            site = rng.choice(SITES)
            plan = rng.choices(plans, weights=(6, 3, 1))[0]
            joined = today - timedelta(days=rng.randint(120, 900))
            conn.execute(
                "INSERT INTO customers VALUES (?,?,?,?,?,?)",
                (
                    cid,
                    f"{rng.choice(FIRST)} {rng.choice(LAST)}",
                    f"+243 000 000 {cid:04d}",
                    site,
                    plan,
                    joined.isoformat(),
                ),
            )
            conn.execute(
                "INSERT INTO meters VALUES (?,?,?,?,?,?)",
                (
                    cid,
                    cid,
                    site,
                    "offline" if rng.random() < 0.1 else "online",
                    joined.isoformat(),
                    round(rng.uniform(100, 9000), 1),
                ),
            )

        invoice_id = payment_id = 0
        for cid, plan in conn.execute("SELECT id, plan FROM customers").fetchall():
            for back in range(MONTHS - 1, -1, -1):
                start = first_of_month(today, -back)
                end = first_of_month(today, -back + 1)
                invoice_id += 1
                paid = rng.random() < (0.5 if back == 0 else 0.85)
                conn.execute(
                    "INSERT INTO invoices VALUES (?,?,?,?,?,?)",
                    (
                        invoice_id,
                        cid,
                        start.strftime("%Y-%m"),
                        PLAN_PRICE[plan],
                        "paid" if paid else "unpaid",
                        start.isoformat(),
                    ),
                )
                if paid:
                    last_day = min(end - timedelta(days=1), today)
                    span = max((last_day - start).days, 0)
                    paid_on = start + timedelta(days=rng.randint(0, span))
                    payment_id += 1
                    conn.execute(
                        "INSERT INTO payments VALUES (?,?,?,?,?,?)",
                        (
                            payment_id,
                            invoice_id,
                            cid,
                            PLAN_PRICE[plan],
                            rng.choice(("mobile_money", "mobile_money", "cash", "bank")),
                            paid_on.isoformat(),
                        ),
                    )

        for sid, (name, category) in enumerate(SUPPLIERS, start=1):
            conn.execute(
                "INSERT INTO suppliers VALUES (?,?,?,?,?)",
                (
                    sid,
                    name,
                    category,
                    f"accounts@{name.lower().replace(' ', '')}.example.com",
                    round(rng.uniform(0, 12000), 2),
                ),
            )
        conn.commit()
    finally:
        conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Create the demo database.")
    parser.add_argument("path", type=Path, nargs="?", default=Path("hub.db"))
    parser.add_argument("--seed", type=int, default=7)
    args = parser.parse_args()
    build_database(args.path, args.seed)
    print(f"wrote {args.path}")


if __name__ == "__main__":
    main()
