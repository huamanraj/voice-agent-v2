"""In-memory STT adapter for offline simulations."""

import asyncio
from collections.abc import AsyncIterator

from voice_agent.contracts.audio import AudioFrame
from voice_agent.contracts.capabilities import STTCapabilities
from voice_agent.contracts.events import SpeechStart, SpeechStop, TranscriptEvent


class MockSTT:
    provider_name = "mock"
    capabilities = STTCapabilities(
        supports_interim=True,
        supports_final=True,
        supports_vad_events=False,
        supports_language_detection=True,
        supports_code_switching=True,
        accepted_codecs=("mulaw_8k", "pcm16_8k", "pcm16_16k"),
    )

    def __init__(self) -> None:
        self.call_id: str | None = None
        self.language_hint: str | None = None
        self.audio_frames: list[AudioFrame] = []
        self._transcripts: asyncio.Queue[TranscriptEvent | None] = asyncio.Queue()
        self._speech_events: asyncio.Queue[SpeechStart | SpeechStop | None] = asyncio.Queue()

    async def start(self, call_id: str, language_hint: str | None = None) -> None:
        self.call_id = call_id
        self.language_hint = language_hint

    async def send_audio(self, frame: AudioFrame) -> None:
        self.audio_frames.append(frame)
        transcript = frame.meta.get("transcript")
        if transcript is None:
            return

        await self._transcripts.put(
            TranscriptEvent(
                call_id=frame.call_id,
                text=str(transcript),
                is_final=bool(frame.meta.get("is_final", True)),
                confidence=float(frame.meta.get("confidence", 1.0)),
                language=str(frame.meta["language"]) if "language" in frame.meta else self.language_hint,
                start_ms=frame.timestamp_ms,
                end_ms=frame.timestamp_ms + (frame.duration_ms or 0),
                provider=self.provider_name,
                asr_turn_id=str(frame.meta["asr_turn_id"]) if "asr_turn_id" in frame.meta else None,
            )
        )

    async def transcripts(self) -> AsyncIterator[TranscriptEvent]:
        while True:
            transcript = await self._transcripts.get()
            if transcript is None:
                break
            yield transcript

    async def speech_events(self) -> AsyncIterator[SpeechStart | SpeechStop]:
        while True:
            event = await self._speech_events.get()
            if event is None:
                break
            yield event

    async def update_language_hint(self, language: str) -> None:
        self.language_hint = language

    async def health_check(self) -> bool:
        return self.call_id is not None

    async def stop(self) -> None:
        await self._transcripts.put(None)
        await self._speech_events.put(None)
