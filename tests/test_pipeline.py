from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from quorava.audit import verify_chain  # noqa: E402
from quorava.pipeline import run_pipeline  # noqa: E402


class PipelineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.result = run_pipeline(ROOT, persist=False)

    def test_ingests_all_source_types(self) -> None:
        self.assertEqual({item["source_type"] for item in self.result.source_stats}, {"excel", "api", "sql"})
        self.assertEqual(self.result.kpis["raw_records"], 27)

    def test_deduplicates_with_deterministic_source_precedence(self) -> None:
        self.assertEqual(self.result.kpis["duplicates_removed"], 5)
        order = next(record for record in self.result.records if record.order_id == "Q-260701")
        self.assertEqual(order.source_type, "sql")

    def test_normalizes_currency_to_eur(self) -> None:
        order = next(record for record in self.result.records if record.order_id == "Q-260711")
        self.assertEqual(order.currency, "RON")
        self.assertAlmostEqual(order.net_eur, 54672.0, places=2)

    def test_revenue_and_margin_reconcile(self) -> None:
        self.assertAlmostEqual(sum(item.net_eur for item in self.result.records), self.result.kpis["net_revenue_eur"], places=2)
        self.assertAlmostEqual(sum(item.margin_eur for item in self.result.records), self.result.kpis["margin_eur"], places=2)

    def test_quality_exceptions_are_visible_not_silently_fixed(self) -> None:
        issue_rules = {issue.rule_id for issue in self.result.quality_issues}
        self.assertIn("DQ-002", issue_rules)
        self.assertIn("DQ-004", issue_rules)
        affected = {issue.record_id for issue in self.result.quality_issues}
        self.assertTrue(all(any(record.record_id == record_id for record in self.result.records) for record_id in affected))

    def test_anomalies_contain_explanation_and_evidence(self) -> None:
        self.assertGreaterEqual(len(self.result.anomalies), 3)
        self.assertTrue(all(item.evidence and item.recommended_action for item in self.result.anomalies))
        self.assertTrue(all(item.model_version == "robust-rules-v1.0" for item in self.result.anomalies))

    def test_audit_chain_verifies(self) -> None:
        self.assertTrue(verify_chain(self.result.audit_log))
        tampered = [item.as_dict() for item in self.result.audit_log]
        tampered[2]["action"] = "tampered.event"
        self.assertFalse(verify_chain(tampered))


if __name__ == "__main__":
    unittest.main()

