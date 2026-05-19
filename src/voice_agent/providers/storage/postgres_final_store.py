"""Postgres durable call store with local retry fallback."""

import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


class PostgresFinalStore:
    provider_name = "postgres"

    def __init__(
        self,
        *,
        dsn: str,
        connect_timeout_seconds: float = 3.0,
        save_timeout_seconds: float = 5.0,
        retry_dir: str = "./logs/retry",
        pool: Any | None = None,
    ) -> None:
        self.dsn = dsn
        self.connect_timeout_seconds = connect_timeout_seconds
        self.save_timeout_seconds = save_timeout_seconds
        self.retry_dir = Path(retry_dir)
        self._pool = pool

    async def _get_pool(self) -> Any:
        if self._pool is not None:
            return self._pool
        try:
            import asyncpg
        except ImportError as exc:
            raise RuntimeError(
                "PostgresFinalStore requires the 'asyncpg' package. Install project dependencies before using Postgres."
            ) from exc
        self._pool = await asyncpg.create_pool(
            dsn=self.dsn,
            command_timeout=self.save_timeout_seconds,
            timeout=self.connect_timeout_seconds,
            min_size=1,
            max_size=5,
        )
        return self._pool

    async def save_call(self, call_id: str, record: dict[str, Any]) -> None:
        try:
            await asyncio.wait_for(self._save_call(call_id, record), timeout=self.save_timeout_seconds)
        except Exception as exc:
            await asyncio.to_thread(self._write_retry_file, call_id, record, exc)

    async def _save_call(self, call_id: str, record: dict[str, Any]) -> None:
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            async with conn.transaction():
                await conn.execute(
                    """
                    INSERT INTO calls (
                        call_id, agent_id, caller, started_at, ended_at, end_reason,
                        transcript_summary, error_count, raw_record
                    )
                    VALUES ($1, $2, $3, to_timestamp($4 / 1000.0), to_timestamp($5 / 1000.0), $6, $7, $8, $9::jsonb)
                    ON CONFLICT (call_id) DO UPDATE SET
                        ended_at = EXCLUDED.ended_at,
                        end_reason = EXCLUDED.end_reason,
                        transcript_summary = EXCLUDED.transcript_summary,
                        error_count = EXCLUDED.error_count,
                        raw_record = EXCLUDED.raw_record
                    """,
                    call_id,
                    record.get("agent_id"),
                    record.get("caller"),
                    _int_or_now(record.get("started_ms")),
                    _int_or_now(record.get("ended_ms")),
                    record.get("reason"),
                    record.get("transcript_summary"),
                    len(record.get("errors", [])),
                    json.dumps(record, ensure_ascii=False),
                )
                await conn.execute("DELETE FROM turns WHERE call_id = $1", call_id)
                for index, turn in enumerate(record.get("turns", []), start=1):
                    await conn.execute(
                        """
                        INSERT INTO turns (
                            call_id, turn_index, speaker, text, full_text, heard_text,
                            interrupted, latency_ms, created_at
                        )
                        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, to_timestamp($9 / 1000.0))
                        """,
                        call_id,
                        index,
                        turn.get("speaker"),
                        turn.get("text"),
                        turn.get("full_text"),
                        turn.get("heard_text"),
                        bool(turn.get("interrupted", False)),
                        turn.get("latency_ms"),
                        _int_or_now(turn.get("timestamp_ms") or turn.get("created_ms")),
                    )
                await conn.execute("DELETE FROM call_metrics WHERE call_id = $1", call_id)
                metrics = record.get("metrics", {})
                await conn.execute(
                    """
                    INSERT INTO call_metrics (
                        call_id, avg_stt_latency_ms, avg_llm_first_token_ms,
                        avg_tts_first_audio_ms, avg_voice_to_voice_ms,
                        interruption_count, agent_interrupted_user_count,
                        audio_drop_count, provider_error_count, raw_metrics
                    )
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10::jsonb)
                    """,
                    call_id,
                    metrics.get("avg_stt_final_latency_ms"),
                    metrics.get("avg_llm_first_token_ms"),
                    metrics.get("avg_tts_first_audio_ms"),
                    metrics.get("avg_voice_to_voice_ms"),
                    metrics.get("interruption_count"),
                    metrics.get("agent_interrupted_user_count"),
                    metrics.get("audio_drop_count"),
                    metrics.get("provider_error_count"),
                    json.dumps(metrics, ensure_ascii=False),
                )
                await conn.execute("DELETE FROM provider_errors WHERE call_id = $1", call_id)
                for error in record.get("provider_errors", []):
                    await conn.execute(
                        """
                        INSERT INTO provider_errors (
                            call_id, provider, error_type, error_code, message, retryable, details
                        )
                        VALUES ($1, $2, $3, $4, $5, $6, $7::jsonb)
                        """,
                        call_id,
                        error.get("provider"),
                        error.get("error_type"),
                        error.get("error_code"),
                        error.get("message"),
                        bool(error.get("retryable", False)),
                        json.dumps(error.get("details", {}), ensure_ascii=False),
                    )

    def _write_retry_file(self, call_id: str, record: dict[str, Any], exc: Exception) -> None:
        self.retry_dir.mkdir(parents=True, exist_ok=True)
        path = self.retry_dir / f"{call_id}-{datetime.now(UTC).strftime('%Y%m%d%H%M%S%f')}.json"
        payload = {
            "call_id": call_id,
            "error": f"{exc.__class__.__name__}: {exc}",
            "record": record,
        }
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    async def close(self) -> None:
        if self._pool is not None:
            close = getattr(self._pool, "close", None)
            if close is not None:
                result = close()
                if hasattr(result, "__await__"):
                    await result


def _int_or_now(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return int(datetime.now(UTC).timestamp() * 1000)
