from __future__ import annotations

import sqlite3
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from quorava.pipeline import run_pipeline  # noqa: E402


SQL_ROWS = [
    ("Q-260701", "AC-1024", "Nordic Workshop Group", "2026-07-03", "Nordics", "SE", "Direct", "Cloud Control", "EUR", 48200, 2400, 45800, 18100, "settled"),
    ("Q-260715", "AC-3220", "Saxon Medical Devices", "2026-07-15", "DACH", "DE", "Direct", "Data Assurance", "EUR", 89200, 4200, 85000, 34400, "settled"),
    ("Q-260716", "AC-3348", "Carpathian Logistics", "2026-07-16", "CEE", "RO", "Partner", "Control API", "RON", 318000, 18000, 300000, 128000, "settled"),
    ("Q-260717", "AC-3511", "Occitan Research Works", "2026-07-17", "France", "FR", "Direct", "Cloud Control", "EUR", 68400, 3400, 65000, 27100, "won"),
    ("Q-260718", "AC-4110", "Atlantic Retail Labs", "2026-07-18", "UKI", "GB", "Marketplace", "Cloud Control", "GBP", 39200, 16200, 23000, 17800, "settled"),
    ("Q-260719", "AC-3722", "Hanseatic Fleet Tech", "2026-07-19", "DACH", "DE", "Partner", "Data Assurance", "EUR", 73600, 3600, 70000, 29400, "settled"),
    ("Q-260720", "AC-3901", "North Sea Analytics", "2026-07-21", "Nordics", "DK", "Direct", "Control API", "EUR", 59400, 2400, 57000, 23100, "won"),
]


def build_sql_source() -> Path:
    target = ROOT / "data" / "sql" / "operations.db"
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        target.unlink()
    connection = sqlite3.connect(target)
    try:
        connection.execute(
            """
            CREATE TABLE sales_ledger (
                order_id TEXT PRIMARY KEY,
                customer_id TEXT NOT NULL,
                customer_name TEXT NOT NULL,
                transaction_date TEXT NOT NULL,
                region TEXT NOT NULL,
                country TEXT NOT NULL,
                channel TEXT NOT NULL,
                product_family TEXT NOT NULL,
                currency TEXT NOT NULL,
                gross_amount REAL NOT NULL,
                discount_amount REAL NOT NULL,
                net_amount REAL NOT NULL,
                cost_amount REAL NOT NULL,
                status TEXT NOT NULL
            )
            """
        )
        connection.executemany("INSERT INTO sales_ledger VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", SQL_ROWS)
        connection.commit()
    finally:
        connection.close()
    return target


def main() -> None:
    sql_path = build_sql_source()
    result = run_pipeline(ROOT)
    print(f"Created {sql_path.relative_to(ROOT)}")
    print(
        f"Pipeline {result.metadata['run_id']} completed: "
        f"{result.kpis['raw_records']} raw -> {result.kpis['canonical_records']} canonical records, "
        f"{result.kpis['duplicates_removed']} duplicates removed."
    )


if __name__ == "__main__":
    main()

