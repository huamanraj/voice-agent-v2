"""Bounded rolling audio buffer for Smart-Turn/VAD context."""

from collections import deque
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
    _frames: deque[AudioFrame] = field(default_factory=deque)
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
        self._frames.append(frame)
        if len(self._data) > self.max_bytes:
            bytes_to_trim = len(self._data) - self.max_bytes
            del self._data[:bytes_to_trim]
            self._trim_frame_history(bytes_to_trim)
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

    def frame_since(self, timestamp_ms: int | None) -> AudioFrame:
        if timestamp_ms is None:
            return self.frame()

        data = bytearray()
        first_timestamp_ms: int | None = None
        latest_timestamp_ms: int | None = None
        for frame in self._frames:
            duration_ms = frame.duration_ms or duration_ms_for_bytes(
                frame.data,
                "pcm16_16k",
                frame.channels,
            )
            if frame.timestamp_ms + duration_ms <= timestamp_ms:
                continue
            if first_timestamp_ms is None:
                first_timestamp_ms = frame.timestamp_ms
            latest_timestamp_ms = frame.timestamp_ms
            data.extend(frame.data)

        if not data:
            return self.frame()

        return AudioFrame(
            call_id=self.call_id,
            data=bytes(data),
            timestamp_ms=first_timestamp_ms or timestamp_ms,
            sample_rate=self.sample_rate,
            codec="pcm16_16k",
            channels=self.channels,
            duration_ms=duration_ms_for_bytes(bytes(data), "pcm16_16k", self.channels),
            meta={"latest_timestamp_ms": latest_timestamp_ms},
        )

    def clear(self) -> None:
        self._data.clear()
        self._frames.clear()
        self._latest_timestamp_ms = None

    def _trim_frame_history(self, bytes_to_trim: int) -> None:
        remaining = bytes_to_trim
        while self._frames and remaining > 0:
            frame = self._frames[0]
            if remaining >= len(frame.data):
                remaining -= len(frame.data)
                self._frames.popleft()
                continue

            trimmed_data = frame.data[remaining:]
            trimmed_duration_ms = duration_ms_for_bytes(
                trimmed_data,
                "pcm16_16k",
                frame.channels,
            )
            trimmed_offset_ms = (frame.duration_ms or 0) - trimmed_duration_ms
            self._frames[0] = AudioFrame(
                call_id=frame.call_id,
                data=trimmed_data,
                timestamp_ms=frame.timestamp_ms + max(0, trimmed_offset_ms),
                sample_rate=frame.sample_rate,
                codec=frame.codec,
                channels=frame.channels,
                sequence_id=frame.sequence_id,
                duration_ms=trimmed_duration_ms,
                meta=frame.meta,
            )
            remaining = 0
