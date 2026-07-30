from __future__ import annotations

import csv
import json
import sqlite3
from pathlib import Path
from typing import Any

from .models import PipelineResult


def write_snapshot(result: PipelineResult, output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    snapshot_path = output_dir / "demo_snapshot.json"
    with snapshot_path.open("w", encoding="utf-8") as handle:
        json.dump(result.as_dict(), handle, indent=2, ensure_ascii=False)
        handle.write("\n")
    return snapshot_path


def write_powerbi_export(result: PipelineResult, output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    export_path = output_dir / "powerbi_revenue_facts.csv"
    fields = [
        "record_id",
        "order_id",
        "transaction_date",
        "region",
        "country",
        "channel",
        "product_family",
        "currency",
        "gross_eur",
        "net_eur",
        "cost_eur",
        "margin_eur",
        "status",
        "quality_score",
        "issue_count",
        "source_type",
        "lineage_hash",
    ]
    with export_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for record in result.records:
            payload = record.as_dict()
            writer.writerow({field: payload[field] for field in fields})
    return export_path


def write_warehouse(result: PipelineResult, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        path.unlink()
    connection = sqlite3.connect(path)
    try:
        connection.executescript(
            """
            CREATE TABLE revenue_facts (
                record_id TEXT PRIMARY KEY,
                order_id TEXT NOT NULL,
                transaction_date TEXT NOT NULL,
                region TEXT NOT NULL,
                country TEXT NOT NULL,
                channel TEXT NOT NULL,
                product_family TEXT NOT NULL,
                gross_eur REAL NOT NULL,
                net_eur REAL NOT NULL,
                cost_eur REAL NOT NULL,
                margin_eur REAL NOT NULL,
                status TEXT NOT NULL,
                quality_score REAL NOT NULL,
                source_type TEXT NOT NULL,
                lineage_hash TEXT NOT NULL
            );
            CREATE TABLE anomaly_findings (
                anomaly_id TEXT PRIMARY KEY,
                record_id TEXT NOT NULL,
                severity TEXT NOT NULL,
                risk_score INTEGER NOT NULL,
                anomaly_type TEXT NOT NULL,
                title TEXT NOT NULL,
                FOREIGN KEY(record_id) REFERENCES revenue_facts(record_id)
            );
            CREATE VIEW powerbi_revenue_model AS
            SELECT transaction_date, region, country, channel, product_family,
                   SUM(net_eur) AS net_revenue_eur,
                   SUM(margin_eur) AS margin_eur,
                   AVG(quality_score) AS data_quality_score,
                   COUNT(*) AS transaction_count
            FROM revenue_facts
            GROUP BY transaction_date, region, country, channel, product_family;
            """
        )
        connection.executemany(
            """
            INSERT INTO revenue_facts VALUES (
                :record_id, :order_id, :transaction_date, :region, :country,
                :channel, :product_family, :gross_eur, :net_eur, :cost_eur,
                :margin_eur, :status, :quality_score, :source_type, :lineage_hash
            )
            """,
            [record.as_dict() for record in result.records],
        )
        connection.executemany(
            """INSERT INTO anomaly_findings VALUES
               (:anomaly_id, :record_id, :severity, :risk_score, :anomaly_type, :title)""",
            [anomaly.as_dict() for anomaly in result.anomalies],
        )
        connection.commit()
    finally:
        connection.close()
    return path


def load_snapshot(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)

