from __future__ import annotations

import json
import sys
import threading
import unittest
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from quorava.api_server import create_server  # noqa: E402


class ApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.server = create_server(ROOT, "127.0.0.1", 0)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = f"http://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls) -> None:
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=2)

    def get(self, path: str):
        with urlopen(self.base + path, timeout=3) as response:
            return response, response.read()

    def test_health_and_security_headers(self) -> None:
        response, body = self.get("/api/health")
        payload = json.loads(body)
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(response.headers["X-Frame-Options"], "DENY")
        self.assertIn("default-src 'self'", response.headers["Content-Security-Policy"])

    def test_overview_and_record_detail(self) -> None:
        _, body = self.get("/api/overview")
        overview = json.loads(body)
        self.assertEqual(len(overview["source_stats"]), 3)
        _, body = self.get("/api/records?search=Q-260701")
        records = json.loads(body)
        self.assertEqual(records["total"], 1)
        record_id = records["items"][0]["record_id"]
        _, body = self.get(f"/api/records/{record_id}")
        self.assertEqual(json.loads(body)["record"]["order_id"], "Q-260701")

    def test_powerbi_export_matches_canonical_grain(self) -> None:
        response, body = self.get("/api/powerbi/export.csv")
        self.assertIn("text/csv", response.headers["Content-Type"])
        self.assertEqual(len(body.decode("utf-8").strip().splitlines()), 23)

    def test_pipeline_rerun_requires_demo_analyst_role(self) -> None:
        forbidden = Request(self.base + "/api/runs", data=b"{}", method="POST", headers={"X-Demo-Role": "viewer"})
        with self.assertRaises(HTTPError) as context:
            urlopen(forbidden, timeout=3)
        self.assertEqual(context.exception.code, 403)

        allowed = Request(self.base + "/api/runs", data=b"{}", method="POST", headers={"X-Demo-Role": "analyst", "Content-Type": "application/json"})
        with urlopen(allowed, timeout=5) as response:
            self.assertEqual(response.status, 201)
            self.assertEqual(json.loads(response.read())["status"], "completed")

    def test_path_traversal_is_rejected(self) -> None:
        request = Request(self.base + "/%2e%2e/%2e%2e/pyproject.toml")
        with self.assertRaises(HTTPError) as context:
            urlopen(request, timeout=3)
        self.assertEqual(context.exception.code, 400)


if __name__ == "__main__":
    unittest.main()

