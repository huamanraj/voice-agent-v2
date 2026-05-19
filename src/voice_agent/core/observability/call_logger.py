"""Structured per-call JSONL logger."""

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from voice_agent.contracts.packets import now_ms


@dataclass(slots=True)
class CallLogger:
    call_id: str
    log_dir: Path
    common: dict[str, Any] = field(default_factory=dict)

    def _log_path(self) -> Path:
        date_dir = datetime.now(UTC).strftime("%Y-%m-%d")
        return self.log_dir / date_dir / f"{self.call_id}.jsonl"

    def emit(self, event_name: str, **details: Any) -> None:
        path = self._log_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "event_name": event_name,
            "call_id": self.call_id,
            "timestamp_ms": now_ms(),
            **self.common,
            "details": details,
        }
        with path.open("a", encoding="utf-8") as log_file:
            log_file.write(json.dumps(payload, ensure_ascii=False) + "\n")
