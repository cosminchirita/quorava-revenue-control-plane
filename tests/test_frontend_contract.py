from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class FrontendContractTests(unittest.TestCase):
    def test_navigation_exposes_all_product_areas(self) -> None:
        html = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
        for view in ("overview", "sources", "quality", "anomalies", "lineage", "audit", "powerbi"):
            self.assertIn(f'data-view="{view}"', html)

    def test_csp_compatible_assets(self) -> None:
        html = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
        self.assertNotIn("<script>", html)
        self.assertIn('src="/app.js"', html)
        self.assertIn('href="/styles.css"', html)

    def test_demo_boundary_is_visible(self) -> None:
        html = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
        script = (ROOT / "web" / "app.js").read_text(encoding="utf-8")
        self.assertIn("Synthetic data", html)
        self.assertIn("never approves, posts or moves funds", script)


if __name__ == "__main__":
    unittest.main()

