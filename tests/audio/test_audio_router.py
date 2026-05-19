import asyncio

from voice_agent.audio.audio_router import AudioRouter
from voice_agent.audio.converter import silence_bytes
from voice_agent.audio.rolling_buffer import RollingAudioBuffer
from voice_agent.config import get_settings
from voice_agent.contracts.audio import AudioFrame
from voice_agent.core.queues.queue_manager import create_session_queues, queue_sizes_from_settings


def test_audio_router_routes_stt_original_and_vad_pcm16_16k() -> None:
    async def scenario() -> None:
        queues = create_session_queues(queue_sizes_from_settings(get_settings()))
        rolling_buffer = RollingAudioBuffer(call_id="call-route")
        router = AudioRouter(
            call_id="call-route",
            queues=queues,
            rolling_buffer=rolling_buffer,
        )
        source = AudioFrame(
            call_id="call-route",
            data=silence_bytes("mulaw_8k", 20),
            timestamp_ms=1000,
            sample_rate=8000,
            codec="mulaw_8k",
            duration_ms=20,
        )

        await router.route_inbound(source)

        stt_packet = await queues.stt_audio.get()
        vad_packet = await queues.vad_audio.get()
        rolling_packet = await queues.rolling_audio.get()

        assert stt_packet.data["frame"].codec == "mulaw_8k"
        assert vad_packet.data["frame"].codec == "pcm16_16k"
        assert len(vad_packet.data["frame"].data) == 640
        assert rolling_packet.data["frame"].codec == "pcm16_16k"
        assert rolling_buffer.duration_ms == 20

    asyncio.run(scenario())
