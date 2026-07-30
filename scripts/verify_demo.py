from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from quorava.audit import verify_chain  # noqa: E402
from quorava.pipeline import run_pipeline  # noqa: E402


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> None:
    result = run_pipeline(ROOT)
    require(result.metadata["data_classification"] == "SYNTHETIC / PUBLIC DEMO", "Demo boundary missing")
    require(result.kpis["raw_records"] >= 25, "Expected all three source families")
    require(result.kpis["duplicates_removed"] >= 3, "Deduplication scenario is not exercised")
    require(result.kpis["data_quality_score"] >= 85, "Demo quality score is unexpectedly low")
    require(len(result.anomalies) >= 3, "Anomaly detector should produce reviewable findings")
    require(verify_chain(result.audit_log), "Audit hash chain is invalid")

    snapshot_path = ROOT / "data" / "warehouse" / "demo_snapshot.json"
    snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
    require(snapshot["metadata"]["run_id"] == result.metadata["run_id"], "Persisted snapshot differs from run")

    connection = sqlite3.connect(ROOT / "data" / "warehouse" / "analytics.db")
    try:
        fact_count = connection.execute("SELECT COUNT(*) FROM revenue_facts").fetchone()[0]
        view_total = connection.execute("SELECT ROUND(SUM(net_revenue_eur), 2) FROM powerbi_revenue_model").fetchone()[0]
    finally:
        connection.close()
    require(fact_count == result.kpis["canonical_records"], "Warehouse fact count does not reconcile")
    require(abs(view_total - result.kpis["net_revenue_eur"]) < 0.02, "Power BI view does not reconcile")
    print(
        f"Quorava verified: {fact_count} canonical records, {len(result.anomalies)} findings, "
        f"audit chain intact, EUR {view_total:,.2f} reconciled."
    )


if __name__ == "__main__":
    main()

