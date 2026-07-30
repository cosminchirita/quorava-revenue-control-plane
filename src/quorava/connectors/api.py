from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from ..models import RawRow


class JsonApiConnector:
    def __init__(self, endpoint: str | Path, timeout_seconds: float = 3.0) -> None:
        self.endpoint = str(endpoint)
        self.timeout_seconds = timeout_seconds

    def _load(self) -> dict:
        parsed = urlparse(self.endpoint)
        if parsed.scheme in ("http", "https"):
            request = Request(self.endpoint, headers={"Accept": "application/json", "User-Agent": "Quorava-Demo/1.0"})
            with urlopen(request, timeout=self.timeout_seconds) as response:  # nosec B310 - schemes are allowlisted
                if response.status != 200:
                    raise RuntimeError(f"API returned HTTP {response.status}")
                if "application/json" not in response.headers.get("Content-Type", ""):
                    raise RuntimeError("API response is not JSON")
                body = response.read(1_048_577)
                if len(body) > 1_048_576:
                    raise RuntimeError("API payload exceeds 1 MiB demo limit")
                return json.loads(body)
        path = Path(self.endpoint)
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)

    def read(self) -> list[RawRow]:
        document = self._load()
        items = document.get("items", [])
        if not isinstance(items, list):
            raise ValueError("API contract violation: 'items' must be an array")
        return [
            RawRow(
                source_type="api",
                source_ref=f"crm-api:item:{index}",
                source_row=index,
                payload=item,
            )
            for index, item in enumerate(items, start=1)
            if isinstance(item, dict)
        ]

