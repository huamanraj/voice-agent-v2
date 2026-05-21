"""Sarvam streaming text-to-speech adapter."""

import asyncio
import base64
import json
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import suppress
from typing import Any, Protocol
from urllib.parse import urlencode

from voice_agent.audio.converter import convert_audio_frame, duration_ms_for_bytes
from voice_agent.config import Settings, get_settings
from voice_agent.contracts.audio import AudioCodec, AudioFrame
from voice_agent.contracts.capabilities import TTSCapabilities
from voice_agent.contracts.events import ProviderError
from voice_agent.contracts.packets import now_ms
from voice_agent.providers.health import websocket_is_open


class SarvamWebSocket(Protocol):
    async def send(self, data: str | bytes) -> None: ...
    async def recv(self) -> str | bytes: ...
    async def close(self) -> None: ...


WebSocketFactory = Callable[[str, dict[str, str]], Awaitable[SarvamWebSocket]]

# Sarvam rejects min_buffer_size below 30 with "Input parameters has to be a valid dictionary".
_SARVAM_TTS_MIN_BUFFER_SIZE_FLOOR = 30
_SARVAM_TTS_MIN_BUFFER_SIZE_DEFAULT = 50


class SarvamTTS:
    provider_name = "sarvam"
    capabilities = TTSCapabilities(
        supports_streaming=True,
        supports_cancel=False,
        supports_word_timestamps=False,
        output_codecs=("mulaw_8k", "pcm16_8k", "pcm16_16k"),
    )

    def __init__(
        self,
        *,
        settings: Settings | None = None,
        api_key: str | None = None,
        websocket_factory: WebSocketFactory | None = None,
        first_audio_timeout_seconds: float | None = None,
        keepalive_seconds: float | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.api_key = api_key if api_key is not None else self.settings.sarvam_api_key
        self.websocket_factory = websocket_factory or _default_websocket_factory
        self.first_audio_timeout_seconds = (
            first_audio_timeout_seconds
            if first_audio_timeout_seconds is not None
            else self.settings.tts_first_audio_timeout_ms / 1000
        )
        self.keepalive_seconds = (
            keepalive_seconds
            if keepalive_seconds is not None
            else float(self.settings.sarvam_tts_keepalive_seconds)
        )

        self.call_id: str | None = None
        self.voice: str | None = None
        self.language: str | None = None
        self.started = False
        self.stopped = False
        self.errors: list[ProviderError] = []
        self.cancelled_message_ids: set[str] = set()

        self._websocket: SarvamWebSocket | None = None
        self._send_lock = asyncio.Lock()
        self._connect_lock = asyncio.Lock()
        self._keepalive_task: asyncio.Task[None] | None = None
        self._output_audio_codec = _normalize_output_audio_codec(
            self.settings.sarvam_tts_output_audio_codec
        )

    async def start(self, call_id: str, voice: str, language: str) -> None:
        if self.started:
            return
        if not self.api_key:
            raise ValueError("SARVAM_API_KEY is required for Sarvam TTS.")
        self.call_id = call_id
        self.voice = _resolve_speaker(self.settings.sarvam_tts_speaker, voice)
        self.language = language or self.settings.sarvam_tts_target_language_code
        if not self.voice:
            raise ValueError("Sarvam TTS speaker is required.")
        self._output_audio_codec = _normalize_output_audio_codec(
            self.settings.sarvam_tts_output_audio_codec
        )
        _codec_for_config(
            self._output_audio_codec,
            self.settings.sarvam_tts_speech_sample_rate,
        )
        await self._connect()
        self.started = True
        self._keepalive_task = asyncio.create_task(self._keepalive_loop())

    async def synthesize(
        self,
        text: str,
        message_id: str,
        sequence_id: int,
    ) -> AsyncIterator[AudioFrame]:
        if not self.started:
            raise RuntimeError("SarvamTTS must be started before synthesize().")
        if self.stopped or message_id in self.cancelled_message_ids:
            return
        try:
            retried_with_linear16 = False
            while True:
                try:
                    async for frame in self._synthesize_once(text, message_id, sequence_id):
                        yield frame
                    break
                except _SarvamRetryableConfigError as exc:
                    if retried_with_linear16:
                        raise RuntimeError(str(exc)) from exc
                    retried_with_linear16 = True
                    await self._fallback_to_linear16(str(exc))
        finally:
            self.cancelled_message_ids.discard(message_id)

    async def cancel(self, message_id: str, reason: str) -> None:
        self.cancelled_message_ids.add(message_id)
        websocket = self._websocket
        if websocket is None:
            return
        try:
            async with self._send_lock:
                await websocket.send(json.dumps({"type": "flush"}))
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
        try:
            await self._ensure_connected()
            websocket = self._websocket
            if websocket is None:
                return False
            async with self._send_lock:
                await websocket.send(json.dumps({"type": "ping"}))
            return True
        except Exception as exc:
            self._record_error(
                "health_check_failed",
                str(exc),
                retryable=True,
                details={"exception": exc.__class__.__name__},
            )
            await self._drop_connection()
            return False

    async def stop(self) -> None:
        if self.stopped:
            return
        self.stopped = True
        if self._keepalive_task is not None and not self._keepalive_task.done():
            self._keepalive_task.cancel()
            with suppress(asyncio.CancelledError):
                await self._keepalive_task
        websocket = self._websocket
        self._websocket = None
        if websocket is not None:
            with suppress(Exception):
                await websocket.close()

    def sarvam_url(self) -> str:
        params = {
            "model": self.settings.sarvam_tts_model,
            "send_completion_event": _bool_query(self.settings.sarvam_tts_send_completion_event),
        }
        return f"{self.settings.sarvam_tts_ws_url}?{urlencode(params)}"

    async def _connect(self) -> None:
        async with self._connect_lock:
            if websocket_is_open(self._websocket):
                return
            websocket = await self.websocket_factory(
                self.sarvam_url(),
                {"Api-Subscription-Key": self.api_key or ""},
            )
            await websocket.send(json.dumps(self._config_payload()))
            self._websocket = websocket

    async def _ensure_connected(self) -> None:
        if websocket_is_open(self._websocket):
            return
        await self._drop_connection()
        await self._connect()

    async def _keepalive_loop(self) -> None:
        while not self.stopped:
            await asyncio.sleep(self.keepalive_seconds)
            websocket = self._websocket
            if websocket is None:
                continue
            try:
                async with self._send_lock:
                    await websocket.send(json.dumps({"type": "ping"}))
            except Exception as exc:
                self._record_error(
                    "keepalive_failed",
                    str(exc),
                    retryable=True,
                    details={"exception": exc.__class__.__name__},
                )
                await self._drop_connection()

    async def _receive_payload(self, *, timeout_seconds: float | None) -> dict[str, Any]:
        await self._ensure_connected()
        websocket = self._websocket
        if websocket is None:
            raise RuntimeError("Sarvam TTS WebSocket is not connected.")
        try:
            message = (
                await websocket.recv()
                if timeout_seconds is None
                else await asyncio.wait_for(websocket.recv(), timeout=timeout_seconds)
            )
        except asyncio.TimeoutError as exc:
            self._record_error("first_audio_timeout", "Sarvam did not return first audio in time.", retryable=True)
            raise TimeoutError("Sarvam did not return first audio in time.") from exc
        except Exception as exc:
            self._record_error(
                "receive_failed",
                str(exc),
                retryable=True,
                details={"exception": exc.__class__.__name__},
            )
            await self._drop_connection()
            raise

        if isinstance(message, bytes):
            self._record_error("unexpected_binary", "Sarvam returned binary data; expected JSON text.", retryable=False)
            return {}
        try:
            payload = json.loads(message)
        except json.JSONDecodeError as exc:
            self._record_error("invalid_json", str(exc), retryable=False)
            return {}
        return payload if isinstance(payload, dict) else {}

    async def _synthesize_once(
        self,
        text: str,
        message_id: str,
        sequence_id: int,
    ) -> AsyncIterator[AudioFrame]:
        await self._ensure_connected()
        websocket = self._websocket
        if websocket is None:
            raise RuntimeError("Sarvam TTS WebSocket is not connected.")

        async with self._send_lock:
            await websocket.send(json.dumps({"type": "text", "data": {"text": text}}))
            await websocket.send(json.dumps({"type": "flush"}))

        first_chunk_received = False
        chunk_index = 0
        request_id: str | None = None
        while not self.stopped:
            response = await self._receive_payload(
                timeout_seconds=None if first_chunk_received else self.first_audio_timeout_seconds
            )
            response_type = str(response.get("type") or "")
            data = response.get("data") if isinstance(response.get("data"), dict) else {}

            if response_type == "error":
                message = str(data.get("message") or response)
                if self._should_retry_with_linear16(message, response, first_chunk_received):
                    raise _SarvamRetryableConfigError(
                        f"Sarvam rejected codec {self._output_audio_codec}: {message}"
                    )
                self._record_error(
                    "sarvam_tts_error",
                    message,
                    retryable=False,
                    error_code=_optional_str(data.get("code")),
                    details=response,
                )
                raise RuntimeError(f"Sarvam TTS error: {message}")

            if response_type == "audio":
                audio_data = _decode_audio(data.get("audio"))
                request_id = request_id or _optional_str(data.get("request_id"))
                if audio_data and message_id not in self.cancelled_message_ids:
                    first_chunk_received = True
                    yield self._audio_frame(
                        audio_data=audio_data,
                        message_id=message_id,
                        sequence_id=sequence_id,
                        chunk_index=chunk_index,
                        request_id=request_id,
                        content_type=_optional_str(data.get("content_type")),
                    )
                    chunk_index += 1
                continue

            if response_type == "event":
                if str(data.get("event_type") or "") == "final":
                    break
                continue

    async def _fallback_to_linear16(self, reason: str) -> None:
        if self._output_audio_codec == "linear16":
            raise RuntimeError(reason)
        self._record_error(
            "codec_fallback",
            reason,
            retryable=True,
            details={"fallback_codec": "linear16"},
        )
        self._output_audio_codec = "linear16"
        await self._drop_connection()
        await self._connect()

    def _config_payload(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "model": self.settings.sarvam_tts_model,
            "target_language_code": _normalize_language(self.language, self.settings),
            "speaker": self.voice,
            "pace": self.settings.sarvam_tts_pace,
            "speech_sample_rate": str(self.settings.sarvam_tts_speech_sample_rate),
            "enable_preprocessing": self.settings.sarvam_tts_enable_preprocessing,
            "output_audio_codec": self._output_audio_codec,
            "output_audio_bitrate": _output_audio_bitrate(self.settings.sarvam_tts_output_audio_bitrate),
            "min_buffer_size": _normalize_min_buffer_size(self.settings.sarvam_tts_min_buffer_size),
            "max_chunk_length": self.settings.sarvam_tts_max_chunk_length,
        }
        if _uses_temperature(self.settings.sarvam_tts_model):
            data["temperature"] = self.settings.sarvam_tts_temperature
        return {"type": "config", "data": data}

    def _should_retry_with_linear16(
        self,
        message: str,
        response: dict[str, Any],
        first_chunk_received: bool,
    ) -> bool:
        if first_chunk_received or self._output_audio_codec == "linear16":
            return False
        error_text = f"{message} {json.dumps(response, ensure_ascii=True, sort_keys=True)}".casefold()
        return any(
            token in error_text
            for token in (
                "codec",
                "format",
                "input parameters",
                "sample_rate",
                "audio",
                "configuration",
                "mulaw",
                "unsupported",
                "invalid",
            )
        )

    def _audio_frame(
        self,
        *,
        audio_data: bytes,
        message_id: str,
        sequence_id: int,
        chunk_index: int,
        request_id: str | None,
        content_type: str | None,
    ) -> AudioFrame:
        codec = _codec_for_config(
            self._output_audio_codec,
            self.settings.sarvam_tts_speech_sample_rate,
        )
        frame = AudioFrame(
            call_id=self.call_id or "unknown",
            data=audio_data,
            timestamp_ms=now_ms(),
            sample_rate=self.settings.sarvam_tts_speech_sample_rate,
            codec=codec,
            channels=1,
            sequence_id=sequence_id,
            duration_ms=duration_ms_for_bytes(audio_data, codec),
            meta={
                "provider": self.provider_name,
                "message_id": message_id,
                "request_id": request_id,
                "content_type": content_type,
                "chunk_index": chunk_index,
            },
        )
        if frame.codec != "mulaw_8k":
            frame = convert_audio_frame(frame, "mulaw_8k")
        return frame

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
                call_id=self.call_id or "unknown",
                provider=self.provider_name,
                error_type=error_type,
                error_code=error_code,
                message=message,
                retryable=retryable,
                details=details or {},
            )
        )


