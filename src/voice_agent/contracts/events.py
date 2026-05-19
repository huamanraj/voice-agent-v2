"""Core event contracts."""

from dataclasses import dataclass, field
from typing import Any, Literal

SpeechSource = Literal["vad", "stt", "telephony"]
PlaybackEventType = Literal["started", "checkpoint_played", "fully_played", "cleared"]


@dataclass(frozen=True, slots=True)
class SpeechStart:
    call_id: str
    ts_ms: int
    source: SpeechSource
    confidence: float


@dataclass(frozen=True, slots=True)
class SpeechStop:
    call_id: str
    ts_ms: int
    source: SpeechSource
    confidence: float


@dataclass(frozen=True, slots=True)
class TranscriptEvent:
    call_id: str
    text: str
    is_final: bool
    confidence: float
    language: str | None
    start_ms: int | None
    end_ms: int | None
    provider: str
    asr_turn_id: str | None = None


@dataclass(frozen=True, slots=True)
class SmartTurnResult:
    call_id: str
    turn_id: int
    is_complete: bool
    confidence: float
    reason: str


@dataclass(frozen=True, slots=True)
class UserTurnFinal:
    call_id: str
    turn_id: int
    text: str
    language: str | None
    confidence: float
    start_ms: int | None
    end_ms: int | None


@dataclass(frozen=True, slots=True)
class InterruptionStarted:
    call_id: str
    turn_id: int | None
    sequence_id: int
    reason: str
    transcript: str | None
    ts_ms: int


@dataclass(frozen=True, slots=True)
class InterruptionRejected:
    call_id: str
    turn_id: int | None
    sequence_id: int
    reason: str
    transcript: str | None
    ts_ms: int


@dataclass(frozen=True, slots=True)
class PlaybackEvent:
    call_id: str
    message_id: str
    sequence_id: int
    checkpoint_id: str | None
    event_type: PlaybackEventType
    ts_ms: int


@dataclass(frozen=True, slots=True)
class ProviderError:
    call_id: str
    provider: str
    error_type: str
    error_code: str | None
    message: str
    retryable: bool
    details: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class HangupEvent:
    call_id: str
    reason: str
    ts_ms: int
