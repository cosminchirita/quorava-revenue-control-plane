from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class RawRow:
    source_type: str
    source_ref: str
    source_row: int
    payload: dict[str, Any]


@dataclass
class RevenueRecord:
    record_id: str
    source_type: str
    source_ref: str
    source_row: int
    order_id: str
    customer_id: str
    customer_label: str
    transaction_date: str
    region: str
    country: str
    channel: str
    product_family: str
    currency: str
    gross_amount: float
    discount_amount: float
    net_amount: float
    cost_amount: float
    gross_eur: float
    net_eur: float
    cost_eur: float
    margin_eur: float
    status: str
    lineage_hash: str
    quality_score: float = 100.0
    issue_count: int = 0

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class QualityIssue:
    issue_id: str
    record_id: str
    rule_id: str
    severity: str
    field: str
    message: str
    observed: Any

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class Anomaly:
    anomaly_id: str
    record_id: str
    order_id: str
    severity: str
    risk_score: int
    anomaly_type: str
    title: str
    explanation: str
    evidence: list[str]
    recommended_action: str
    model_version: str = "robust-rules-v1.0"

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class AuditEntry:
    sequence: int
    timestamp: str
    actor: str
    action: str
    object_ref: str
    payload_hash: str
    previous_hash: str
    entry_hash: str

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class PipelineResult:
    metadata: dict[str, Any]
    kpis: dict[str, Any]
    source_stats: list[dict[str, Any]]
    records: list[RevenueRecord]
    quality_issues: list[QualityIssue]
    anomalies: list[Anomaly]
    duplicates: list[dict[str, Any]]
    audit_log: list[AuditEntry]
    quality_rules: list[dict[str, Any]] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "metadata": self.metadata,
            "kpis": self.kpis,
            "source_stats": self.source_stats,
            "records": [item.as_dict() for item in self.records],
            "quality_issues": [item.as_dict() for item in self.quality_issues],
            "anomalies": [item.as_dict() for item in self.anomalies],
            "duplicates": self.duplicates,
            "audit_log": [item.as_dict() for item in self.audit_log],
            "quality_rules": self.quality_rules,
        }

