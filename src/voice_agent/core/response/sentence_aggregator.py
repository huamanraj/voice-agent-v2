"""Aggregate streaming LLM tokens into TTS-friendly sentence chunks."""

import asyncio
import re
from collections.abc import AsyncIterator
from dataclasses import dataclass, field

from voice_agent.contracts.packets import now_ms

SENTENCE_ENDINGS = (".", "?", "!", "।")
PAUSE_MARKERS = (",", ";", ":")


@dataclass(slots=True)
class SentenceAggregator:
    min_chars: int = 80
    max_chars: int = 160
    timeout_ms: int = 500
    _buffer: list[str] = field(default_factory=list)
    _started_ms: int | None = None

    def add(self, token: str, timestamp_ms: int | None = None) -> list[str]:
        if not token:
            return []
        if self._started_ms is None:
            self._started_ms = timestamp_ms or now_ms()
        self._buffer.append(token)

        text = self.current_text()
        if not text:
            return []
        if _ends_sentence(text):
            return [self.flush()]
        if len(text) >= self.max_chars:
            return [self._flush_at_word_boundary()]
        if len(text) >= self.min_chars and _ends_pause(text):
            return [self.flush()]
        return []

    def flush_due(self, timestamp_ms: int | None = None) -> str | None:
        if not self._buffer or self._started_ms is None:
            return None
        ts_ms = timestamp_ms or now_ms()
        if ts_ms - self._started_ms < self.timeout_ms:
            return None
        return self.flush()

    def seconds_until_flush(self, timestamp_ms: int | None = None) -> float | None:
        if not self._buffer or self._started_ms is None:
            return None
        elapsed_ms = (timestamp_ms or now_ms()) - self._started_ms
        return max(0.0, (self.timeout_ms - elapsed_ms) / 1000)

    def flush(self) -> str:
        text = sanitize_for_speech(self.current_text())
        self._buffer.clear()
        self._started_ms = None
        return text

    def current_text(self) -> str:
        return "".join(self._buffer)

    def _flush_at_word_boundary(self) -> str:
        text = self.current_text()
        split_index = text.rfind(" ", 0, self.max_chars)
        if split_index <= 0:
            return self.flush()

        ready = sanitize_for_speech(text[:split_index])
        remainder = text[split_index:]
        self._buffer = [remainder]
        self._started_ms = now_ms() if remainder.strip() else None
        return ready


async def aggregate_token_stream(
    tokens: AsyncIterator[str],
    *,
    min_chars: int = 80,
    max_chars: int = 160,
    timeout_ms: int = 500,
) -> AsyncIterator[str]:
    aggregator = SentenceAggregator(
        min_chars=min_chars,
        max_chars=max_chars,
        timeout_ms=timeout_ms,
    )
    queue: asyncio.Queue[str | None] = asyncio.Queue()

    async def produce() -> None:
        try:
            async for token in tokens:
                await queue.put(token)
        finally:
            await queue.put(None)

    producer = asyncio.create_task(produce())
    try:
        while True:
            timeout = aggregator.seconds_until_flush()
            try:
                item = await asyncio.wait_for(queue.get(), timeout=timeout)
            except asyncio.TimeoutError:
                chunk = aggregator.flush_due()
                if chunk:
                    yield chunk
                continue

            if item is None:
                chunk = aggregator.flush()
                if chunk:
                    yield chunk
                break

            for chunk in aggregator.add(item):
                if chunk:
                    yield chunk
    finally:
        if not producer.done():
            producer.cancel()
            try:
                await producer
            except asyncio.CancelledError:
                pass


def sanitize_for_speech(text: str) -> str:
    cleaned = re.sub(r"```.*?```", " ", text, flags=re.DOTALL)
    cleaned = cleaned.replace("`", "")
    cleaned = re.sub(r"^\s{0,3}#{1,6}\s*", "", cleaned, flags=re.MULTILINE)
    cleaned = re.sub(r"^\s*[-*+]\s+", "", cleaned, flags=re.MULTILINE)
    cleaned = cleaned.replace("**", "").replace("__", "")
    return re.sub(r"\s+", " ", cleaned).strip()


def _ends_sentence(text: str) -> bool:
    return text.rstrip().endswith(SENTENCE_ENDINGS)


def _ends_pause(text: str) -> bool:
    return text.rstrip().endswith(PAUSE_MARKERS)
