"""Provider-neutral session orchestration skeleton."""

import asyncio
from dataclasses import asdict, dataclass, field
from collections.abc import Awaitable, Callable
from typing import Any

from voice_agent.audio.audio_router import AudioRouter
from voice_agent.audio.rolling_buffer import RollingAudioBuffer
from voice_agent.config import Settings, get_settings
from voice_agent.contracts.audio import AudioFrame
from voice_agent.contracts.events import (
    InterruptionRejected,
    InterruptionStarted,
    PlaybackEvent,
    ProviderError,
    SpeechStart,
    TranscriptEvent,
    UserTurnFinal,
)
from voice_agent.contracts.packets import AgentPacket, now_ms
from voice_agent.contracts.ports import (
    FinalStorePort,
    LLMPort,
    LiveStorePort,
    STTPort,
    TTSPort,
    TelephonyPort,
)
from voice_agent.core.queues.backpressure import BackpressurePolicy
from voice_agent.core.queues.queue_manager import (
    SessionQueues,
    broadcast_eos,
    create_session_queues,
    put_packet,
    queue_sizes_from_settings,
)
from voice_agent.core.interruption.output_gate import OutputDecision, OutputGate
from voice_agent.core.interruption.interruption_manager import (
    InterruptionManager,
    InterruptionOutcome,
)
from voice_agent.core.interruption.sequence_manager import SequenceManager
from voice_agent.core.state_machine import CallState
from voice_agent.core.turn_detection.turn_manager import TurnManager


@dataclass(slots=True)
class SessionProviders:
    telephony: TelephonyPort
    stt: STTPort
    tts: TTSPort
    llm: LLMPort
    live_store: LiveStorePort | None = None
    final_store: FinalStorePort | None = None


@dataclass(slots=True)
class SessionStats:
    audio_frames_received: int = 0
    transcripts_received: int = 0
    user_turns_finalized: int = 0
    llm_responses_started: int = 0
    tts_chunks_created: int = 0
    audio_chunks_sent: int = 0
    playback_events_received: int = 0
    stale_audio_chunks_dropped: int = 0
    blocked_audio_chunks_dropped: int = 0
    waited_audio_chunks_dropped: int = 0
    interruption_candidates_started: int = 0
    interruptions_confirmed: int = 0
    interruptions_rejected: int = 0
    errors: int = 0