async def _default_websocket_factory(url: str, headers: dict[str, str]) -> SarvamWebSocket:
    import websockets

    return await websockets.connect(url, additional_headers=headers)


def _resolve_speaker(configured_speaker: str | None, start_voice: str) -> str | None:
    speaker = start_voice if start_voice and start_voice != "mock-voice" else configured_speaker
    if speaker is None:
        return None
    normalized = speaker.strip().casefold()
    return normalized or None


def _normalize_language(language: str | None, settings: Settings) -> str:
    if language:
        return language
    return settings.sarvam_tts_target_language_code


def _normalize_output_audio_codec(output_audio_codec: str) -> str:
    normalized = output_audio_codec.strip().casefold()
    if normalized == "pcm":
        return "linear16"
    return normalized


def _codec_for_config(output_audio_codec: str, speech_sample_rate: int) -> AudioCodec:
    normalized = output_audio_codec.strip().casefold()
    if normalized == "mulaw" and speech_sample_rate == 8000:
        return "mulaw_8k"
    if normalized == "linear16" and speech_sample_rate == 8000:
        return "pcm16_8k"
    if normalized == "linear16" and speech_sample_rate == 16000:
        return "pcm16_16k"
    raise ValueError(f"Unsupported Sarvam output format: {output_audio_codec}@{speech_sample_rate}")


def _decode_audio(data: Any) -> bytes:
    if not isinstance(data, str) or not data:
        return b""
    return base64.b64decode(data)


def _bool_query(value: bool) -> str:
    return "true" if value else "false"


def _optional_str(value: Any) -> str | None:
    return str(value) if value is not None else None


def _uses_temperature(model: str) -> bool:
    return model.strip().casefold() == "bulbul:v3"


def _output_audio_bitrate(configured_bitrate: str | None) -> str:
    bitrate = (configured_bitrate or "128k").strip()
    return bitrate or "128k"


def _normalize_min_buffer_size(configured_size: int) -> int:
    if configured_size < _SARVAM_TTS_MIN_BUFFER_SIZE_FLOOR:
        return _SARVAM_TTS_MIN_BUFFER_SIZE_DEFAULT
    return configured_size


class _SarvamRetryableConfigError(RuntimeError):
    """Raised when the first synth request should be retried with a safer codec."""
