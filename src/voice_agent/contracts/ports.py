"""Provider ports consumed by the core runtime."""

from collections.abc import AsyncIterator
from typing import Any, Protocol, runtime_checkable

from voice_agent.contracts.audio import AudioFrame
from voice_agent.contracts.capabilities import (
    LLMCapabilities,
    STTCapabilities,
    TTSCapabilities,
    TelephonyCapabilities,
)
from voice_agent.contracts.events import PlaybackEvent, SpeechStart, SpeechStop, TranscriptEvent


@runtime_checkable
class TelephonyPort(Protocol):
    provider_name: str
    capabilities: TelephonyCapabilities

    async def start(self) -> None: ...
    async def receive_audio(self) -> AsyncIterator[AudioFrame]: ...
    async def send_audio(self, frame: AudioFrame) -> None: ...
    async def clear_playback(self, reason: str) -> None: ...
    async def send_checkpoint(self, checkpoint_id: str) -> None: ...
    async def playback_events(self) -> AsyncIterator[PlaybackEvent]: ...
    async def hangup(self, reason: str) -> None: ...
    async def stop(self, reason: str) -> None: ...


@runtime_checkable
class STTPort(Protocol):
    provider_name: str
    capabilities: STTCapabilities

    async def start(self, call_id: str, language_hint: str | None = None) -> None: ...
    async def send_audio(self, frame: AudioFrame) -> None: ...
    async def transcripts(self) -> AsyncIterator[TranscriptEvent]: ...
    async def speech_events(self) -> AsyncIterator[SpeechStart | SpeechStop]: ...
    async def update_language_hint(self, language: str) -> None: ...
    async def stop(self) -> None: ...


@runtime_checkable
class TTSPort(Protocol):
    provider_name: str
    capabilities: TTSCapabilities

    async def start(self, call_id: str, voice: str, language: str) -> None: ...
    async def synthesize(
        self,
        text: str,
        message_id: str,
        sequence_id: int,
    ) -> AsyncIterator[AudioFrame]: ...
    async def cancel(self, message_id: str, reason: str) -> None: ...
    async def stop(self) -> None: ...


@runtime_checkable
class LLMPort(Protocol):
    provider_name: str
    capabilities: LLMCapabilities

    async def stream_response(
        self,
        call_id: str,
        messages: list[dict[str, Any]],
        response_id: str,
    ) -> AsyncIterator[str]: ...
    async def classify(
        self,
        call_id: str,
        prompt: str,
        schema: dict[str, Any] | None = None,
    ) -> dict[str, Any]: ...
    async def cancel(self, response_id: str) -> None: ...
    async def stop(self) -> None: ...


@runtime_checkable
class LiveStorePort(Protocol):
    provider_name: str

    async def get_call_state(self, call_id: str) -> dict[str, Any] | None: ...
    async def set_call_state(self, call_id: str, state: dict[str, Any]) -> None: ...
    async def delete_call_state(self, call_id: str) -> None: ...


@runtime_checkable
class FinalStorePort(Protocol):
    provider_name: str

    async def save_call(self, call_id: str, record: dict[str, Any]) -> None: ...


@runtime_checkable
class ObservabilityPort(Protocol):
    provider_name: str

    async def emit(self, event_name: str, payload: dict[str, Any]) -> None: ...
    async def flush(self) -> None: ...


@runtime_checkable
class VADPort(Protocol):
    provider_name: str

    async def process_audio(self, frame: AudioFrame) -> AsyncIterator[Any]: ...


@runtime_checkable
class TurnDetectionPort(Protocol):
    provider_name: str

    async def classify_turn(self, transcript: str, context: dict[str, Any]) -> dict[str, Any]: ...


@runtime_checkable
class MemoryPort(Protocol):
    provider_name: str

    async def load(self, call_id: str) -> list[dict[str, Any]]: ...
    async def append(self, call_id: str, item: dict[str, Any]) -> None: ...
