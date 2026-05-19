"""Audio frame conversion utilities."""

from array import array

from voice_agent.audio.resample import (
    pcm16_bytes_to_samples,
    resample_pcm16_mono,
    samples_to_pcm16_bytes,
)
from voice_agent.contracts.audio import AudioCodec, AudioFrame

MULAW_BIAS = 0x84
MULAW_CLIP = 32635
MULAW_SEGMENT_ENDS = (0xFF, 0x1FF, 0x3FF, 0x7FF, 0xFFF, 0x1FFF, 0x3FFF, 0x7FFF)


def mulaw_to_pcm16(data: bytes) -> bytes:
    samples = array("h")
    for value in data:
        decoded = (~value) & 0xFF
        sign = decoded & 0x80
        exponent = (decoded >> 4) & 0x07
        mantissa = decoded & 0x0F
        sample = ((mantissa << 3) + MULAW_BIAS) << exponent
        sample -= MULAW_BIAS
        samples.append(-sample if sign else sample)
    return samples_to_pcm16_bytes(samples)


def pcm16_to_mulaw(data: bytes) -> bytes:
    encoded = bytearray()
    for sample in pcm16_bytes_to_samples(data):
        encoded.append(_linear_sample_to_mulaw(sample))
    return bytes(encoded)


def convert_audio_frame(frame: AudioFrame, target_codec: AudioCodec) -> AudioFrame:
    if frame.codec == target_codec:
        return frame

    pcm16_data = to_pcm16(frame)
    target_rate = sample_rate_for_codec(target_codec)
    if frame.sample_rate != target_rate:
        pcm16_data = resample_pcm16_mono(pcm16_data, frame.sample_rate, target_rate)

    if target_codec == "pcm16_8k" or target_codec == "pcm16_16k":
        data = pcm16_data
    elif target_codec == "mulaw_8k":
        if target_rate != 8000:
            raise ValueError("mulaw_8k target must use 8000 Hz.")
        data = pcm16_to_mulaw(pcm16_data)
    else:
        raise ValueError(f"Unsupported target codec: {target_codec}")

    return AudioFrame(
        call_id=frame.call_id,
        data=data,
        timestamp_ms=frame.timestamp_ms,
        sample_rate=target_rate,
        codec=target_codec,
        channels=frame.channels,
        sequence_id=frame.sequence_id,
        duration_ms=duration_ms_for_bytes(data, target_codec, frame.channels),
        meta={**frame.meta, "source_codec": frame.codec},
    )


def to_pcm16(frame: AudioFrame) -> bytes:
    if frame.channels != 1:
        raise ValueError("Only mono audio is supported in Phase 7.")
    if frame.codec in {"opus_16k", "opus_48k"}:
        raise ValueError(f"Opus decoding is not implemented for {frame.codec}.")
    if frame.codec == "mulaw_8k":
        return mulaw_to_pcm16(frame.data)
    if frame.codec in {"pcm16_8k", "pcm16_16k"}:
        if len(frame.data) % 2 != 0:
            raise ValueError("PCM16 frame data length must be even.")
        return frame.data
    raise ValueError(f"Unsupported source codec: {frame.codec}")


def sample_rate_for_codec(codec: AudioCodec) -> int:
    if codec.endswith("_8k"):
        return 8000
    if codec.endswith("_16k"):
        return 16000
    if codec.endswith("_48k"):
        return 48000
    raise ValueError(f"Cannot infer sample rate for codec: {codec}")


def bytes_per_sample(codec: AudioCodec) -> int:
    if codec == "mulaw_8k":
        return 1
    if codec in {"pcm16_8k", "pcm16_16k"}:
        return 2
    raise ValueError(f"Unsupported codec for byte sizing: {codec}")


def bytes_per_ms(codec: AudioCodec, channels: int = 1) -> float:
    return sample_rate_for_codec(codec) * bytes_per_sample(codec) * channels / 1000


def duration_ms_for_bytes(data: bytes, codec: AudioCodec, channels: int = 1) -> int:
    per_ms = bytes_per_ms(codec, channels)
    return round(len(data) / per_ms) if per_ms else 0


def silence_bytes(codec: AudioCodec, duration_ms: int, channels: int = 1) -> bytes:
    length = round(bytes_per_ms(codec, channels) * duration_ms)
    if codec == "mulaw_8k":
        return b"\xff" * length
    if codec in {"pcm16_8k", "pcm16_16k"}:
        return b"\x00" * length
    raise ValueError(f"Unsupported codec for silence: {codec}")


def _linear_sample_to_mulaw(sample: int) -> int:
    if sample < 0:
        sample = min(-sample, MULAW_CLIP)
        mask = 0x7F
    else:
        sample = min(sample, MULAW_CLIP)
        mask = 0xFF

    sample += MULAW_BIAS
    segment = _mulaw_segment(sample)
    mantissa = (sample >> (segment + 3)) & 0x0F
    return ((segment << 4) | mantissa) ^ mask


def _mulaw_segment(sample: int) -> int:
    for index, end in enumerate(MULAW_SEGMENT_ENDS):
        if sample <= end:
            return index
    return 7
