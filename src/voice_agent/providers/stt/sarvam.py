"""Sarvam streaming speech-to-text adapter."""

import asyncio
import base64
import json
from collections import deque
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import suppress
from typing import Any, Protocol
from urllib.parse import urlencode

from voice_agent.config import Settings, get_settings
from voice_agent.contracts.audio import AudioCodec, AudioFrame
from voice_agent.contracts.capabilities import STTCapabilities
from voice_agent.contracts.events import ProviderError, SpeechStart, SpeechStop, TranscriptEvent
from voice_agent.contracts.packets import now_ms
from voice_agent.providers.health import websocket_is_open, websocket_ping


class SarvamWebSocket(Protocol):
    async def send(self, data: bytes | str) -> None: ...
    async def recv(self) -> str | bytes: ...
    async def close(self) -> None: ...


WebSocketFactory = Callable[[str, dict[str, str]], Awaitable[SarvamWebSocket]]


class SarvamSTT:
    provider_name = "sarvam"
    capabilities = STTCapabilities(
        supports_interim=False,
        supports_final=True,
        supports_vad_events=True,
        supports_language_detection=True,
        supports_code_switching=True,
        accepted_codecs=("pcm16_8k", "pcm16_16k"),
    )

    def __init__(
        self,
        *,
        settings: Settings | None = None,
        api_key: str | None = None,
        websocket_factory: WebSocketFactory | None = None,
        target_codec: AudioCodec | None = None,
        queue_maxsize: int = 300,
        reconnect_backoffs_seconds: tuple[float, ...] = (0.2, 0.5, 1.0),
        reconnect_buffer_ms: int = 2000,
        health_timeout_seconds: float | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.api_key = api_key if api_key is not None else self.settings.sarvam_api_key
        self.websocket_factory = websocket_factory or _default_websocket_factory
        self.target_codec = target_codec or _codec_for_sample_rate(self.settings.sarvam_stt_sample_rate)
        self.reconnect_backoffs_seconds = reconnect_backoffs_seconds
        self.reconnect_buffer_ms = reconnect_buffer_ms
        self.health_timeout_seconds = (
            health_timeout_seconds
            if health_timeout_seconds is not None
            else self.settings.provider_health_timeout_ms / 1000
        )

        self.call_id: str | None = None
        self.language_hint: str | None = None
        self.started = False
        self.stopped = False
        self.reconnects = 0
        self.errors: list[ProviderError] = []
        self.last_metadata: dict[str, Any] | None = None

        self._websocket: SarvamWebSocket | None = None
        self._connect_lock = asyncio.Lock()
        self._receiver_task: asyncio.Task[None] | None = None
        self._transcripts: asyncio.Queue[TranscriptEvent | None] = asyncio.Queue(queue_maxsize)
        self._speech_events: asyncio.Queue[SpeechStart | SpeechStop | None] = asyncio.Queue(queue_maxsize)
        self._reconnect_buffer: deque[AudioFrame] = deque()
        self._reconnect_buffer_duration_ms = 0

    async def start(self, call_id: str, language_hint: str | None = None) -> None:
        if self.started:
            return
        if not self.api_key:
            raise ValueError("SARVAM_API_KEY is required for Sarvam STT.")
        if self.target_codec not in self.capabilities.accepted_codecs:
            raise ValueError(f"Sarvam STT does not accept codec: {self.target_codec}")
        self.call_id = call_id
        self.language_hint = _normalize_language_hint(
            language_hint or self.settings.sarvam_stt_language_code
        )
        await self._connect_with_retries(raise_on_failure=True)
        self.started = True
        self._receiver_task = asyncio.create_task(self._receiver_loop())

    async def send_audio(self, frame: AudioFrame) -> None:
        if self.stopped:
            return
        if frame.codec not in self.capabilities.accepted_codecs:
            raise ValueError(f"Sarvam STT does not accept codec: {frame.codec}")
        if frame.codec != self.target_codec:
            raise ValueError(
                f"Sarvam STT expected {self.target_codec}; AudioRouter should convert {frame.codec} first."
            )

        websocket = self._websocket
        if websocket is None:
            self._buffer_frame(frame)
            await self._connect_with_retries(raise_on_failure=False)
            return

        try:
            await websocket.send(json.dumps(self._audio_message(frame)))
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
        self.language_hint = _normalize_language_hint(language)

    async def health_check(self) -> bool:
        if not self.started or self.stopped:
            return False
        websocket = self._websocket
        if websocket is None:
            return await self._connect_with_retries(raise_on_failure=False)
        if not await websocket_ping(websocket, timeout_seconds=self.health_timeout_seconds):
            await self._drop_connection()
            return await self._connect_with_retries(raise_on_failure=False)
        return True

    async def stop(self) -> None:
        if self.stopped:
            return
        self.stopped = True
        websocket = self._websocket
        if websocket is not None:
            with suppress(Exception):
                await websocket.send(json.dumps({"type": "flush"}))
            with suppress(Exception):
                await websocket.close()
        self._websocket = None
        if self._receiver_task is not None and not self._receiver_task.done():
            self._receiver_task.cancel()
            with suppress(asyncio.CancelledError):
                await self._receiver_task
        await self._transcripts.put(None)
        await self._speech_events.put(None)

    def sarvam_url(self) -> str:
        params = {
            "language-code": self.language_hint or self.settings.sarvam_stt_language_code,
            "model": self.settings.sarvam_stt_model,
            "mode": self.settings.sarvam_stt_mode,
            "sample_rate": str(_sample_rate_for_codec(self.target_codec)),
            "input_audio_codec": "pcm_s16le",
            "vad_signals": _bool_param(self.settings.sarvam_stt_vad_signals),
            "flush_signal": "true",
        }
        if self.settings.sarvam_stt_high_vad_sensitivity is not None:
            params["high_vad_sensitivity"] = _bool_param(
                self.settings.sarvam_stt_high_vad_sensitivity
            )
        return f"{self.settings.sarvam_stt_ws_url}?{urlencode(params)}"

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

    async def _handle_message(self, message: str | bytes) -> None:
        if isinstance(message, bytes):
            return
        try:
            payload = json.loads(message)
        except json.JSONDecodeError as exc:
            self._record_error("invalid_json", str(exc), retryable=False)
            return

        message_type = str(payload.get("type") or "")
        data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
        if message_type == "data":
            await self._handle_transcription(data)
        elif message_type == "events":
            await self._handle_speech_event(data)
        elif message_type == "error":
            self._record_error(
                "sarvam_error",
                str(data.get("error") or data.get("message") or payload),
                retryable=False,
                error_code=_optional_str(data.get("code")),
                details=payload,
            )
        else:
            self.last_metadata = payload

    async def _handle_transcription(self, data: dict[str, Any]) -> None:
        transcript = str(data.get("transcript") or "").strip()
        if not transcript:
            return
        metrics = data.get("metrics") if isinstance(data.get("metrics"), dict) else {}
        duration_seconds = _safe_float(metrics.get("audio_duration"))
        end_ms = round(duration_seconds * 1000) if duration_seconds is not None else None
        confidence = _safe_float(data.get("language_probability"))
        await self._transcripts.put(
            TranscriptEvent(
                call_id=self._call_id(),
                text=transcript,
                is_final=True,
                confidence=confidence if confidence is not None else 0.0,
                language=_optional_str(data.get("language_code")) or self.language_hint,
                start_ms=None,
                end_ms=end_ms,
                provider=self.provider_name,
                asr_turn_id=_optional_str(data.get("request_id")),
            )
        )

    async def _handle_speech_event(self, data: dict[str, Any]) -> None:
        signal_type = str(data.get("signal_type") or "").upper()
        event_ts = now_ms()
        if signal_type == "START_SPEECH":
            await self._speech_events.put(
                SpeechStart(self._call_id(), event_ts, "stt", confidence=1.0)
            )
        elif signal_type == "END_SPEECH":
            await self._speech_events.put(
                SpeechStop(self._call_id(), event_ts, "stt", confidence=1.0)
            )

    async def _connect_with_retries(self, *, raise_on_failure: bool) -> bool:
        async with self._connect_lock:
            if websocket_is_open(self._websocket) or self.stopped:
                return websocket_is_open(self._websocket)
            delays = (0.0, *self.reconnect_backoffs_seconds)
            last_error: Exception | None = None
            for delay in delays:
                if delay:
                    await asyncio.sleep(delay)
                try:
                    self._websocket = await self.websocket_factory(
                        self.sarvam_url(),
                        {"Api-Subscription-Key": self.api_key or ""},
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
                str(last_error or "Sarvam STT connection failed."),
                retryable=False,
            )
            if raise_on_failure:
                raise ConnectionError("Sarvam STT connection failed.") from last_error
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
            await websocket.send(json.dumps(self._audio_message(frame)))

    def _audio_message(self, frame: AudioFrame) -> dict[str, Any]:
        return {
            "audio": {
                "data": base64.b64encode(frame.data).decode("ascii"),
                "sample_rate": str(_sample_rate_for_codec(frame.codec)),
                "encoding": "audio/wav",
            }
        }

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
        error_code: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        self.errors.append(
            ProviderError(
                call_id=self._call_id(),
                provider=self.provider_name,
                error_type=error_type,
                error_code=error_code,
                message=message,
                retryable=retryable,
                details=details or {},
            )
        )

    def _call_id(self) -> str:
        return self.call_id or "unknown"


async def _default_websocket_factory(url: str, headers: dict[str, str]) -> SarvamWebSocket:
    import websockets

    return await websockets.connect(url, additional_headers=headers)


def _sample_rate_for_codec(codec: AudioCodec) -> int:
    if codec.endswith("_8k"):
        return 8000
    if codec.endswith("_16k"):
        return 16000
    raise ValueError(f"Unsupported Sarvam codec: {codec}")


def _codec_for_sample_rate(sample_rate: int) -> AudioCodec:
    if sample_rate == 8000:
        return "pcm16_8k"
    if sample_rate == 16000:
        return "pcm16_16k"
    raise ValueError(f"Unsupported Sarvam STT sample rate: {sample_rate}")


def _normalize_language_hint(language: str | None) -> str:
    if not language or language.casefold() in {"multi", "auto", "detect"}:
        return "unknown"
    return language


def _bool_param(value: bool) -> str:
    return "true" if value else "false"


def _optional_str(value: Any) -> str | None:
    return str(value) if value is not None else None


def _safe_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
