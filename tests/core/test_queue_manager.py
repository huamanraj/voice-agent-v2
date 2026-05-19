import asyncio

from voice_agent.config import get_settings
from voice_agent.contracts.packets import AgentPacket
from voice_agent.core.queues.backpressure import BackpressurePolicy
from voice_agent.core.queues.queue_manager import (
    create_session_queues,
    put_packet,
    queue_sizes_from_settings,
)


def test_queue_manager_uses_bounded_sizes_from_settings() -> None:
    sizes = queue_sizes_from_settings(get_settings())
    queues = create_session_queues(sizes)

    assert queues.telephony_audio_in.maxsize == sizes.telephony_audio_in
    assert queues.stt_audio.maxsize == sizes.stt_audio
    assert queues.tts_audio.maxsize == sizes.tts_audio
    assert queues.error.maxsize == sizes.error


def test_put_packet_drops_oldest_when_queue_is_full() -> None:
    async def scenario() -> None:
        queue: asyncio.Queue[AgentPacket] = asyncio.Queue(maxsize=1)
        first = AgentPacket.eos_packet("call-1", packet_type="first")
        second = AgentPacket.eos_packet("call-1", packet_type="second")

        assert await put_packet(queue, first)
        assert await put_packet(queue, second, BackpressurePolicy.DROP_OLDEST)

        assert queue.qsize() == 1
        assert (await queue.get()).packet_type == "second"

    asyncio.run(scenario())
