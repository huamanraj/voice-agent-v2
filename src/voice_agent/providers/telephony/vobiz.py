"""Vobiz Streaming WebSocket telephony adapter."""

import asyncio
import base64
import json
from collections.abc import AsyncIterator
from contextlib import suppress
from typing import Any, Protocol

from voice_agent.audio.chunker import chunk_audio_frame
from voice_agent.audio.converter import convert_audio_frame, duration_ms_for_bytes
from voice_agent.contracts.audio import AudioCodec, AudioFrame
from voice_agent.contracts.capabilities import TelephonyCapabilities
from voice_agent.contracts.events import PlaybackEvent, ProviderError
from voice_agent.contracts.packets import now_ms


class VobizWebSocket(Protocol):
    async def receive_text(self) -> str: ...
    async def send_text(self, data: str) -> None: ...
    async def close(self) -> None: ...


class VobizTelephony:
    provider_name = "vobiz"
    capabilities = TelephonyCapabilities(
        supports_clear_playback=True,
        supports_playback_checkpoint=True,
        supports_bidirectional_audio=True,
        inbound_codec="mulaw_8k",
        outbound_codec="mulaw_8k",
    )

    def __init__(
        self,
        websocket: VobizWebSocket,
        *,
        call_id: str | None = None,
        auth_token: str | None = None,
        clear_timeout_seconds: float = 0.5,
        queue_maxsize: int = 200,
    ) -> None:
        self.websocket = websocket
        self.call_id = call_id or "unknown"
        self.stream_id: str | None = None
        self.auth_token = auth_token
        self.clear_timeout_seconds = clear_timeout_seconds
        self.started = False
        self.stopped = False
        self.stop_reason: str | None = None
        self.errors: list[ProviderError] = []

        self._incoming_audio: asyncio.Queue[AudioFrame | None] = asyncio.Queue(queue_maxsize)
        self._playback_events: asyncio.Queue[PlaybackEvent | None] = asyncio.Queue(queue_maxsize)
        self._clear_ack_event = asyncio.Event()
        self._receiver_task: asyncio.Task[None] | None = None
        self._finished = False
        self._local_media_sequence = 0
        self._media_codec: AudioCodec = "mulaw_8k"
        self._media_sample_rate = 8000
        self._media_content_type = "audio/x-mulaw"

    async def start(self) -> None:
        if self.started:
            return
        self.started = True
        self._receiver_task = asyncio.create_task(self._receiver_loop())

    async def receive_audio(self) -> AsyncIterator[AudioFrame]:
        while True:
            frame = await self._incoming_audio.get()
            if frame is None:
                break
            yield frame

    async def send_audio(self, frame: AudioFrame) -> None:
        outbound = convert_audio_frame(frame, self._media_codec)
        content_type = _content_type_for_codec(outbound.codec)
        for chunk in chunk_audio_frame(outbound, chunk_ms=20, pad_final=False):
            payload = base64.b64encode(_wire_audio_bytes(chunk.data, outbound.codec)).decode("ascii")
            await self._send_json(
                {
                    "event": "playAudio",
                    "media": {
                        "contentType": content_type,
                        "sampleRate": outbound.sample_rate,
                        "payload": payload,
                    },
                }
            )

    async def clear_playback(self, reason: str) -> None:
        if self.stream_id is None:
            self._record_error(
                "missing_stream_id",
                "Cannot send clearAudio before Vobiz start provides streamId.",
                retryable=True,
            )
            return
        self._clear_ack_event.clear()
        await self._send_json({"event": "clearAudio", "streamId": self.stream_id})
        with suppress(asyncio.TimeoutError):
            await asyncio.wait_for(self._clear_ack_event.wait(), self.clear_timeout_seconds)

    async def send_checkpoint(self, checkpoint_id: str) -> None:
        if self.stream_id is None:
            self._record_error(
                "missing_stream_id",
                "Cannot send checkpoint before Vobiz start provides streamId.",
                retryable=True,
            )
            return
        await self._send_json(
            {"event": "checkpoint", "streamId": self.stream_id, "name": checkpoint_id}
        )

    async def playback_events(self) -> AsyncIterator[PlaybackEvent]:
        while True:
            event = await self._playback_events.get()
            if event is None:
                break
            yield event

    async def stop(self, reason: str) -> None:
        self.stop_reason = reason
        if not self.stopped and self.stream_id is not None:
            with suppress(Exception):
                await self._send_json({"event": "stop", "streamId": self.stream_id})
        await self._finish_stream(reason)
        if self._receiver_task and self._receiver_task is not asyncio.current_task():
            self._receiver_task.cancel()
            with suppress(asyncio.CancelledError):
                await self._receiver_task
        with suppress(Exception):
            await self.websocket.close()

    async def _receiver_loop(self) -> None:
        try:
            while not self._finished:
                try:
                    message = await self._receive_text()
                except asyncio.CancelledError:
                    raise
                except Exception as exc:
                    self._record_error(
                        "websocket_closed",
                        str(exc),
                        retryable=False,
                        details={"exception": exc.__class__.__name__},
                    )
                    break

                try:
                    packet = json.loads(message)
                except json.JSONDecodeError as exc:
                    self._record_error(
                        "invalid_json",
                        str(exc),
                        retryable=False,
                        details={"message_length": len(message)},
                    )
                    continue
                if not isinstance(packet, dict):
                    self._record_error(
                        "invalid_json",
                        "Vobiz WebSocket message must be a JSON object.",
                        retryable=False,
                        details={"message_type": type(packet).__name__},
                    )
                    continue

                try:
                    await self._handle_packet(packet)
                except Exception as exc:
                    self._record_error(
                        "event_failed",
                        str(exc),
                        retryable=False,
                        details={
                            "event": packet.get("event"),
                            "exception": exc.__class__.__name__,
                        },
                    )
        finally:
            await self._finish_stream("websocket_closed")

    async def _handle_packet(self, packet: dict[str, Any]) -> None:
        event_name = str(packet.get("event", ""))
        if event_name == "start":
            await self._handle_start(packet)
        elif event_name == "media":
            await self._handle_media(packet)
        elif event_name == "playedStream":
            await self._handle_played_stream(packet)
        elif event_name == "clearedAudio":
            await self._handle_cleared_audio(packet)
        elif event_name == "stop":
            await self._finish_stream("remote_stop")
        else:
            self._record_error(
                "unknown_event",
                f"Unsupported Vobiz event: {event_name or '<missing>'}",
                retryable=False,
                details={"event": event_name},
            )

    async def _handle_start(self, packet: dict[str, Any]) -> None:
        start = packet.get("start") if isinstance(packet.get("start"), dict) else {}
        if self.auth_token is not None and not self._has_valid_token(packet, start):
            self._record_error("auth_failed", "Vobiz start token did not match.", retryable=False)
            await self._finish_stream("auth_failed")
            return

        call_id = start.get("callId") or packet.get("callId")
        stream_id = start.get("streamId") or packet.get("streamId")
        if not call_id or not stream_id:
            self._record_error(
                "invalid_start",
                "Vobiz start event missing callId or streamId.",
                retryable=False,
                details={"has_call_id": bool(call_id), "has_stream_id": bool(stream_id)},
            )
            await self._finish_stream("invalid_start")
            return

        self.call_id = str(call_id)
        self.stream_id = str(stream_id)
        media_format = start.get("mediaFormat") if isinstance(start.get("mediaFormat"), dict) else {}
        try:
            codec, sample_rate, content_type = _codec_from_media_format(media_format)
        except ValueError as exc:
            self._record_error("invalid_start_media_format", str(exc), retryable=False)
            await self._finish_stream("invalid_start_media_format")
            return
        self._media_codec = codec
        self._media_sample_rate = sample_rate
        self._media_content_type = content_type

    async def _handle_media(self, packet: dict[str, Any]) -> None:
        media = packet.get("media") if isinstance(packet.get("media"), dict) else {}
        track = str(media.get("track", "inbound"))
        if track != "inbound":
            return

        payload = media.get("payload")
        if not isinstance(payload, str):
            self._record_error("invalid_media", "Vobiz media event missing payload.", retryable=False)
            return

        try:
            data = base64.b64decode(payload, validate=True)
        except ValueError as exc:
            self._record_error(
                "invalid_media_payload",
                str(exc),
                retryable=False,
                details={"payload_length": len(payload)},
            )
            return

        sequence_id = _safe_int(media.get("chunk"), self._local_media_sequence)
        timestamp_ms = _safe_int(media.get("timestamp"), now_ms())
        self._local_media_sequence = sequence_id + 1

        try:
            codec, sample_rate, content_type = _codec_from_media_format(
                {
                    "encoding": media.get("contentType") or self._media_content_type,
                    "sampleRate": media.get("sampleRate") or self._media_sample_rate,
                }
            )
            data = _internal_audio_bytes(data, codec)
        except ValueError as exc:
            self._record_error("invalid_media_format", str(exc), retryable=False)
            return
        await self._incoming_audio.put(
            AudioFrame(
                call_id=self.call_id,
                data=data,
                timestamp_ms=timestamp_ms,
                sample_rate=sample_rate,
                codec=codec,
                channels=1,
                sequence_id=sequence_id,
                duration_ms=duration_ms_for_bytes(data, codec, 1),
                meta={
                    "provider": self.provider_name,
                    "stream_id": self.stream_id,
                    "track": track,
                    "sequence_number": packet.get("sequenceNumber"),
                    "content_type": content_type,
                },
            )
        )

    async def _handle_played_stream(self, packet: dict[str, Any]) -> None:
        checkpoint_id = str(packet.get("name") or packet.get("checkpoint") or "")
        await self._playback_events.put(
            PlaybackEvent(
                call_id=self.call_id,
                message_id=checkpoint_id or "vobiz-checkpoint",
                sequence_id=_safe_int(packet.get("sequenceNumber"), 0),
                checkpoint_id=checkpoint_id or None,
                event_type="checkpoint_played",
                ts_ms=now_ms(),
            )
        )

    async def _handle_cleared_audio(self, packet: dict[str, Any]) -> None:
        self._clear_ack_event.set()
        await self._playback_events.put(
            PlaybackEvent(
                call_id=self.call_id,
                message_id="vobiz-clear",
                sequence_id=_safe_int(packet.get("sequenceNumber"), 0),
                checkpoint_id=None,
                event_type="cleared",
                ts_ms=now_ms(),
            )
        )

    async def _send_json(self, payload: dict[str, Any]) -> None:
        try:
            await self._send_text(json.dumps(payload, separators=(",", ":")))
        except Exception as exc:
            self._record_error(
                "send_failed",
                str(exc),
                retryable=True,
                details={"event": payload.get("event"), "exception": exc.__class__.__name__},
            )
            raise

    async def _receive_text(self) -> str:
        receive_text = getattr(self.websocket, "receive_text", None)
        if receive_text is not None:
            return await receive_text()
        recv = getattr(self.websocket, "recv", None)
        if recv is None:
            raise RuntimeError("Vobiz websocket must provide receive_text() or recv().")
        return await recv()

    async def _send_text(self, data: str) -> None:
        send_text = getattr(self.websocket, "send_text", None)
        if send_text is not None:
            await send_text(data)
            return
        send = getattr(self.websocket, "send", None)
        if send is None:
            raise RuntimeError("Vobiz websocket must provide send_text() or send().")
        await send(data)

    async def _finish_stream(self, reason: str) -> None:
        if self._finished:
            return
        self._finished = True
        self.stopped = True
        self.stop_reason = self.stop_reason or reason
        self._clear_ack_event.set()
        _put_terminal(self._incoming_audio)
        _put_terminal(self._playback_events)

    def _has_valid_token(self, packet: dict[str, Any], start: dict[str, Any]) -> bool:
        candidates = [packet.get("token"), start.get("token")]
        extra_headers = packet.get("extra_headers")
        if isinstance(extra_headers, str):
            with suppress(json.JSONDecodeError):
                parsed_headers = json.loads(extra_headers)
                if isinstance(parsed_headers, dict):
                    candidates.extend([parsed_headers.get("token"), parsed_headers.get("x-vobiz-token")])
        return self.auth_token in candidates

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
                call_id=self.call_id,
                provider=self.provider_name,
                error_type=error_type,
                error_code=None,
                message=message,
                retryable=retryable,
                details=details or {},
            )
        )


