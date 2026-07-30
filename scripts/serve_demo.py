from __future__ import annotations

import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from quorava.api_server import serve  # noqa: E402


if __name__ == "__main__":
    serve(ROOT, os.getenv("QUORAVA_HOST", "127.0.0.1"), int(os.getenv("QUORAVA_PORT", "8787")))

