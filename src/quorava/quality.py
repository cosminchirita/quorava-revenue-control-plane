from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from .models import QualityIssue, RevenueRecord
from .utils import stable_hash


SEVERITY_PENALTY = {"critical": 35, "high": 20, "medium": 10, "low": 4}


def _issue(record: RevenueRecord, rule_id: str, severity: str, field: str, message: str, observed: Any) -> QualityIssue:
    return QualityIssue(
        issue_id=f"ISS-{stable_hash([record.record_id, rule_id, field], 10).upper()}",
        record_id=record.record_id,
        rule_id=rule_id,
        severity=severity,
        field=field,
        message=message,
        observed=observed,
    )


def validate_record(record: RevenueRecord, contract: dict[str, Any], as_of: date) -> list[QualityIssue]:
    issues: list[QualityIssue] = []
    for field in contract["required_fields"]:
        value = getattr(record, field, None)
        if value in (None, "", "unknown"):
            issues.append(_issue(record, "DQ-001", "critical", field, "Required value is missing", value))

    expected_net = round(record.gross_amount - record.discount_amount, 2)
    if abs(expected_net - record.net_amount) > float(contract["amount_tolerance"]):
        issues.append(
            _issue(
                record,
                "DQ-002",
                "high",
                "net_amount",
                "Gross amount less discount does not reconcile to net amount",
                {"expected": expected_net, "actual": record.net_amount},
            )
        )

    if record.currency not in contract["allowed_currencies"]:
        issues.append(_issue(record, "DQ-003", "high", "currency", "Unsupported currency", record.currency))

    try:
        transaction_date = date.fromisoformat(record.transaction_date)
        limit = as_of + timedelta(days=int(contract["max_future_days"]))
        if transaction_date > limit:
            issues.append(_issue(record, "DQ-004", "medium", "transaction_date", "Date is beyond the allowed future window", record.transaction_date))
    except ValueError:
        issues.append(_issue(record, "DQ-004", "medium", "transaction_date", "Date is not ISO-8601", record.transaction_date))

    if record.status not in contract["allowed_statuses"]:
        issues.append(_issue(record, "DQ-005", "medium", "status", "Status is outside the canonical domain", record.status))

    negative_fields = [
        field
        for field in ("gross_amount", "discount_amount", "net_amount", "cost_amount")
        if getattr(record, field) < 0
    ]
    if negative_fields:
        issues.append(_issue(record, "DQ-006", "high", ",".join(negative_fields), "Amounts must be non-negative", negative_fields))

    return issues


def apply_quality_scores(records: list[RevenueRecord], issues: list[QualityIssue]) -> None:
    by_record: dict[str, list[QualityIssue]] = {}
    for issue in issues:
        by_record.setdefault(issue.record_id, []).append(issue)
    for record in records:
        record_issues = by_record.get(record.record_id, [])
        penalty = sum(SEVERITY_PENALTY.get(issue.severity, 5) for issue in record_issues)
        record.quality_score = float(max(0, 100 - penalty))
        record.issue_count = len(record_issues)


def aggregate_quality(records: list[RevenueRecord], issues: list[QualityIssue]) -> dict[str, Any]:
    total = len(records) or 1
    passed = sum(1 for record in records if record.issue_count == 0)
    severity_counts = {severity: 0 for severity in ("critical", "high", "medium", "low")}
    for issue in issues:
        severity_counts[issue.severity] = severity_counts.get(issue.severity, 0) + 1
    return {
        "score": round(sum(record.quality_score for record in records) / total, 1),
        "pass_rate": round(passed / total * 100, 1),
        "records_passed": passed,
        "records_failed": len(records) - passed,
        "issue_count": len(issues),
        "severity_counts": severity_counts,
    }

