"""Audio data contracts."""

from dataclasses import dataclass, field
from typing import Any, Literal

AudioCodec = Literal["mulaw_8k", "pcm16_8k", "pcm16_16k", "opus_48k"]


@dataclass(slots=True)
class AudioFrame:
    call_id: str
    data: bytes
    timestamp_ms: int
    sample_rate: int
    codec: AudioCodec
    channels: int = 1
    sequence_id: int | None = None
    duration_ms: int | None = None
    meta: dict[str, Any] = field(default_factory=dict)

    @property
    def byte_length(self) -> int:
        return len(self.data)
