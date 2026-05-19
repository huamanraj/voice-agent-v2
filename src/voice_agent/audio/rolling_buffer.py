"""Bounded rolling audio buffer for Smart-Turn/VAD context."""

from dataclasses import dataclass, field

from voice_agent.audio.converter import duration_ms_for_bytes
from voice_agent.contracts.audio import AudioFrame


@dataclass(slots=True)
class RollingAudioBuffer:
    call_id: str
    max_duration_ms: int = 8000
    sample_rate: int = 16000
    codec: str = "pcm16_16k"
    channels: int = 1
    _data: bytearray = field(default_factory=bytearray)
    _latest_timestamp_ms: int | None = None

    @property
    def max_bytes(self) -> int:
        return round(self.sample_rate * 2 * self.channels * self.max_duration_ms / 1000)

    @property
    def duration_ms(self) -> int:
        return duration_ms_for_bytes(bytes(self._data), "pcm16_16k", self.channels)

    def append(self, frame: AudioFrame) -> None:
        if frame.call_id != self.call_id:
            raise ValueError("Cannot append audio for a different call_id.")
        if frame.codec != self.codec or frame.sample_rate != self.sample_rate:
            raise ValueError("RollingAudioBuffer requires PCM16 16k mono frames.")
        if frame.channels != self.channels:
            raise ValueError("RollingAudioBuffer channel count mismatch.")

        self._data.extend(frame.data)
        if len(self._data) > self.max_bytes:
            del self._data[: len(self._data) - self.max_bytes]
        self._latest_timestamp_ms = frame.timestamp_ms

    def bytes(self) -> bytes:
        return bytes(self._data)

    def frame(self) -> AudioFrame:
        return AudioFrame(
            call_id=self.call_id,
            data=self.bytes(),
            timestamp_ms=self._latest_timestamp_ms or 0,
            sample_rate=self.sample_rate,
            codec="pcm16_16k",
            channels=self.channels,
            duration_ms=self.duration_ms,
        )

    def clear(self) -> None:
        self._data.clear()
        self._latest_timestamp_ms = None
