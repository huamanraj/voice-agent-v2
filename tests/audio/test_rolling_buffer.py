from voice_agent.audio.converter import silence_bytes
from voice_agent.audio.rolling_buffer import RollingAudioBuffer
from voice_agent.contracts.audio import AudioFrame


def test_rolling_audio_buffer_keeps_last_eight_seconds() -> None:
    buffer = RollingAudioBuffer(call_id="call-roll", max_duration_ms=8000)
    buffer.append(frame(duration_ms=9000))

    assert buffer.duration_ms == 8000
    assert len(buffer.bytes()) == 256000
    assert buffer.frame().codec == "pcm16_16k"


def test_rolling_audio_buffer_rejects_wrong_codec() -> None:
    buffer = RollingAudioBuffer(call_id="call-roll")
    wrong_frame = AudioFrame(
        call_id="call-roll",
        data=silence_bytes("mulaw_8k", 20),
        timestamp_ms=1000,
        sample_rate=8000,
        codec="mulaw_8k",
        duration_ms=20,
    )

    try:
        buffer.append(wrong_frame)
    except ValueError as exc:
        assert "PCM16 16k" in str(exc)
    else:
        raise AssertionError("Expected wrong codec to be rejected.")


def test_rolling_audio_buffer_returns_audio_since_timestamp() -> None:
    buffer = RollingAudioBuffer(call_id="call-roll")
    buffer.append(frame(duration_ms=20, timestamp_ms=1000))
    buffer.append(frame(duration_ms=20, timestamp_ms=1020))
    buffer.append(frame(duration_ms=20, timestamp_ms=1040))

    segment = buffer.frame_since(1020)

    assert segment.timestamp_ms == 1020
    assert segment.duration_ms == 40
    assert len(segment.data) == 1280


def frame(duration_ms: int, timestamp_ms: int = 1000) -> AudioFrame:
    return AudioFrame(
        call_id="call-roll",
        data=silence_bytes("pcm16_16k", duration_ms),
        timestamp_ms=timestamp_ms,
        sample_rate=16000,
        codec="pcm16_16k",
        duration_ms=duration_ms,
    )