@dataclass(slots=True)
class SessionOrchestrator:
    call_id: str
    providers: SessionProviders
    settings: Settings | None = None
    state: CallState = field(init=False)
    queues: SessionQueues = field(init=False)
    stats: SessionStats = field(init=False)
    errors: list[ProviderError] = field(init=False)
    tasks: dict[str, asyncio.Task[None]] = field(init=False)
    sequence_manager: SequenceManager = field(init=False)
    output_gate: OutputGate = field(init=False)
    interruption_manager: InterruptionManager = field(init=False)
    turn_manager: TurnManager = field(init=False)
    rolling_audio_buffer: RollingAudioBuffer = field(init=False)
    audio_router: AudioRouter = field(init=False)
    _shutdown_started: bool = field(init=False)

    def __post_init__(self) -> None:
        self.settings = self.settings or get_settings()
        self.state = CallState.NEW
        self.queues = create_session_queues(queue_sizes_from_settings(self.settings))
        self.stats = SessionStats()
        self.errors: list[ProviderError] = []
        self.tasks: dict[str, asyncio.Task[None]] = {}
        self.sequence_manager = SequenceManager()
        self.output_gate = OutputGate()
        self.rolling_audio_buffer = RollingAudioBuffer(call_id=self.call_id)
        self.audio_router = AudioRouter(
            call_id=self.call_id,
            queues=self.queues,
            rolling_buffer=self.rolling_audio_buffer,
        )
        self.interruption_manager = InterruptionManager(
            call_id=self.call_id,
            settings=self.settings,
            output_gate=self.output_gate,
            sequence_manager=self.sequence_manager,
            telephony=self.providers.telephony,
            tts=self.providers.tts,
            llm=self.providers.llm,
        )
        self.turn_manager = TurnManager(self.call_id, self.settings)
        self._shutdown_started = False

    async def start(self) -> None:
        if self.state != CallState.NEW:
            raise RuntimeError(f"Session {self.call_id} already started in state {self.state}.")

        self._shutdown_started = False
        self.state = CallState.STARTING
        await self._save_live_state()
        await self.providers.telephony.start()
        await self.providers.stt.start(self.call_id)
        await self.providers.tts.start(self.call_id, voice="mock-voice", language="en-IN")

        self.tasks = {
            "receive_audio_loop": self._create_task("receive_audio_loop", self._receive_audio_loop),
            "stt_sender_loop": self._create_task("stt_sender_loop", self._stt_sender_loop),
            "stt_receiver_loop": self._create_task("stt_receiver_loop", self._stt_receiver_loop),
            "vad_processor_loop": self._create_task(
                "vad_processor_loop",
                lambda: self._drain_loop(self.queues.vad_audio),
            ),
            "rolling_buffer_loop": self._create_task(
                "rolling_buffer_loop",
                lambda: self._drain_loop(self.queues.rolling_audio),
            ),
            "turn_manager_loop": self._create_task("turn_manager_loop", self._turn_manager_loop),
            "interruption_manager_loop": self._create_task(
                "interruption_manager_loop",
                self._interruption_manager_loop,
            ),
            "llm_loop": self._create_task("llm_loop", self._llm_loop),
            "tts_loop": self._create_task("tts_loop", self._tts_loop),
            "output_loop": self._create_task("output_loop", self._output_loop),
            "playback_loop": self._create_task("playback_loop", self._playback_loop),
            "metrics_loop": self._create_task("metrics_loop", self._metrics_loop),
            "error_loop": self._create_task("error_loop", self._error_loop),
        }
        self.state = CallState.LISTENING
        await self._save_live_state()

    async def run(self) -> SessionStats:
        await self.start()
        await self.wait_closed()
        return self.stats

    async def wait_closed(self) -> None:
        if not self.tasks:
            return

        await asyncio.gather(*self.tasks.values(), return_exceptions=True)
        await self._finalize_closed()

    async def shutdown(self, reason: str = "shutdown_requested") -> None:
        if self._shutdown_started:
            return

        self._shutdown_started = True
        self.state = CallState.CLOSING
        await self._save_live_state()
        await self._send_eos_to_all_queues()
        await self._stop_providers(reason)

        current_task = asyncio.current_task()
        for task in self.tasks.values():
            if task is not current_task and not task.done():
                task.cancel()

        await asyncio.gather(
            *(task for task in self.tasks.values() if task is not current_task),
            return_exceptions=True,
        )
        await self._finalize_closed(reason=reason)

    def _create_task(
        self,
        name: str,
        coroutine_factory: Callable[[], Awaitable[None]],
    ) -> asyncio.Task[None]:
        return asyncio.create_task(
            self._guard_loop(name, coroutine_factory),
            name=f"{self.call_id}:{name}",
        )

    async def _guard_loop(
        self,
        name: str,
        coroutine_factory: Callable[[], Awaitable[None]],
    ) -> None:
        try:
            await coroutine_factory()
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            error = ProviderError(
                call_id=self.call_id,
                provider="core",
                error_type=name,
                error_code=exc.__class__.__name__,
                message=str(exc),
                retryable=False,
            )
            self.errors.append(error)
            self.stats.errors += 1
            await self._emit_error(error)

    async def _receive_audio_loop(self) -> None:
        async for frame in self.providers.telephony.receive_audio():
            self.stats.audio_frames_received += 1
            await self.audio_router.route_inbound(frame)

        for queue in (self.queues.stt_audio, self.queues.vad_audio, self.queues.rolling_audio):
            await put_packet(queue, AgentPacket.eos_packet(self.call_id), BackpressurePolicy.DROP_OLDEST)

    async def _stt_sender_loop(self) -> None:
        while True:
            packet = await self.queues.stt_audio.get()
            if packet.eos:
                await self.providers.stt.stop()
                self.queues.stt_audio.task_done()
                break

            frame = packet.data["frame"]
            if not isinstance(frame, AudioFrame):
                raise TypeError("stt_audio packet must contain an AudioFrame.")
            await self.providers.stt.send_audio(frame)
            self.queues.stt_audio.task_done()

    async def _stt_receiver_loop(self) -> None:
        async for transcript in self.providers.stt.transcripts():
            self.stats.transcripts_received += 1
            packet = self._packet(
                "transcript_final" if transcript.is_final else "transcript_interim",
                {"event": transcript},
            )
            await put_packet(self.queues.transcript_event, packet, BackpressurePolicy.DROP_OLDEST)
            await put_packet(self.queues.interruption_event, packet, BackpressurePolicy.DROP_OLDEST)

        await put_packet(
            self.queues.transcript_event,
            AgentPacket.eos_packet(self.call_id),
            BackpressurePolicy.DROP_OLDEST,
        )
        await put_packet(
            self.queues.interruption_event,
            AgentPacket.eos_packet(self.call_id),
            BackpressurePolicy.DROP_OLDEST,
        )

    async def _turn_manager_loop(self) -> None:
        while True:
            packet = await self.queues.transcript_event.get()
            if packet.eos:
                forced_turn = self.turn_manager.force_emit("transcript_eos", now_ms())
                if forced_turn is not None:
                    await self._emit_user_turn(forced_turn)
                await put_packet(
                    self.queues.turn_event,
                    AgentPacket.eos_packet(self.call_id),
                    BackpressurePolicy.DROP_OLDEST,
                )
                self.queues.transcript_event.task_done()
                break

            transcript = packet.data["event"]
            if not isinstance(transcript, TranscriptEvent):
                raise TypeError("transcript_event packet must contain a TranscriptEvent.")

            self.turn_manager.handle_transcript(transcript)
            turn = self.turn_manager.emit_turn(now_ms())
            if turn is not None:
                await self._emit_user_turn(turn)
            self.queues.transcript_event.task_done()

    async def _emit_user_turn(self, turn: UserTurnFinal) -> None:
        self.stats.user_turns_finalized += 1
        await put_packet(
            self.queues.turn_event,
            self._packet("user_turn_final", {"event": turn}, turn_id=turn.turn_id),
            BackpressurePolicy.DROP_OLDEST,
        )

    async def _llm_loop(self) -> None:
        while True:
            packet = await self.queues.turn_event.get()
            if packet.eos:
                await put_packet(
                    self.queues.tts_request,
                    AgentPacket.eos_packet(self.call_id),
                    BackpressurePolicy.DROP_OLDEST,
                )
                self.queues.turn_event.task_done()
                break

            turn = packet.data["event"]
            if not isinstance(turn, UserTurnFinal):
                raise TypeError("turn_event packet must contain a UserTurnFinal.")

            self.state = CallState.THINKING
            sequence_id = self.sequence_manager.create_sequence()
            response_id = f"{self.call_id}-response-{sequence_id}"
            message_id = f"{self.call_id}-message-{sequence_id}"
            await self.output_gate.set_send()
            self.interruption_manager.track_response(sequence_id, response_id, message_id)
            self.stats.llm_responses_started += 1
            tokens = [
                token
                async for token in self.providers.llm.stream_response(
                    call_id=self.call_id,
                    messages=[{"role": "user", "content": turn.text}],
                    response_id=response_id,
                )
            ]
            text = "".join(tokens).strip()
            await put_packet(
                self.queues.tts_request,
                self._packet(
                    "llm_sentence",
                    {
                        "text": text,
                        "message_id": message_id,
                    },
                    turn_id=turn.turn_id,
                    sequence_id=sequence_id,
                    request_id=response_id,
                ),
                BackpressurePolicy.DROP_OLDEST,
            )
            self.queues.turn_event.task_done()

    async def _tts_loop(self) -> None:
        while True:
            packet = await self.queues.tts_request.get()
            if packet.eos:
                await self.providers.tts.stop()
                await put_packet(
                    self.queues.tts_audio,
                    AgentPacket.eos_packet(self.call_id),
                    BackpressurePolicy.DROP_OLDEST,
                )
                self.queues.tts_request.task_done()
                break

            self.state = CallState.SPEAKING
            text = str(packet.data["text"])
            message_id = str(packet.data["message_id"])
            sequence_id = packet.sequence_id or 0
            async for frame in self.providers.tts.synthesize(text, message_id, sequence_id):
                self.stats.tts_chunks_created += 1
                await put_packet(
                    self.queues.tts_audio,
                    self._packet(
                        "tts_audio_chunk",
                        {"frame": frame},
                        turn_id=packet.turn_id,
                        sequence_id=sequence_id,
                        request_id=packet.request_id,
                    ),
                    BackpressurePolicy.DROP_OLDEST,
                )
            self.queues.tts_request.task_done()

    async def _output_loop(self) -> None:
        while True:
            packet = await self.queues.tts_audio.get()
            if packet.eos:
                await self.providers.telephony.stop("normal_eos")
                await self._send_eos_to_idle_queues()
                self.queues.tts_audio.task_done()
                break

            frame = packet.data["frame"]
            if not isinstance(frame, AudioFrame):
                raise TypeError("tts_audio packet must contain an AudioFrame.")
            if not self.sequence_manager.is_valid(packet.sequence_id):
                self.stats.stale_audio_chunks_dropped += 1
                self.queues.tts_audio.task_done()
                continue

            decision = self.output_gate.decision_for(packet.sequence_id)
            if decision == OutputDecision.WAIT:
                decision = await self.output_gate.wait_until_released(
                    self.settings.output_gate_wait_timeout_ms / 1000
                )
            if decision == OutputDecision.DROP:
                self.stats.blocked_audio_chunks_dropped += 1
                self.queues.tts_audio.task_done()
                continue
            if decision == OutputDecision.WAIT:
                self.stats.waited_audio_chunks_dropped += 1
                self.queues.tts_audio.task_done()
                continue

            await self.providers.telephony.send_audio(frame)
            self.interruption_manager.mark_agent_audio_sent(packet.sequence_id)
            self.stats.audio_chunks_sent += 1
            self.queues.tts_audio.task_done()

    async def invalidate_pending_output(self, reason: str) -> set[int]:
        invalidated = self.sequence_manager.invalidate_pending(reason)
        await self.output_gate.block_sequences(invalidated)
        return invalidated

    async def _interruption_manager_loop(self) -> None:
        while True:
            packet = await self.queues.interruption_event.get()
            if packet.eos:
                self.queues.interruption_event.task_done()
                break

            event = packet.data.get("event")
            if isinstance(event, SpeechStart):
                decision = await self.interruption_manager.handle_speech_start(event)
            elif isinstance(event, TranscriptEvent):
                decision = await self.interruption_manager.handle_transcript(event)
            else:
                self.queues.interruption_event.task_done()
                continue

            if decision.outcome == InterruptionOutcome.CANDIDATE:
                self.stats.interruption_candidates_started += 1
            elif decision.outcome == InterruptionOutcome.CONFIRMED:
                self.stats.interruptions_confirmed += 1
                self.state = CallState.INTERRUPTED
                if isinstance(decision.event, InterruptionStarted):
                    await put_packet(
                        self.queues.metrics,
                        self._packet("interruption_started", {"event": decision.event}),
                        BackpressurePolicy.DROP_METRICS,
                    )
            elif decision.outcome == InterruptionOutcome.REJECTED:
                self.stats.interruptions_rejected += 1
                if isinstance(decision.event, InterruptionRejected):
                    await put_packet(
                        self.queues.metrics,
                        self._packet("interruption_rejected", {"event": decision.event}),
                        BackpressurePolicy.DROP_METRICS,
                    )
            self.queues.interruption_event.task_done()

    async def _playback_loop(self) -> None:
        async for event in self.providers.telephony.playback_events():
            self.stats.playback_events_received += 1
            await put_packet(
                self.queues.playback_event,
                self._packet("playback_event", {"event": event}, sequence_id=event.sequence_id),
                BackpressurePolicy.DROP_OLDEST,
            )

    async def _metrics_loop(self) -> None:
        await self._drain_loop(self.queues.metrics)

    async def _error_loop(self) -> None:
        while True:
            packet = await self.queues.error.get()
            if packet.eos:
                self.queues.error.task_done()
                break

            error = packet.data.get("error")
            if isinstance(error, ProviderError):
                self.errors.append(error)
            self.queues.error.task_done()

    async def _drain_loop(self, queue: asyncio.Queue[AgentPacket]) -> None:
        while True:
            packet = await queue.get()
            queue.task_done()
            if packet.eos:
                break

    def _packet(
        self,
        packet_type: str,
        data: dict[str, Any],
        *,
        turn_id: int | None = None,
        sequence_id: int | None = None,
        request_id: str | None = None,
    ) -> AgentPacket:
        return AgentPacket(
            packet_type=packet_type,
            call_id=self.call_id,
            turn_id=turn_id,
            sequence_id=sequence_id,
            request_id=request_id,
            timestamp_ms=now_ms(),
            data=data,
        )

    async def _emit_error(self, error: ProviderError) -> None:
        await put_packet(
            self.queues.error,
            self._packet("error", {"error": error}),
            BackpressurePolicy.DROP_OLDEST,
        )

    async def _send_eos_to_all_queues(self) -> None:
        await broadcast_eos(self.queues.all_queues(), self.call_id)

    async def _send_eos_to_idle_queues(self) -> None:
        await broadcast_eos(
            (
                self.queues.interruption_event,
                self.queues.metrics,
                self.queues.error,
            ),
            self.call_id,
        )

    async def _stop_providers(self, reason: str) -> None:
        await self.providers.llm.stop()
        await self.providers.tts.stop()
        await self.providers.stt.stop()
        await self.providers.telephony.stop(reason)

    async def _save_live_state(self) -> None:
        if self.providers.live_store is None:
            return
        await self.providers.live_store.set_call_state(
            self.call_id,
            {"state": self.state.value, "stats": asdict(self.stats)},
        )

    async def _finalize_closed(self, reason: str = "closed") -> None:
        if self.state == CallState.CLOSED:
            return
        self.state = CallState.CLOSED
        if self.providers.final_store is not None:
            await self.providers.final_store.save_call(
                self.call_id,
                {
                    "call_id": self.call_id,
                    "reason": reason,
                    "state": self.state.value,
                    "stats": asdict(self.stats),
                    "errors": [error.message for error in self.errors],
                },
            )
        if self.providers.live_store is not None:
            await self.providers.live_store.delete_call_state(self.call_id)