def _codec_from_media_format(media_format: dict[str, Any]) -> tuple[AudioCodec, int, str]:
    content_type = str(
        media_format.get("encoding")
        or media_format.get("contentType")
        or media_format.get("content_type")
        or "audio/x-mulaw"
    ).lower()
    sample_rate = _sample_rate_from_content_type(content_type) or _safe_int(
        media_format.get("sampleRate") or media_format.get("sample_rate"),
        8000,
    )
    base_content_type = content_type.split(";", 1)[0].strip()

    if base_content_type in {"audio/x-mulaw", "audio/pcmu", "mulaw", "pcmu"}:
        return "mulaw_8k", 8000, "audio/x-mulaw"
    if base_content_type in {"audio/x-l16", "audio/l16", "l16", "pcm16", "audio/pcm"}:
        if sample_rate == 16000:
            return "pcm16_16k", 16000, "audio/x-l16"
        return "pcm16_8k", 8000, "audio/x-l16"

    raise ValueError(f"Unsupported Vobiz media format: {content_type}")


def _content_type_for_codec(codec: AudioCodec) -> str:
    if codec == "mulaw_8k":
        return "audio/x-mulaw"
    if codec in {"pcm16_8k", "pcm16_16k"}:
        return "audio/x-l16"
    raise ValueError(f"Unsupported Vobiz outbound codec: {codec}")


