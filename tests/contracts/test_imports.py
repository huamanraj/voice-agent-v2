from voice_agent.config import get_settings
from voice_agent.contracts import AgentPacket, AudioFrame
from voice_agent.contracts.capabilities import LLMCapabilities
from voice_agent.contracts.packets import now_ms


def test_phase_one_contracts_import() -> None:
    settings = get_settings()
    frame = AudioFrame(
        call_id="call-test",
        data=b"",
        timestamp_ms=now_ms(),
        sample_rate=settings.telephony_sample_rate,
        codec="mulaw_8k",
    )
    packet = AgentPacket(
        packet_type="audio_frame",
        call_id=frame.call_id,
        turn_id=None,
        sequence_id=frame.sequence_id,
        request_id=None,
        timestamp_ms=frame.timestamp_ms,
        data={"bytes": frame.byte_length},
    )
    capabilities = LLMCapabilities(
        supports_streaming=True,
        supports_json_mode=True,
        supports_tool_calling=False,
    )

    assert packet.call_id == "call-test"
    assert capabilities.supports_streaming
