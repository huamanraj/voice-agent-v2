"""Audio routing for STT, VAD, and rolling context paths."""

from dataclasses import dataclass

from voice_agent.audio.converter import convert_audio_frame
from voice_agent.audio.rolling_buffer import RollingAudioBuffer
from voice_agent.contracts.audio import AudioCodec, AudioFrame
from voice_agent.contracts.packets import AgentPacket, now_ms
from voice_agent.core.queues.backpressure import BackpressurePolicy
from voice_agent.core.queues.queue_manager import SessionQueues, put_packet


@dataclass(slots=True)
class AudioRouter:
    call_id: str
    queues: SessionQueues
    rolling_buffer: RollingAudioBuffer
    stt_target_codec: AudioCodec = "mulaw_8k"

    async def route_inbound(self, frame: AudioFrame) -> None:
        stt_frame = convert_audio_frame(frame, self.stt_target_codec) if frame.codec != self.stt_target_codec else frame
        vad_frame = convert_audio_frame(frame, "pcm16_16k")
        self.rolling_buffer.append(vad_frame)

        await put_packet(
            self.queues.telephony_audio_in,
            self._packet("audio_frame", frame),
            BackpressurePolicy.DROP_OLDEST,
        )
        await put_packet(
            self.queues.stt_audio,
            self._packet("audio_frame", stt_frame),
            BackpressurePolicy.DROP_OLDEST,
        )
        await put_packet(
            self.queues.vad_audio,
            self._packet("audio_frame", vad_frame),
            BackpressurePolicy.DROP_OLDEST,
        )
        await put_packet(
            self.queues.rolling_audio,
            self._packet("audio_frame", vad_frame),
            BackpressurePolicy.DROP_OLDEST,
        )

    def _packet(self, packet_type: str, frame: AudioFrame) -> AgentPacket:
        return AgentPacket(
            packet_type=packet_type,
            call_id=self.call_id,
            turn_id=None,
            sequence_id=frame.sequence_id,
            request_id=None,
            timestamp_ms=now_ms(),
            data={"frame": frame},
        )
