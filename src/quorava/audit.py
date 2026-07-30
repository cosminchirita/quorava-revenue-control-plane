from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from .models import AuditEntry
from .utils import stable_hash


class AuditChain:
    def __init__(self, started_at: str) -> None:
        self.entries: list[AuditEntry] = []
        self._base_time = datetime.fromisoformat(started_at.replace("Z", "+00:00")).astimezone(timezone.utc)

    def append(self, actor: str, action: str, object_ref: str, payload: Any) -> AuditEntry:
        sequence = len(self.entries) + 1
        previous_hash = self.entries[-1].entry_hash if self.entries else "GENESIS"
        timestamp = (self._base_time + timedelta(seconds=sequence)).isoformat().replace("+00:00", "Z")
        payload_hash = stable_hash(payload, 32)
        entry_hash = stable_hash(
            {
                "sequence": sequence,
                "timestamp": timestamp,
                "actor": actor,
                "action": action,
                "object_ref": object_ref,
                "payload_hash": payload_hash,
                "previous_hash": previous_hash,
            },
            32,
        )
        entry = AuditEntry(sequence, timestamp, actor, action, object_ref, payload_hash, previous_hash, entry_hash)
        self.entries.append(entry)
        return entry


def verify_chain(entries: list[dict[str, Any]] | list[AuditEntry]) -> bool:
    previous_hash = "GENESIS"
    for item in entries:
        entry = item.as_dict() if isinstance(item, AuditEntry) else item
        if entry["previous_hash"] != previous_hash:
            return False
        expected = stable_hash(
            {
                "sequence": entry["sequence"],
                "timestamp": entry["timestamp"],
                "actor": entry["actor"],
                "action": entry["action"],
                "object_ref": entry["object_ref"],
                "payload_hash": entry["payload_hash"],
                "previous_hash": entry["previous_hash"],
            },
            32,
        )
        if expected != entry["entry_hash"]:
            return False
        previous_hash = entry["entry_hash"]
    return True

