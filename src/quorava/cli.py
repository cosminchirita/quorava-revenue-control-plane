from __future__ import annotations

import argparse
import json
from pathlib import Path

from .api_server import serve
from .audit import verify_chain
from .pipeline import run_pipeline
from .utils import repo_root


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="quorava", description="Quorava Revenue Control Plane demo")
    subcommands = parser.add_subparsers(dest="command", required=True)

    run = subcommands.add_parser("run", help="Run the deterministic demo pipeline")
    run.add_argument("--root", type=Path, default=repo_root())
    run.add_argument("--api-url", default=None)

    server = subcommands.add_parser("serve", help="Start the dashboard and local API")
    server.add_argument("--root", type=Path, default=repo_root())
    server.add_argument("--host", default="127.0.0.1")
    server.add_argument("--port", type=int, default=8787)

    verify = subcommands.add_parser("verify", help="Verify pipeline invariants and audit chain")
    verify.add_argument("--root", type=Path, default=repo_root())
    return parser


def main() -> None:
    args = build_parser().parse_args()
    root = args.root.resolve()
    if args.command == "run":
        result = run_pipeline(root, api_endpoint=args.api_url)
        print(json.dumps({"run_id": result.metadata["run_id"], "kpis": result.kpis}, indent=2))
    elif args.command == "serve":
        serve(root, args.host, args.port)
    elif args.command == "verify":
        result = run_pipeline(root)
        if not verify_chain(result.audit_log):
            raise SystemExit("Audit chain verification failed")
        print(f"Verified {len(result.records)} canonical records and {len(result.audit_log)} chained audit events.")

