from __future__ import annotations

from statistics import median

from .models import Anomaly, RevenueRecord
from .utils import stable_hash


def _severity(score: int) -> str:
    if score >= 80:
        return "critical"
    if score >= 60:
        return "high"
    if score >= 35:
        return "medium"
    return "low"


def detect_anomalies(records: list[RevenueRecord]) -> list[Anomaly]:
    if not records:
        return []
    values = [record.net_eur for record in records]
    centre = median(values)
    absolute_deviations = [abs(value - centre) for value in values]
    mad = median(absolute_deviations) or 1.0
    anomalies: list[Anomaly] = []

    for record in records:
        evidence: list[str] = []
        score = 0
        anomaly_type = "statistical_outlier"
        title = "Revenue value outside robust baseline"
        recommendation = "Validate the order against the commercial approval and source ledger."

        robust_z = 0.6745 * abs(record.net_eur - centre) / mad
        if robust_z >= 2.5:
            score += min(55, round(robust_z * 12))
            evidence.append(f"Robust z-score {robust_z:.2f} against median EUR {centre:,.0f}")

        discount_rate = record.discount_amount / record.gross_amount if record.gross_amount else 0
        if discount_rate >= 0.30:
            score += 32
            anomaly_type = "discount_leakage"
            title = "Discount exceeds commercial tolerance"
            recommendation = "Confirm discount authority and attach the approved exception."
            evidence.append(f"Discount rate {discount_rate:.1%} exceeds the 30% policy threshold")

        margin_rate = record.margin_eur / record.net_eur if record.net_eur else 0
        if margin_rate < 0.20:
            score += 38
            anomaly_type = "margin_erosion"
            title = "Low or negative contribution margin"
            recommendation = "Review cost allocation, pricing and revenue recognition before sign-off."
            evidence.append(f"Contribution margin {margin_rate:.1%} is below the 20% floor")

        if record.issue_count:
            score += min(30, record.issue_count * 12)
            evidence.append(f"{record.issue_count} data-quality exception(s) reduce confidence")

        if score < 25:
            continue
        score = min(99, score)
        anomalies.append(
            Anomaly(
                anomaly_id=f"ANM-{stable_hash([record.record_id, anomaly_type], 10).upper()}",
                record_id=record.record_id,
                order_id=record.order_id,
                severity=_severity(score),
                risk_score=score,
                anomaly_type=anomaly_type,
                title=title,
                explanation=(
                    "The explainable detector combines a median absolute deviation baseline, "
                    "commercial policy thresholds and data-quality confidence penalties."
                ),
                evidence=evidence,
                recommended_action=recommendation,
            )
        )

    return sorted(anomalies, key=lambda item: (-item.risk_score, item.order_id))

