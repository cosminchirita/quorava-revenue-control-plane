#!/usr/bin/env sh
set -eu
cd "$(dirname "$0")"
python3 -m venv .venv
. .venv/bin/activate
python -m pip install --disable-pip-version-check -e .
python scripts/bootstrap_demo.py
python -m quorava serve --host 127.0.0.1 --port 8787
