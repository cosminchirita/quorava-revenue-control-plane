from __future__ import annotations

from collections import Counter, defaultdict
from datetime import date
from pathlib import Path
from typing import Any, Iterable

from .anomaly import detect_anomalies
from .audit import AuditChain
from .connectors import ExcelConnector, JsonApiConnector, SQLiteConnector
from .models import PipelineResult, RawRow, RevenueRecord
from .quality import aggregate_quality, apply_quality_scores, validate_record
from .storage import write_powerbi_export, write_snapshot, write_warehouse
from .utils import customer_label, load_json, normalize_text, stable_hash, to_iso_date, to_money


SOURCE_PRIORITY = {"sql": 0, "api": 1, "excel": 2}
STATUS_MAP = {
    "closed": "won",
    "paid": "settled",
    "complete": "settled",
    "completed": "settled",
    "open": "pending",
    "in review": "pending",
    "returned": "refunded",
}


def _lookup(payload: dict[str, Any], aliases: list[str]) -> Any:
    for alias in aliases:
        if alias in payload and payload[alias] not in (None, ""):
            return payload[alias]
    return None


def normalize_row(
    row: RawRow,
    mappings: dict[str, list[str]],
    rates: dict[str, float],
) -> RevenueRecord:
    values = {field: _lookup(row.payload, aliases) for field, aliases in mappings.items()}
    currency = normalize_text(values["currency"], "UNKNOWN").upper()
    rate = float(rates.get(currency, 0))
    gross = to_money(values["gross_amount"])
    discount = to_money(values["discount_amount"])
    net = to_money(values["net_amount"])
    cost = to_money(values["cost_amount"])
    raw_status = normalize_text(values["status"]).lower()
    status = STATUS_MAP.get(raw_status, raw_status)
    order_id = normalize_text(values["order_id"])
    transaction_date = to_iso_date(values["transaction_date"])
    record_id = f"REV-{stable_hash([row.source_type, row.source_ref, order_id], 12).upper()}"
    canonical_basis = {
        "order_id": order_id,
        "customer_id": normalize_text(values["customer_id"]),
        "transaction_date": transaction_date,
        "region": normalize_text(values["region"]),
        "country": normalize_text(values["country"]).upper(),
        "channel": normalize_text(values["channel"]).title(),
        "product_family": normalize_text(values["product_family"]).title(),
        "currency": currency,
        "gross_amount": gross,
        "discount_amount": discount,
        "net_amount": net,
        "cost_amount": cost,
        "status": status,
    }
    return RevenueRecord(
        record_id=record_id,
        source_type=row.source_type,
        source_ref=row.source_ref,
        source_row=row.source_row,
        customer_label=customer_label(values["customer_name"]),
        gross_eur=round(gross * rate, 2),
        net_eur=round(net * rate, 2),
        cost_eur=round(cost * rate, 2),
        margin_eur=round((net - cost) * rate, 2),
        lineage_hash=stable_hash({"source": row.source_ref, "canonical": canonical_basis}, 24),
        **canonical_basis,
    )


def _deduplicate(records: list[RevenueRecord]) -> tuple[list[RevenueRecord], list[dict[str, Any]]]:
    groups: dict[str, list[RevenueRecord]] = defaultdict(list)
    for record in records:
        fingerprint = stable_hash([record.order_id, record.transaction_date, round(record.net_eur, 2)], 24)
        groups[fingerprint].append(record)

    canonical: list[RevenueRecord] = []
    duplicates: list[dict[str, Any]] = []
    for fingerprint, candidates in groups.items():
        ranked = sorted(candidates, key=lambda item: (item.issue_count, SOURCE_PRIORITY[item.source_type], item.source_ref))
        winner = ranked[0]
        canonical.append(winner)
        for duplicate in ranked[1:]:
            duplicates.append(
                {
                    "fingerprint": fingerprint,
                    "kept_record_id": winner.record_id,
                    "removed_record_id": duplicate.record_id,
                    "kept_source": winner.source_type,
                    "removed_source": duplicate.source_type,
                    "reason": "Same order, transaction date and normalized net amount",
                }
            )
    canonical.sort(key=lambda item: (item.transaction_date, item.order_id))
    return canonical, duplicates


def _source_stats(raw_rows: list[RawRow], normalized: list[RevenueRecord], issues: list) -> list[dict[str, Any]]:
    raw_counts = Counter(row.source_type for row in raw_rows)
    normalized_counts = Counter(record.source_type for record in normalized)
    issue_records = Counter()
    record_source = {record.record_id: record.source_type for record in normalized}
    for issue in issues:
        issue_records[record_source.get(issue.record_id, "unknown")] += 1
    labels = {
        "excel": "Excel workbooks",
        "api": "CRM REST API",
        "sql": "ERP SQLite ledger",
    }
    return [
        {
            "source_type": source,
            "name": labels[source],
            "status": "healthy" if issue_records[source] == 0 else "attention",
            "raw_rows": raw_counts[source],
            "normalized_rows": normalized_counts[source],
            "quality_issues": issue_records[source],
            "freshness": {"excel": "8 min", "api": "2 min", "sql": "4 min"}[source],
        }
        for source in ("excel", "api", "sql")
    ]


def _time_series(records: Iterable[RevenueRecord]) -> list[dict[str, Any]]:
    days: dict[str, dict[str, float]] = defaultdict(lambda: {"net": 0.0, "margin": 0.0})
    for record in records:
        bucket = days[record.transaction_date]
        bucket["net"] += record.net_eur
        bucket["margin"] += record.margin_eur
    return [
        {"date": key, "net_revenue_eur": round(value["net"], 2), "margin_eur": round(value["margin"], 2)}
        for key, value in sorted(days.items())
    ]


