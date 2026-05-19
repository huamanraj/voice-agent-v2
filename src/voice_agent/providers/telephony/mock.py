"""In-memory telephony adapter for offline simulations."""

import asyncio
from collections.abc import AsyncIterator

from voice_agent.contracts.audio import AudioFrame
from voice_agent.contracts.capabilities import TelephonyCapabilities
from voice_agent.contracts.events import PlaybackEvent
from voice_agent.contracts.packets import now_ms


class MockTelephony:
    provider_name = "mock"
    capabilities = TelephonyCapabilities(
        supports_clear_playback=True,
        supports_playback_checkpoint=True,
        supports_bidirectional_audio=True,
        inbound_codec="mulaw_8k",
        outbound_codec="mulaw_8k",
    )

    def __init__(self, call_id: str, queue_maxsize: int = 100) -> None:
        self.call_id = call_id
        self.started = False
        self.stopped = False
        self.stop_reason: str | None = None
        self.sent_audio: list[AudioFrame] = []
        self.checkpoints: list[str] = []
        self.clear_reasons: list[str] = []
        self._incoming_audio: asyncio.Queue[AudioFrame | None] = asyncio.Queue(queue_maxsize)
        self._playback_events: asyncio.Queue[PlaybackEvent | None] = asyncio.Queue()

    async def start(self) -> None:
        self.started = True

    async def enqueue_audio(self, frame: AudioFrame) -> None:
        await self._incoming_audio.put(frame)

    async def finish_input(self) -> None:
        await self._incoming_audio.put(None)

    async def receive_audio(self) -> AsyncIterator[AudioFrame]:
        while True:
            frame = await self._incoming_audio.get()
            if frame is None:
                break
            yield frame

    async def send_audio(self, frame: AudioFrame) -> None:
        self.sent_audio.append(frame)
        await self._playback_events.put(
            PlaybackEvent(
                call_id=frame.call_id,
                message_id=str(frame.meta.get("message_id", "mock-message")),
                sequence_id=frame.sequence_id or 0,
                checkpoint_id=str(frame.meta["checkpoint_id"])
                if "checkpoint_id" in frame.meta
                else None,
                event_type="started",
                ts_ms=now_ms(),
            )
        )

    async def clear_playback(self, reason: str) -> None:
        self.clear_reasons.append(reason)
        await self._playback_events.put(
            PlaybackEvent(
                call_id=self.call_id,
                message_id="mock-clear",
                sequence_id=0,
                checkpoint_id=None,
                event_type="cleared",
                ts_ms=now_ms(),
            )
        )

    async def send_checkpoint(self, checkpoint_id: str) -> None:
        self.checkpoints.append(checkpoint_id)
        await self._playback_events.put(
            PlaybackEvent(
                call_id=self.call_id,
                message_id="mock-message",
                sequence_id=0,
                checkpoint_id=checkpoint_id,
                event_type="checkpoint_played",
                ts_ms=now_ms(),
            )
        )

    async def playback_events(self) -> AsyncIterator[PlaybackEvent]:
        while True:
            event = await self._playback_events.get()
            if event is None:
                break
            yield event

    async def stop(self, reason: str) -> None:
        self.stopped = True
        self.stop_reason = reason
        await self.finish_input()
        await self._playback_events.put(None)
