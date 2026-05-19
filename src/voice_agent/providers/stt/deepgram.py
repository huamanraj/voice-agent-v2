"""Deepgram streaming speech-to-text adapter."""

import asyncio
import json
from collections import deque
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import suppress
from typing import Any, Protocol
from urllib.parse import urlencode

from voice_agent.contracts.audio import AudioCodec, AudioFrame
from voice_agent.contracts.capabilities import STTCapabilities
from voice_agent.contracts.events import ProviderError, SpeechStart, SpeechStop, TranscriptEvent
from voice_agent.contracts.packets import now_ms
from voice_agent.config import Settings, get_settings


class DeepgramWebSocket(Protocol):
    async def send(self, data: bytes | str) -> None: ...
    async def recv(self) -> str | bytes: ...
    async def close(self) -> None: ...


WebSocketFactory = Callable[[str, dict[str, str]], Awaitable[DeepgramWebSocket]]


class DeepgramSTT:
    provider_name = "deepgram"
    capabilities = STTCapabilities(
        supports_interim=True,
        supports_final=True,
        supports_vad_events=True,
        supports_language_detection=True,
        supports_code_switching=True,
        accepted_codecs=("mulaw_8k", "pcm16_8k", "pcm16_16k"),
    )

    def __init__(
        self,
        *,
        settings: Settings | None = None,
        api_key: str | None = None,
        websocket_factory: WebSocketFactory | None = None,
        target_codec: AudioCodec = "mulaw_8k",
        queue_maxsize: int = 300,
        reconnect_backoffs_seconds: tuple[float, ...] = (0.2, 0.5, 1.0),
        reconnect_buffer_ms: int = 2000,
        keepalive_seconds: float | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.api_key = api_key if api_key is not None else self.settings.deepgram_api_key
        self.websocket_factory = websocket_factory or _default_websocket_factory
        self.target_codec = target_codec
        self.reconnect_backoffs_seconds = reconnect_backoffs_seconds
        self.reconnect_buffer_ms = reconnect_buffer_ms
        self.keepalive_seconds = keepalive_seconds or float(self.settings.deepgram_keepalive_seconds)

        self.call_id: str | None = None
        self.language_hint: str | None = None
        self.started = False
        self.stopped = False
        self.reconnects = 0
        self.errors: list[ProviderError] = []
        self.last_metadata: dict[str, Any] | None = None

        self._websocket: DeepgramWebSocket | None = None
        self._connect_lock = asyncio.Lock()
        self._receiver_task: asyncio.Task[None] | None = None
        self._keepalive_task: asyncio.Task[None] | None = None
        self._transcripts: asyncio.Queue[TranscriptEvent | None] = asyncio.Queue(queue_maxsize)
        self._speech_events: asyncio.Queue[SpeechStart | SpeechStop | None] = asyncio.Queue(queue_maxsize)
        self._reconnect_buffer: deque[AudioFrame] = deque()
        self._reconnect_buffer_duration_ms = 0

    async def start(self, call_id: str, language_hint: str | None = None) -> None:
        if self.started:
            return
        if not self.api_key:
            raise ValueError("DEEPGRAM_API_KEY is required for Deepgram STT.")
        self.call_id = call_id
        self.language_hint = language_hint or self.settings.deepgram_language
        await self._connect_with_retries(raise_on_failure=True)
        self.started = True
        self._receiver_task = asyncio.create_task(self._receiver_loop())
        self._keepalive_task = asyncio.create_task(self._keepalive_loop())

    async def send_audio(self, frame: AudioFrame) -> None:
        if self.stopped:
            return
        if frame.codec not in self.capabilities.accepted_codecs:
            raise ValueError(f"Deepgram STT does not accept codec: {frame.codec}")
        if frame.codec != self.target_codec:
            raise ValueError(
                f"Deepgram STT expected {self.target_codec}; AudioRouter should convert {frame.codec} first."
            )

        websocket = self._websocket
        if websocket is None:
            self._buffer_frame(frame)
            await self._connect_with_retries(raise_on_failure=False)
            return

        try:
            await websocket.send(frame.data)
        except Exception as exc:
            self._record_error(
                "audio_send_failed",
                str(exc),
                retryable=True,
                details={"exception": exc.__class__.__name__},
            )
            self._buffer_frame(frame)
            await self._drop_connection()
            await self._connect_with_retries(raise_on_failure=False)

    async def transcripts(self) -> AsyncIterator[TranscriptEvent]:
        while True:
            event = await self._transcripts.get()
            if event is None:
                break
            yield event

    async def speech_events(self) -> AsyncIterator[SpeechStart | SpeechStop]:
        while True:
            event = await self._speech_events.get()
            if event is None:
                break
            yield event

    async def update_language_hint(self, language: str) -> None:
        self.language_hint = language

    async def stop(self) -> None:
        if self.stopped:
            return
        self.stopped = True
        websocket = self._websocket
        if websocket is not None:
            with suppress(Exception):
                await websocket.send(json.dumps({"type": "Finalize"}))
            with suppress(Exception):
                await websocket.send(json.dumps({"type": "CloseStream"}))
            with suppress(Exception):
                await websocket.close()
        self._websocket = None
        for task in (self._receiver_task, self._keepalive_task):
            if task is not None and not task.done():
                task.cancel()
                with suppress(asyncio.CancelledError):
                    await task
        await self._transcripts.put(None)
        await self._speech_events.put(None)

    def deepgram_url(self) -> str:
        params = {
            "model": self.settings.deepgram_model,
            "encoding": _encoding_for_codec(self.target_codec),
            "sample_rate": str(_sample_rate_for_codec(self.target_codec)),
            "channels": "1",
            "interim_results": "true",
            "vad_events": "true",
            "smart_format": "true",
            "endpointing": str(self.settings.deepgram_endpointing_ms),
            "utterance_end_ms": str(self.settings.deepgram_utterance_end_ms),
            "language": self.language_hint or self.settings.deepgram_language,
        }
        return f"{self.settings.deepgram_ws_url}?{urlencode(params)}"

    async def _receiver_loop(self) -> None:
        while not self.stopped:
            websocket = self._websocket
            if websocket is None:
                await asyncio.sleep(0.05)
                continue
            try:
                message = await websocket.recv()
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                self._record_error(
                    "receive_failed",
                    str(exc),
                    retryable=True,
                    details={"exception": exc.__class__.__name__},
                )
                await self._drop_connection()
                await self._connect_with_retries(raise_on_failure=False)
                continue
            await self._handle_message(message)

    async def _keepalive_loop(self) -> None:
        while not self.stopped:
            await asyncio.sleep(self.keepalive_seconds)
            websocket = self._websocket
            if websocket is None:
                continue
            try:
                await websocket.send(json.dumps({"type": "KeepAlive"}))
            except Exception as exc:
                self._record_error(
                    "keepalive_failed",
                    str(exc),
                    retryable=True,
                    details={"exception": exc.__class__.__name__},
                )
                await self._drop_connection()
                await self._connect_with_retries(raise_on_failure=False)

    async def _handle_message(self, message: str | bytes) -> None:
        if isinstance(message, bytes):
            return
        try:
            payload = json.loads(message)
        except json.JSONDecodeError as exc:
            self._record_error("invalid_json", str(exc), retryable=False)
            return

        message_type = payload.get("type")
        if message_type == "Results":
            await self._handle_results(payload)
        elif message_type == "SpeechStarted":
            await self._speech_events.put(
                SpeechStart(
                    call_id=self._call_id(),
                    ts_ms=now_ms(),
                    source="stt",
                    confidence=1.0,
                )
            )
        elif message_type == "UtteranceEnd":
            await self._speech_events.put(
                SpeechStop(
                    call_id=self._call_id(),
                    ts_ms=now_ms(),
                    source="stt",
                    confidence=1.0,
                )
            )
        elif message_type == "Metadata":
            self.last_metadata = payload
        elif message_type == "Error":
            self._record_error(
                "deepgram_error",
                str(payload.get("message") or payload),
                retryable=False,
                details=payload,
            )

    async def _handle_results(self, payload: dict[str, Any]) -> None:
        alternative = _first_alternative(payload)
        transcript = str(alternative.get("transcript") or "").strip()
        if not transcript:
            return

        start_seconds = _safe_float(payload.get("start"))
        duration_seconds = _safe_float(payload.get("duration"))
        start_ms = round(start_seconds * 1000) if start_seconds is not None else None
        end_ms = (
            round((start_seconds + duration_seconds) * 1000)
            if start_seconds is not None and duration_seconds is not None
            else None
        )
        await self._transcripts.put(
            TranscriptEvent(
                call_id=self._call_id(),
                text=transcript,
                is_final=bool(payload.get("is_final") or payload.get("speech_final")),
                confidence=float(alternative.get("confidence") or 0.0),
                language=_language_from_alternative(alternative, self.language_hint),
                start_ms=start_ms,
                end_ms=end_ms,
                provider=self.provider_name,
                asr_turn_id=_request_id(payload),
            )
        )

    async def _connect_with_retries(self, *, raise_on_failure: bool) -> bool:
        async with self._connect_lock:
            if self._websocket is not None or self.stopped:
                return self._websocket is not None
            delays = (0.0, *self.reconnect_backoffs_seconds)
            last_error: Exception | None = None
            for delay in delays:
                if delay:
                    await asyncio.sleep(delay)
                try:
                    self._websocket = await self.websocket_factory(
                        self.deepgram_url(),
                        {"Authorization": f"Token {self.api_key}"},
                    )
                    if delay:
                        self.reconnects += 1
                    await self._flush_reconnect_buffer()
                    return True
                except Exception as exc:
                    last_error = exc
                    self._record_error(
                        "connect_failed",
                        str(exc),
                        retryable=True,
                        details={"exception": exc.__class__.__name__},
                    )
            self._record_error(
                "connect_exhausted",
                str(last_error or "Deepgram connection failed."),
                retryable=False,
            )
            if raise_on_failure:
                raise ConnectionError("Deepgram STT connection failed.") from last_error
            return False

    async def _flush_reconnect_buffer(self) -> None:
        websocket = self._websocket
        if websocket is None:
            return
        while self._reconnect_buffer:
            frame = self._reconnect_buffer.popleft()
            self._reconnect_buffer_duration_ms = max(
                0, self._reconnect_buffer_duration_ms - (frame.duration_ms or 0)
            )
            await websocket.send(frame.data)

    def _buffer_frame(self, frame: AudioFrame) -> None:
        self._reconnect_buffer.append(frame)
        self._reconnect_buffer_duration_ms += frame.duration_ms or 0
        while self._reconnect_buffer_duration_ms > self.reconnect_buffer_ms and self._reconnect_buffer:
            removed = self._reconnect_buffer.popleft()
            self._reconnect_buffer_duration_ms = max(
                0, self._reconnect_buffer_duration_ms - (removed.duration_ms or 0)
            )

    async def _drop_connection(self) -> None:
        websocket = self._websocket
        self._websocket = None
        if websocket is not None:
            with suppress(Exception):
                await websocket.close()

    def _record_error(
        self,
        error_type: str,
        message: str,
        *,
        retryable: bool,
        details: dict[str, Any] | None = None,
    ) -> None:
        self.errors.append(
            ProviderError(
                call_id=self._call_id(),
                provider=self.provider_name,
                error_type=error_type,
                error_code=None,
                message=message,
                retryable=retryable,
                details=details or {},
            )
        )

    def _call_id(self) -> str:
        return self.call_id or "unknown"


async def _default_websocket_factory(url: str, headers: dict[str, str]) -> DeepgramWebSocket:
    import websockets

    return await websockets.connect(url, additional_headers=headers)


def _encoding_for_codec(codec: AudioCodec) -> str:
    if codec == "mulaw_8k":
        return "mulaw"
    if codec in {"pcm16_8k", "pcm16_16k"}:
        return "linear16"
    raise ValueError(f"Unsupported Deepgram codec: {codec}")


def _sample_rate_for_codec(codec: AudioCodec) -> int:
    if codec.endswith("_8k"):
        return 8000
    if codec.endswith("_16k"):
        return 16000
    raise ValueError(f"Unsupported Deepgram codec: {codec}")


def _first_alternative(payload: dict[str, Any]) -> dict[str, Any]:
    channel = payload.get("channel") if isinstance(payload.get("channel"), dict) else {}
    alternatives = channel.get("alternatives") if isinstance(channel.get("alternatives"), list) else []
    first = alternatives[0] if alternatives else {}
    return first if isinstance(first, dict) else {}


def _language_from_alternative(alternative: dict[str, Any], fallback: str | None) -> str | None:
    languages = alternative.get("languages")
    if isinstance(languages, list) and languages:
        return str(languages[0])
    words = alternative.get("words")
    if isinstance(words, list):
        for word in words:
            if isinstance(word, dict) and word.get("language"):
                return str(word["language"])
    return fallback


def _request_id(payload: dict[str, Any]) -> str | None:
    metadata = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}
    request_id = metadata.get("request_id")
    return str(request_id) if request_id else None


def _safe_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
