"""Fixed-duration audio frame chunking."""

from collections.abc import Iterator

from voice_agent.audio.converter import bytes_per_ms, duration_ms_for_bytes, silence_bytes
from voice_agent.contracts.audio import AudioFrame


def chunk_size_bytes(frame: AudioFrame, chunk_ms: int) -> int:
    if chunk_ms <= 0:
        raise ValueError("chunk_ms must be positive.")
    size = round(bytes_per_ms(frame.codec, frame.channels) * chunk_ms)
    if size <= 0:
        raise ValueError("Calculated chunk size must be positive.")
    return size


def chunk_audio_frame(
    frame: AudioFrame,
    chunk_ms: int = 20,
    pad_final: bool = False,
) -> Iterator[AudioFrame]:
    size = chunk_size_bytes(frame, chunk_ms)
    timestamp_ms = frame.timestamp_ms

    for offset in range(0, len(frame.data), size):
        chunk = frame.data[offset : offset + size]
        if len(chunk) < size:
            if not pad_final:
                duration_ms = duration_ms_for_bytes(chunk, frame.codec, frame.channels)
            else:
                chunk += silence_bytes(frame.codec, chunk_ms, frame.channels)[: size - len(chunk)]
                duration_ms = chunk_ms
        else:
            duration_ms = chunk_ms

        yield AudioFrame(
            call_id=frame.call_id,
            data=chunk,
            timestamp_ms=timestamp_ms,
            sample_rate=frame.sample_rate,
            codec=frame.codec,
            channels=frame.channels,
            sequence_id=frame.sequence_id,
            duration_ms=duration_ms,
            meta={**frame.meta, "chunk_offset": offset},
        )
        timestamp_ms += duration_ms