def _sample_rate_from_content_type(content_type: str) -> int | None:
    for part in content_type.split(";"):
        key, _, value = part.strip().partition("=")
        if key in {"rate", "sample_rate", "samplerate"}:
            return _safe_int(value, 8000)
    return None


def _safe_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _wire_audio_bytes(data: bytes, codec: AudioCodec) -> bytes:
    if codec in {"pcm16_8k", "pcm16_16k"}:
        return _swap_pcm16_endian(data)
    return data


def _internal_audio_bytes(data: bytes, codec: AudioCodec) -> bytes:
    if codec in {"pcm16_8k", "pcm16_16k"}:
        return _swap_pcm16_endian(data)
    return data


def _swap_pcm16_endian(data: bytes) -> bytes:
    if len(data) % 2 != 0:
        raise ValueError("PCM16 L16 audio payload must contain an even number of bytes.")
    swapped = bytearray(len(data))
    swapped[0::2] = data[1::2]
    swapped[1::2] = data[0::2]
    return bytes(swapped)


def _put_terminal(queue: asyncio.Queue[Any]) -> None:
    try:
        queue.put_nowait(None)
    except asyncio.QueueFull:
        with suppress(asyncio.QueueEmpty):
            queue.get_nowait()
        with suppress(asyncio.QueueFull):
            queue.put_nowait(None)
