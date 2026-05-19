from voice_agent.audio.chunker import chunk_audio_frame, chunk_size_bytes
from voice_agent.audio.converter import silence_bytes
from voice_agent.contracts.audio import AudioFrame


def test_chunk_size_matches_phase_plan_values() -> None:
    assert chunk_size_bytes(frame("mulaw_8k", 8000, 20), 20) == 160
    assert chunk_size_bytes(frame("pcm16_8k", 8000, 20), 20) == 320
    assert chunk_size_bytes(frame("pcm16_16k", 16000, 20), 20) == 640


def test_chunk_audio_frame_splits_into_fixed_20ms_frames() -> None:
    source = frame("mulaw_8k", 8000, 60)

    chunks = list(chunk_audio_frame(source, chunk_ms=20))

    assert len(chunks) == 3
    assert [len(chunk.data) for chunk in chunks] == [160, 160, 160]
    assert [chunk.timestamp_ms for chunk in chunks] == [1000, 1020, 1040]
    assert all(chunk.duration_ms == 20 for chunk in chunks)


def test_chunk_audio_frame_can_pad_final_chunk() -> None:
    source = AudioFrame(
        call_id="call-chunk",
        data=silence_bytes("mulaw_8k", 25),
        timestamp_ms=1000,
        sample_rate=8000,
        codec="mulaw_8k",
        duration_ms=25,
    )

    chunks = list(chunk_audio_frame(source, chunk_ms=20, pad_final=True))

    assert [len(chunk.data) for chunk in chunks] == [160, 160]
    assert [chunk.duration_ms for chunk in chunks] == [20, 20]


def frame(codec: str, sample_rate: int, duration_ms: int) -> AudioFrame:
    return AudioFrame(
        call_id="call-chunk",
        data=silence_bytes(codec, duration_ms),
        timestamp_ms=1000,
        sample_rate=sample_rate,
        codec=codec,
        duration_ms=duration_ms,
    )