def _region_breakdown(records: Iterable[RevenueRecord]) -> list[dict[str, Any]]:
    regions: dict[str, dict[str, float]] = defaultdict(lambda: {"net": 0.0, "margin": 0.0, "orders": 0})
    for record in records:
        bucket = regions[record.region]
        bucket["net"] += record.net_eur
        bucket["margin"] += record.margin_eur
        bucket["orders"] += 1
    return [
        {
            "region": region,
            "net_revenue_eur": round(values["net"], 2),
            "margin_eur": round(values["margin"], 2),
            "orders": int(values["orders"]),
        }
        for region, values in sorted(regions.items(), key=lambda item: -item[1]["net"])
    ]


def run_pipeline(
    root: Path,
    *,
    api_endpoint: str | Path | None = None,
    persist: bool = True,
) -> PipelineResult:
    as_of = date(2026, 7, 30)
    started_at = "2026-07-30T09:30:00Z"
    config_dir = root / "config"
    data_dir = root / "data"
    mappings = load_json(config_dir / "field_mappings.json")
    contract = load_json(config_dir / "data_contract.json")
    rules = load_json(config_dir / "quality_rules.json")
    rate_config = load_json(config_dir / "exchange_rates.json")
    rates = rate_config["rates_to_eur"]
    api_endpoint = api_endpoint or (data_dir / "api" / "crm_snapshot.json")

    audit = AuditChain(started_at)
    audit.append("pipeline.service", "run.started", "pipeline:demo", {"contract": contract["contract_version"]})

    connectors = [
        *(ExcelConnector(path) for path in sorted((data_dir / "excel").glob("*.xlsx"))),
        JsonApiConnector(api_endpoint),
        SQLiteConnector(data_dir / "sql" / "operations.db"),
    ]
    raw_rows: list[RawRow] = []
    for connector in connectors:
        batch = connector.read()
        raw_rows.extend(batch)
        audit.append("pipeline.service", "source.ingested", connector.__class__.__name__, {"rows": len(batch)})

    normalized = [normalize_row(row, mappings, rates) for row in raw_rows]
    issues = [issue for record in normalized for issue in validate_record(record, contract, as_of)]
    apply_quality_scores(normalized, issues)
    audit.append("quality.engine", "contract.evaluated", contract["dataset"], {"records": len(normalized), "issues": len(issues)})

    canonical, duplicates = _deduplicate(normalized)
    canonical_ids = {record.record_id for record in canonical}
    canonical_issues = [issue for issue in issues if issue.record_id in canonical_ids]
    audit.append("identity.engine", "duplicates.resolved", "canonical_revenue_event", {"removed": len(duplicates)})

    anomalies = detect_anomalies(canonical)
    audit.append("risk.engine", "anomalies.scored", "robust-rules-v1.0", {"findings": len(anomalies)})

    quality = aggregate_quality(canonical, canonical_issues)
    net_revenue = round(sum(record.net_eur for record in canonical), 2)
    margin = round(sum(record.margin_eur for record in canonical), 2)
    source_stats = _source_stats(raw_rows, normalized, issues)
    critical_findings = sum(1 for item in anomalies if item.severity == "critical")
    controls_passed = sum(1 for rule in rules["rules"] if not any(issue.rule_id == rule["id"] for issue in canonical_issues))
    run_id = f"RUN-{stable_hash([started_at, len(raw_rows), len(canonical), contract['contract_version']], 10).upper()}"

    kpis = {
        "net_revenue_eur": net_revenue,
        "margin_eur": margin,
        "margin_rate": round(margin / net_revenue * 100, 1) if net_revenue else 0,
        "raw_records": len(raw_rows),
        "canonical_records": len(canonical),
        "duplicates_removed": len(duplicates),
        "duplicate_rate": round(len(duplicates) / max(len(raw_rows), 1) * 100, 1),
        "data_quality_score": quality["score"],
        "quality_pass_rate": quality["pass_rate"],
        "quality_issue_count": quality["issue_count"],
        "anomaly_count": len(anomalies),
        "critical_findings": critical_findings,
        "controls_passed": controls_passed,
        "controls_total": len(rules["rules"]),
        "time_series": _time_series(canonical),
        "region_breakdown": _region_breakdown(canonical),
    }
    metadata = {
        "product": "Quorava Revenue Control Plane",
        "environment": "synthetic-demo",
        "run_id": run_id,
        "started_at": started_at,
        "completed_at": "2026-07-30T09:30:08Z",
        "contract_version": contract["contract_version"],
        "rule_version": rules["rule_version"],
        "model_version": "robust-rules-v1.0",
        "exchange_rate_as_of": rate_config["as_of"],
        "data_classification": "SYNTHETIC / PUBLIC DEMO",
        "decision_boundary": "Human review required; no autonomous financial action",
        "quality_summary": quality,
    }
    audit.append("pipeline.service", "run.completed", run_id, {"kpis": kpis})
    result = PipelineResult(
        metadata=metadata,
        kpis=kpis,
        source_stats=source_stats,
        records=canonical,
        quality_issues=canonical_issues,
        anomalies=anomalies,
        duplicates=duplicates,
        audit_log=audit.entries,
        quality_rules=rules["rules"],
    )
    if persist:
        warehouse_dir = data_dir / "warehouse"
        write_snapshot(result, warehouse_dir)
        write_powerbi_export(result, warehouse_dir)
        write_warehouse(result, warehouse_dir / "analytics.db")
    return result

