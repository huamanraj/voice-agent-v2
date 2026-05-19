"""Structured per-call JSONL logger."""

import asyncio
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


class AsyncCallLogger:
    def __init__(
        self,
        *,
        call_id: str,
        log_dir: Path,
        queue_maxsize: int = 2000,
        common: dict[str, Any] | None = None,
    ) -> None:
        self.call_id = call_id
        self.log_dir = log_dir
        self.common = common or {}
        self._queue: asyncio.Queue[dict[str, Any] | None] = asyncio.Queue(queue_maxsize)
        self._task: asyncio.Task[None] | None = None
        self.dropped_logs = 0

    def start(self) -> None:
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self._writer_loop(), name=f"{self.call_id}:call_logger")

    def emit(
        self,
        event_name: str,
        *,
        turn_id: int | None = None,
        sequence_id: int | None = None,
        message_id: str | None = None,
        provider: str | None = None,
        state: str | None = None,
        **details: Any,
    ) -> None:
        payload = {
            "event_name": event_name,
            "call_id": self.call_id,
            "turn_id": turn_id,
            "sequence_id": sequence_id,
            "message_id": message_id,
            "provider": provider,
            "timestamp_ms": now_ms(),
            **self.common,
            "state": state,
            "details": details,
        }
        try:
            self._queue.put_nowait(payload)
        except asyncio.QueueFull:
            self.dropped_logs += 1

    async def stop(self, timeout_seconds: float = 1.0) -> None:
        if self._task is None:
            return
        with_timeout = timeout_seconds if timeout_seconds > 0 else None
        try:
            self._queue.put_nowait(None)
        except asyncio.QueueFull:
            _ = self._queue.get_nowait()
            self._queue.task_done()
            self._queue.put_nowait(None)
        if with_timeout is None:
            await self._task
            return
        try:
            await asyncio.wait_for(self._task, with_timeout)
        except asyncio.TimeoutError:
            self._task.cancel()
            await asyncio.gather(self._task, return_exceptions=True)

    async def _writer_loop(self) -> None:
        while True:
            payload = await self._queue.get()
            try:
                if payload is None:
                    break
                await asyncio.to_thread(self._write_payload, payload)
            finally:
                self._queue.task_done()

    def _write_payload(self, payload: dict[str, Any]) -> None:
        date_dir = datetime.now(UTC).strftime("%Y-%m-%d")
        path = self.log_dir / date_dir / f"{self.call_id}.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as log_file:
            log_file.write(json.dumps(payload, ensure_ascii=False, default=str) + "\n")
