"""Queue management for the async pipeline."""

import asyncio
from dataclasses import dataclass

from voice_agent.config import Settings
from voice_agent.contracts.packets import AgentPacket
from voice_agent.core.queues.backpressure import BackpressurePolicy


@dataclass(frozen=True, slots=True)
class QueueSizes:
    telephony_audio_in: int
    stt_audio: int
    vad_audio: int
    rolling_audio: int
    transcript_event: int
    speech_event: int
    turn_event: int
    interruption_event: int
    llm_request: int
    llm_output: int
    tts_request: int
    tts_audio: int
    telephony_audio_out: int
    playback_event: int
    metrics: int
    dtmf: int
    error: int


@dataclass(slots=True)
class SessionQueues:
    telephony_audio_in: asyncio.Queue[AgentPacket]
    stt_audio: asyncio.Queue[AgentPacket]
    vad_audio: asyncio.Queue[AgentPacket]
    rolling_audio: asyncio.Queue[AgentPacket]
    transcript_event: asyncio.Queue[AgentPacket]
    speech_event: asyncio.Queue[AgentPacket]
    turn_event: asyncio.Queue[AgentPacket]
    interruption_event: asyncio.Queue[AgentPacket]
    llm_request: asyncio.Queue[AgentPacket]
    llm_output: asyncio.Queue[AgentPacket]
    tts_request: asyncio.Queue[AgentPacket]
    tts_audio: asyncio.Queue[AgentPacket]
    telephony_audio_out: asyncio.Queue[AgentPacket]
    playback_event: asyncio.Queue[AgentPacket]
    metrics: asyncio.Queue[AgentPacket]
    dtmf: asyncio.Queue[AgentPacket]
    error: asyncio.Queue[AgentPacket]

    def all_queues(self) -> tuple[asyncio.Queue[AgentPacket], ...]:
        return (
            self.telephony_audio_in,
            self.stt_audio,
            self.vad_audio,
            self.rolling_audio,
            self.transcript_event,
            self.speech_event,
            self.turn_event,
            self.interruption_event,
            self.llm_request,
            self.llm_output,
            self.tts_request,
            self.tts_audio,
            self.telephony_audio_out,
            self.playback_event,
            self.metrics,
            self.dtmf,
            self.error,
        )


def queue_sizes_from_settings(settings: Settings) -> QueueSizes:
    return QueueSizes(
        telephony_audio_in=settings.queue_audio_in_max,
        stt_audio=settings.queue_stt_audio_max,
        vad_audio=settings.queue_vad_audio_max,
        rolling_audio=settings.queue_rolling_audio_max,
        transcript_event=settings.queue_transcript_event_max,
        speech_event=settings.queue_speech_event_max,
        turn_event=settings.queue_turn_event_max,
        interruption_event=settings.queue_interruption_event_max,
        llm_request=settings.queue_llm_request_max,
        llm_output=settings.queue_llm_output_max,
        tts_request=settings.queue_tts_request_max,
        tts_audio=settings.queue_tts_audio_max,
        telephony_audio_out=settings.queue_telephony_audio_out_max,
        playback_event=settings.queue_playback_event_max,
        metrics=settings.queue_metrics_max,
        dtmf=settings.queue_dtmf_max,
        error=settings.queue_error_max,
    )


def create_session_queues(sizes: QueueSizes) -> SessionQueues:
    return SessionQueues(
        telephony_audio_in=asyncio.Queue(sizes.telephony_audio_in),
        stt_audio=asyncio.Queue(sizes.stt_audio),
        vad_audio=asyncio.Queue(sizes.vad_audio),
        rolling_audio=asyncio.Queue(sizes.rolling_audio),
        transcript_event=asyncio.Queue(sizes.transcript_event),
        speech_event=asyncio.Queue(sizes.speech_event),
        turn_event=asyncio.Queue(sizes.turn_event),
        interruption_event=asyncio.Queue(sizes.interruption_event),
        llm_request=asyncio.Queue(sizes.llm_request),
        llm_output=asyncio.Queue(sizes.llm_output),
        tts_request=asyncio.Queue(sizes.tts_request),
        tts_audio=asyncio.Queue(sizes.tts_audio),
        telephony_audio_out=asyncio.Queue(sizes.telephony_audio_out),
        playback_event=asyncio.Queue(sizes.playback_event),
        metrics=asyncio.Queue(sizes.metrics),
        dtmf=asyncio.Queue(sizes.dtmf),
        error=asyncio.Queue(sizes.error),
    )


async def put_packet(
    queue: asyncio.Queue[AgentPacket],
    packet: AgentPacket,
    policy: BackpressurePolicy = BackpressurePolicy.BLOCK,
) -> bool:
    if policy == BackpressurePolicy.BLOCK:
        await queue.put(packet)
        return True

    if policy == BackpressurePolicy.DROP_METRICS and queue.full():
        return False

    if queue.full() and policy in {
        BackpressurePolicy.DROP_OLDEST,
        BackpressurePolicy.DROP_STALE_SEQUENCE,
    }:
        try:
            queue.get_nowait()
            queue.task_done()
        except asyncio.QueueEmpty:
            pass

    try:
        queue.put_nowait(packet)
        return True
    except asyncio.QueueFull:
        return False


async def broadcast_eos(queues: tuple[asyncio.Queue[AgentPacket], ...], call_id: str) -> None:
    eos = AgentPacket.eos_packet(call_id)
    for queue in queues:
        await put_packet(queue, eos, BackpressurePolicy.DROP_OLDEST)
