from voice_agent.audio.converter import (
    convert_audio_frame,
    duration_ms_for_bytes,
    mulaw_to_pcm16,
    pcm16_to_mulaw,
    silence_bytes,
)
from voice_agent.contracts.audio import AudioFrame
from voice_agent.contracts.packets import now_ms


def test_mulaw_silence_decodes_to_pcm16_zero() -> None:
    assert mulaw_to_pcm16(b"\xff") == b"\x00\x00"
    assert pcm16_to_mulaw(b"\x00\x00") == b"\xff"


def test_convert_mulaw_8k_to_pcm16_16k() -> None:
    frame = AudioFrame(
        call_id="call-audio",
        data=silence_bytes("mulaw_8k", 20),
        timestamp_ms=now_ms(),
        sample_rate=8000,
        codec="mulaw_8k",
        duration_ms=20,
    )

    converted = convert_audio_frame(frame, "pcm16_16k")

    assert converted.codec == "pcm16_16k"
    assert converted.sample_rate == 16000
    assert len(converted.data) == 640
    assert converted.duration_ms == 20


def test_convert_pcm16_16k_to_mulaw_8k() -> None:
    frame = AudioFrame(
        call_id="call-audio",
        data=silence_bytes("pcm16_16k", 20),
        timestamp_ms=now_ms(),
        sample_rate=16000,
        codec="pcm16_16k",
        duration_ms=20,
    )

    converted = convert_audio_frame(frame, "mulaw_8k")

    assert converted.codec == "mulaw_8k"
    assert converted.sample_rate == 8000
    assert len(converted.data) == 160
    assert duration_ms_for_bytes(converted.data, converted.codec) == 20
