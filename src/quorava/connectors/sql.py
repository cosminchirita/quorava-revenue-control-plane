from __future__ import annotations

import sqlite3
from pathlib import Path

from ..models import RawRow


class SQLiteConnector:
    SAFE_QUERY = """
        SELECT order_id, customer_id, customer_name, transaction_date, region,
               country, channel, product_family, currency, gross_amount,
               discount_amount, net_amount, cost_amount, status
        FROM sales_ledger
        ORDER BY transaction_date, order_id
    """

    def __init__(self, path: Path) -> None:
        self.path = path

    def read(self) -> list[RawRow]:
        if not self.path.exists():
            raise FileNotFoundError(f"SQLite source not found: {self.path}")
        connection = sqlite3.connect(f"file:{self.path.as_posix()}?mode=ro", uri=True)
        connection.row_factory = sqlite3.Row
        try:
            result = connection.execute(self.SAFE_QUERY).fetchall()
        finally:
            connection.close()
        return [
            RawRow(
                source_type="sql",
                source_ref=f"sales_ledger:{index}",
                source_row=index,
                payload=dict(row),
            )
            for index, row in enumerate(result, start=1)
        ]

