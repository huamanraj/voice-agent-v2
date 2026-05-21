"""Cartesia streaming text-to-speech adapter."""

import asyncio
import base64
import json
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import suppress
from typing import Any, Protocol

from voice_agent.audio.converter import convert_audio_frame, duration_ms_for_bytes
from voice_agent.config import Settings, get_settings
from voice_agent.contracts.audio import AudioCodec, AudioFrame
from voice_agent.contracts.capabilities import TTSCapabilities
from voice_agent.contracts.events import ProviderError
from voice_agent.contracts.packets import now_ms
from voice_agent.providers.health import websocket_ping


class CartesiaWebSocket(Protocol):
    async def send(self, data: str | bytes) -> None: ...
    async def recv(self) -> str | bytes: ...
    async def close(self) -> None: ...


WebSocketFactory = Callable[[str, dict[str, str]], Awaitable[CartesiaWebSocket]]


class CartesiaTTS:
    provider_name = "cartesia"
    capabilities = TTSCapabilities(
        supports_streaming=True,
        supports_cancel=True,
        supports_word_timestamps=True,
        output_codecs=("mulaw_8k", "pcm16_8k"),
    )

    def __init__(
        self,
        *,
        settings: Settings | None = None,
        api_key: str | None = None,
        voice_id: str | None = None,
        websocket_factory: WebSocketFactory | None = None,
        first_audio_timeout_seconds: float | None = None,
        health_timeout_seconds: float | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.api_key = api_key if api_key is not None else self.settings.cartesia_api_key
        self.voice_id = voice_id if voice_id is not None else self.settings.cartesia_voice_id
        self.websocket_factory = websocket_factory or _default_websocket_factory
        self.first_audio_timeout_seconds = (
            first_audio_timeout_seconds
            if first_audio_timeout_seconds is not None
            else self.settings.tts_first_audio_timeout_ms / 1000
        )
        self.health_timeout_seconds = (
            health_timeout_seconds
            if health_timeout_seconds is not None
            else self.settings.provider_health_timeout_ms / 1000
        )

        self.call_id: str | None = None
        self.language: str | None = None
        self.started = False
        self.stopped = False
        self.errors: list[ProviderError] = []
        self.cancelled_message_ids: set[str] = set()
        self.context_ids_to_ignore: set[str] = set()
        self.word_timestamps_by_context: dict[str, dict[str, Any]] = {}

        self._websocket: CartesiaWebSocket | None = None
        self._send_lock = asyncio.Lock()
        self._message_contexts: dict[str, str] = {}
        self._context_messages: dict[str, str] = {}

    async def start(self, call_id: str, voice: str, language: str) -> None:
        if self.started:
            return
        if not self.api_key:
            raise ValueError("CARTESIA_API_KEY is required for Cartesia TTS.")
        self.voice_id = _resolve_voice_id(self.voice_id, voice)
        if not self.voice_id:
            raise ValueError("CARTESIA_VOICE_ID is required for Cartesia TTS.")
        _codec_for_output_format(self.settings.cartesia_output_encoding, self.settings.cartesia_sample_rate)

        self.call_id = call_id
        self.language = _normalize_language(language or self.settings.cartesia_language)
        self._websocket = await self.websocket_factory(
            self.settings.cartesia_ws_url,
            {
                "X-API-Key": self.api_key,
                "Cartesia-Version": self.settings.cartesia_version,
            },
        )
        self.started = True

    async def synthesize(
        self,
        text: str,
        message_id: str,
        sequence_id: int,
    ) -> AsyncIterator[AudioFrame]:
        if not self.started or self._websocket is None:
            raise RuntimeError("CartesiaTTS must be started before synthesize().")
        if self.stopped or message_id in self.cancelled_message_ids:
            return

        context_id = self._context_id_for_message(message_id)
        payload = self._generation_payload(text=text, context_id=context_id)
        async with self._send_lock:
            await self._websocket.send(json.dumps(payload))

        first_chunk_received = False
        chunk_index = 0
        while not self.stopped:
            response = await self._receive_payload(
                timeout_seconds=None if first_chunk_received else self.first_audio_timeout_seconds
            )
            response_context_id = str(response.get("context_id") or "")
            if response_context_id and response_context_id != context_id:
                continue

            response_type = str(response.get("type") or "")
            if response_type == "error":
                message = str(response.get("message") or response.get("title") or response)
                self._record_error(
                    "cartesia_error",
                    message,
                    retryable=False,
                    error_code=_optional_str(response.get("error_code")),
                    details=response,
                )
                raise RuntimeError(f"Cartesia TTS error: {message}")

            if response_type == "timestamps":
                timestamps = response.get("word_timestamps")
                if isinstance(timestamps, dict):
                    self.word_timestamps_by_context[context_id] = timestamps
                if response.get("done"):
                    break
                continue

            if response_type == "flush_done":
                continue

            if response_type == "chunk":
                audio_data = _decode_audio(response.get("data"))
                if audio_data and context_id not in self.context_ids_to_ignore:
                    first_chunk_received = True
                    yield self._audio_frame(
                        audio_data=audio_data,
                        message_id=message_id,
                        sequence_id=sequence_id,
                        context_id=context_id,
                        chunk_index=chunk_index,
                        is_final=bool(response.get("done")),
                        step_time=response.get("step_time"),
                    )
                    chunk_index += 1
                if response.get("done"):
                    break
                continue

            if response.get("done"):
                break

        self._message_contexts.pop(message_id, None)
        self._context_messages.pop(context_id, None)

    async def cancel(self, message_id: str, reason: str) -> None:
        self.cancelled_message_ids.add(message_id)
        context_id = self._message_contexts.get(message_id)
        if context_id is None:
            return
        self.context_ids_to_ignore.add(context_id)
        websocket = self._websocket
        if websocket is None:
            return
        try:
            async with self._send_lock:
                await websocket.send(json.dumps({"context_id": context_id, "cancel": True}))
        except Exception as exc:
            self._record_error(
                "cancel_failed",
                str(exc),
                retryable=True,
                details={"message_id": message_id, "reason": reason, "exception": exc.__class__.__name__},
            )

    async def health_check(self) -> bool:
        if not self.started or self.stopped:
            return False
        websocket = self._websocket
        if websocket is None:
            return False
        return await websocket_ping(websocket, timeout_seconds=self.health_timeout_seconds)

    async def stop(self) -> None:
        if self.stopped:
            return
        self.stopped = True
        websocket = self._websocket
        self._websocket = None
        if websocket is not None:
            with suppress(Exception):
                await websocket.close()

    def _generation_payload(self, *, text: str, context_id: str) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model_id": self.settings.cartesia_model,
            "transcript": text,
            "voice": {"mode": "id", "id": self.voice_id},
            "output_format": {
                "container": "raw",
                "encoding": self.settings.cartesia_output_encoding,
                "sample_rate": self.settings.cartesia_sample_rate,
            },
            "language": self.language or _normalize_language(self.settings.cartesia_language),
            "context_id": context_id,
            "continue": False,
            "max_buffer_delay_ms": self.settings.cartesia_max_buffer_delay_ms,
            "add_timestamps": self.settings.cartesia_add_timestamps,
        }
        return payload

    async def _receive_payload(self, *, timeout_seconds: float | None) -> dict[str, Any]:
        websocket = self._websocket
        if websocket is None:
            raise RuntimeError("Cartesia WebSocket is not connected.")
        try:
            message = (
                await websocket.recv()
                if timeout_seconds is None
                else await asyncio.wait_for(websocket.recv(), timeout=timeout_seconds)
            )
        except asyncio.TimeoutError as exc:
            self._record_error("first_audio_timeout", "Cartesia did not return first audio in time.", retryable=True)
            raise TimeoutError("Cartesia did not return first audio in time.") from exc
        except Exception as exc:
            self._record_error(
                "receive_failed",
                str(exc),
                retryable=True,
                details={"exception": exc.__class__.__name__},
            )
            raise
        if isinstance(message, bytes):
            self._record_error("unexpected_binary", "Cartesia returned binary data; expected JSON text.", retryable=False)
            return {}
        try:
            payload = json.loads(message)
        except json.JSONDecodeError as exc:
            self._record_error("invalid_json", str(exc), retryable=False)
            return {}
        return payload if isinstance(payload, dict) else {}

    def _audio_frame(
        self,
        *,
        audio_data: bytes,
        message_id: str,
        sequence_id: int,
        context_id: str,
        chunk_index: int,
        is_final: bool,
        step_time: Any,
    ) -> AudioFrame:
        codec = _codec_for_output_format(self.settings.cartesia_output_encoding, self.settings.cartesia_sample_rate)
        frame = AudioFrame(
            call_id=self.call_id or "unknown",
            data=audio_data,
            timestamp_ms=now_ms(),
            sample_rate=self.settings.cartesia_sample_rate,
            codec=codec,
            channels=1,
            sequence_id=sequence_id,
            duration_ms=duration_ms_for_bytes(audio_data, codec),
            meta={
                "provider": self.provider_name,
                "message_id": message_id,
                "context_id": context_id,
                "chunk_index": chunk_index,
                "is_final": is_final,
                "step_time": step_time,
                "word_timestamps": self.word_timestamps_by_context.get(context_id),
            },
        )
        if frame.codec != "mulaw_8k":
            frame = convert_audio_frame(frame, "mulaw_8k")
        return frame

    def _context_id_for_message(self, message_id: str) -> str:
        context_id = self._message_contexts.get(message_id)
        if context_id is None:
            context_id = message_id
            self._message_contexts[message_id] = context_id
            self._context_messages[context_id] = message_id
        return context_id

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
                call_id=self.call_id or "unknown",
                provider=self.provider_name,
                error_type=error_type,
                error_code=error_code,
                message=message,
                retryable=retryable,
                details=details or {},
            )
        )


async def _default_websocket_factory(url: str, headers: dict[str, str]) -> CartesiaWebSocket:
    import websockets

    return await websockets.connect(url, additional_headers=headers)


def _resolve_voice_id(configured_voice_id: str | None, start_voice: str) -> str | None:
    if configured_voice_id:
        return configured_voice_id
    if start_voice and start_voice != "mock-voice":
        return start_voice
    return None


def _normalize_language(language: str | None) -> str:
    if not language:
        return "en"
    return language.split("-")[0].lower()


def _codec_for_output_format(encoding: str, sample_rate: int) -> AudioCodec:
    if encoding == "pcm_mulaw" and sample_rate == 8000:
        return "mulaw_8k"
    if encoding == "pcm_s16le" and sample_rate == 8000:
        return "pcm16_8k"
    if encoding == "pcm_s16le" and sample_rate == 16000:
        return "pcm16_16k"
    raise ValueError(f"Unsupported Cartesia output format: {encoding}@{sample_rate}")


def _decode_audio(data: Any) -> bytes:
    if not isinstance(data, str) or not data:
        return b""
    return base64.b64decode(data)


def _optional_str(value: Any) -> str | None:
    return str(value) if value is not None else None
