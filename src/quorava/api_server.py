from __future__ import annotations

import csv
import io
import json
import mimetypes
import os
import threading
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

from .audit import verify_chain
from .pipeline import run_pipeline


class DemoState:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.lock = threading.Lock()
        self.snapshot = run_pipeline(root).as_dict()

    def refresh(self) -> dict:
        with self.lock:
            self.snapshot = run_pipeline(self.root).as_dict()
            return self.snapshot


def _powerbi_csv(snapshot: dict) -> bytes:
    fields = [
        "record_id", "order_id", "transaction_date", "region", "country", "channel",
        "product_family", "gross_eur", "net_eur", "cost_eur", "margin_eur", "status",
        "quality_score", "source_type", "lineage_hash",
    ]
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=fields)
    writer.writeheader()
    for record in snapshot["records"]:
        writer.writerow({field: record[field] for field in fields})
    return buffer.getvalue().encode("utf-8")


def make_handler(state: DemoState, web_root: Path):
    resolved_web_root = web_root.resolve()

    class Handler(BaseHTTPRequestHandler):
        server_version = "QuoravaDemo/1.0"

        def log_message(self, format_string: str, *args) -> None:
            print(f"[quorava] {self.address_string()} - {format_string % args}")

        def _security_headers(self) -> None:
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("X-Frame-Options", "DENY")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("Permissions-Policy", "camera=(), microphone=(), geolocation=(), payment=()")
            self.send_header(
                "Content-Security-Policy",
                "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; "
                "connect-src 'self'; font-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'",
            )
            self.send_header("Cache-Control", "no-store")

        def _send_json(self, payload: object, status: int = 200) -> None:
            encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
            self.send_response(status)
            self._security_headers()
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)

        def _send_bytes(self, payload: bytes, content_type: str, status: int = 200, filename: str | None = None) -> None:
            self.send_response(status)
            self._security_headers()
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(payload)))
            if filename:
                self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
            self.end_headers()
            self.wfile.write(payload)

        def _api_get(self, path: str, query: dict[str, list[str]]) -> bool:
            snapshot = state.snapshot
            if path == "/api/health":
                self._send_json({"status": "ok", "service": "quorava-demo-api", "run_id": snapshot["metadata"]["run_id"]})
            elif path == "/api/overview":
                self._send_json({
                    "metadata": snapshot["metadata"],
                    "kpis": snapshot["kpis"],
                    "source_stats": snapshot["source_stats"],
                    "anomalies": snapshot["anomalies"][:5],
                    "recent_audit": snapshot["audit_log"][-5:][::-1],
                })
            elif path == "/api/records":
                search = query.get("search", [""])[0].strip().lower()[:80]
                source = query.get("source", [""])[0].strip().lower()[:20]
                records = snapshot["records"]
                if source:
                    records = [item for item in records if item["source_type"] == source]
                if search:
                    records = [
                        item for item in records
                        if search in " ".join(str(item.get(key, "")) for key in ("order_id", "customer_label", "region", "country", "product_family")).lower()
                    ]
                self._send_json({"items": records, "total": len(records)})
            elif path.startswith("/api/records/"):
                record_id = unquote(path.rsplit("/", 1)[-1])[:80]
                record = next((item for item in snapshot["records"] if item["record_id"] == record_id), None)
                if not record:
                    self._send_json({"error": "record_not_found"}, HTTPStatus.NOT_FOUND)
                else:
                    self._send_json({
                        "record": record,
                        "quality_issues": [item for item in snapshot["quality_issues"] if item["record_id"] == record_id],
                        "anomalies": [item for item in snapshot["anomalies"] if item["record_id"] == record_id],
                    })
            elif path == "/api/anomalies":
                self._send_json({"items": snapshot["anomalies"], "total": len(snapshot["anomalies"])})
            elif path == "/api/quality":
                self._send_json({
                    "summary": snapshot["metadata"]["quality_summary"],
                    "rules": snapshot["quality_rules"],
                    "issues": snapshot["quality_issues"],
                })
            elif path == "/api/lineage":
                self._send_json({
                    "nodes": [
                        {"id": "excel", "label": "Excel workbooks", "kind": "source"},
                        {"id": "api", "label": "CRM REST API", "kind": "source"},
                        {"id": "sql", "label": "ERP SQL ledger", "kind": "source"},
                        {"id": "normalize", "label": "Canonical mapping", "kind": "process"},
                        {"id": "quality", "label": "Contract controls", "kind": "process"},
                        {"id": "dedup", "label": "Identity resolution", "kind": "process"},
                        {"id": "risk", "label": "Explainable anomaly scoring", "kind": "process"},
                        {"id": "warehouse", "label": "Revenue warehouse", "kind": "target"},
                        {"id": "powerbi", "label": "Power BI model", "kind": "target"},
                    ],
                    "edges": [
                        ["excel", "normalize"], ["api", "normalize"], ["sql", "normalize"],
                        ["normalize", "quality"], ["quality", "dedup"], ["dedup", "risk"],
                        ["risk", "warehouse"], ["warehouse", "powerbi"],
                    ],
                    "records": snapshot["records"],
                })
            elif path == "/api/audit":
                self._send_json({"verified": verify_chain(snapshot["audit_log"]), "items": snapshot["audit_log"]})
            elif path == "/api/powerbi/export.csv":
                self._send_bytes(_powerbi_csv(snapshot), "text/csv; charset=utf-8", filename="quorava_revenue_facts.csv")
            elif path == "/api/source/crm":
                payload = (state.root / "data" / "api" / "crm_snapshot.json").read_bytes()
                self._send_bytes(payload, "application/json; charset=utf-8")
            else:
                return False
            return True

        def do_GET(self) -> None:  # noqa: N802
            parsed = urlparse(self.path)
            if parsed.path.startswith("/api/"):
                if not self._api_get(parsed.path, parse_qs(parsed.query)):
                    self._send_json({"error": "endpoint_not_found"}, HTTPStatus.NOT_FOUND)
                return

            relative = "index.html" if parsed.path in ("", "/") else unquote(parsed.path.lstrip("/"))
            candidate = (resolved_web_root / relative).resolve()
            if resolved_web_root not in candidate.parents and candidate != resolved_web_root:
                self._send_json({"error": "invalid_path"}, HTTPStatus.BAD_REQUEST)
                return
            if not candidate.is_file():
                candidate = resolved_web_root / "index.html"
            content_type = mimetypes.guess_type(candidate.name)[0] or "application/octet-stream"
            if content_type.startswith("text/") or content_type in ("application/javascript", "application/json"):
                content_type += "; charset=utf-8"
            self._send_bytes(candidate.read_bytes(), content_type)

        def do_POST(self) -> None:  # noqa: N802
            parsed = urlparse(self.path)
            if parsed.path != "/api/runs":
                self._send_json({"error": "endpoint_not_found"}, HTTPStatus.NOT_FOUND)
                return
            role = self.headers.get("X-Demo-Role", os.getenv("QUORAVA_DEMO_ROLE", "analyst"))
            if role not in ("analyst", "admin"):
                self._send_json({"error": "forbidden", "message": "Analyst role is required"}, HTTPStatus.FORBIDDEN)
                return
            max_bytes = int(os.getenv("QUORAVA_MAX_REQUEST_BYTES", "1048576"))
            length = int(self.headers.get("Content-Length", "0"))
            if length > max_bytes:
                self._send_json({"error": "payload_too_large"}, HTTPStatus.REQUEST_ENTITY_TOO_LARGE)
                return
            if length:
                self.rfile.read(length)
            snapshot = state.refresh()
            self._send_json({"status": "completed", "run_id": snapshot["metadata"]["run_id"], "kpis": snapshot["kpis"]}, HTTPStatus.CREATED)

        def do_OPTIONS(self) -> None:  # noqa: N802
            self._send_json({"error": "cross_origin_requests_not_supported"}, HTTPStatus.METHOD_NOT_ALLOWED)

    return Handler


def create_server(root: Path, host: str = "127.0.0.1", port: int = 8787) -> ThreadingHTTPServer:
    state = DemoState(root)
    handler = make_handler(state, root / "web")
    return ThreadingHTTPServer((host, port), handler)


def serve(root: Path, host: str = "127.0.0.1", port: int = 8787) -> None:
    server = create_server(root, host, port)
    print(f"Quorava demo is running at http://{host}:{server.server_port}")
    print("Synthetic data only. Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()

