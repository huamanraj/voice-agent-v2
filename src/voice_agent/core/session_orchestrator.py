"""Provider-neutral session orchestration skeleton."""

import asyncio
from dataclasses import asdict, dataclass, field
from collections.abc import AsyncIterator, Awaitable, Callable
from pathlib import Path
from typing import Any

from voice_agent.agents import AgentProfile
from voice_agent.audio.audio_router import AudioRouter
from voice_agent.audio.rolling_buffer import RollingAudioBuffer
from voice_agent.config import Settings, get_settings
from voice_agent.contracts.audio import AudioFrame
from voice_agent.contracts.events import (
    InterruptionRejected,
    InterruptionStarted,
    PlaybackEvent,
    ProviderError,
    SmartTurnResult,
    SpeechStart,
    SpeechStop,
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
from voice_agent.core.interruption.output_gate import OutputDecision, OutputGate, OutputGateState
from voice_agent.core.interruption.interruption_manager import (
    InterruptionManager,
    InterruptionOutcome,
)
from voice_agent.core.interruption.sequence_manager import SequenceManager
from voice_agent.core.context.context_manager import ContextManager
from voice_agent.core.metrics.latency_tracker import LatencyTracker
from voice_agent.core.observability.call_logger import AsyncCallLogger
from voice_agent.core.playback.playback_tracker import PlaybackTracker
from voice_agent.core.response.sentence_aggregator import aggregate_token_stream
from voice_agent.core.state_machine import CallState
from voice_agent.core.turn_detection.local_models import TurnDetectionModels
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
    stale_tts_requests_dropped: int = 0
    pending_tts_requests_purged: int = 0
    pending_tts_audio_purged: int = 0
    llm_tokens_received: int = 0
    llm_sentences_created: int = 0
    llm_first_token_latency_ms: int | None = None
    interruption_candidates_started: int = 0
    interruptions_confirmed: int = 0
    interruptions_rejected: int = 0
    errors: int = 0


@dataclass(slots=True)
class SessionOrchestrator:
    call_id: str
    providers: SessionProviders
    settings: Settings | None = None
    agent: AgentProfile | None = None
    turn_detection_models: TurnDetectionModels | None = None
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
    playback_tracker: PlaybackTracker = field(init=False)
    context_manager: ContextManager = field(init=False)
    latency_tracker: LatencyTracker = field(init=False)
    call_logger: AsyncCallLogger = field(init=False)
    _shutdown_started: bool = field(init=False)
    _active_llm_task: asyncio.Task[None] | None = field(init=False)
    _active_llm_response_id: str | None = field(init=False)
    _active_llm_sequence_id: int | None = field(init=False)
    _turn_check_task: asyncio.Task[None] | None = field(init=False)
    _interruption_cleanup_done: asyncio.Event = field(init=False)
    _vad_stream: Any | None = field(init=False)
    _session_started_ms: int = field(init=False)
    _session_ended_ms: int | None = field(init=False)
    _first_media_frame_seen: bool = field(init=False)
    final_record: dict[str, Any] | None = field(init=False)

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
        self.playback_tracker = PlaybackTracker(call_id=self.call_id)
        self.context_manager = ContextManager(system_prompt=self.settings.llm_system_prompt)
        self.latency_tracker = LatencyTracker()
        self.call_logger = AsyncCallLogger(
            call_id=self.call_id,
            log_dir=Path(self.settings.log_dir),
            queue_maxsize=self.settings.call_log_queue_max,
        )
        self.interruption_manager = InterruptionManager(
            call_id=self.call_id,
            settings=self.settings,
            output_gate=self.output_gate,
            sequence_manager=self.sequence_manager,
            telephony=self.providers.telephony,
            tts=self.providers.tts,
            llm=self.providers.llm,
            on_confirmed=self._handle_confirmed_interruption,
        )
        self.turn_manager = TurnManager(self.call_id, self.settings)
        self._vad_stream = (
            self.turn_detection_models.vad.create_stream(self.call_id, self.settings)
            if self.turn_detection_models is not None
            and self.turn_detection_models.vad is not None
            and self.settings.vad_enabled
            else None
        )
        self._shutdown_started = False
        self._active_llm_task = None
        self._active_llm_response_id = None
        self._active_llm_sequence_id = None
        self._turn_check_task = None
        self._interruption_cleanup_done = asyncio.Event()
        self._interruption_cleanup_done.set()
        self._session_started_ms = now_ms()
        self._session_ended_ms = None
        self._first_media_frame_seen = False
        self.final_record = None

    async def start(self) -> None:
        if self.state != CallState.NEW:
            raise RuntimeError(f"Session {self.call_id} already started in state {self.state}.")

        self._shutdown_started = False
        self._session_started_ms = now_ms()
        self.call_logger.start()
        self._log("call_started")
        self.state = CallState.STARTING
        await self._save_live_state()
        await self.providers.telephony.start()
        self._log("provider_connected", provider=self.providers.telephony.provider_name)
        await self.providers.stt.start(self.call_id, language_hint=self.settings.deepgram_language)
        self._log("provider_connected", provider=self.providers.stt.provider_name)
        await self.providers.tts.start(
            self.call_id,
            voice=self.settings.agent_tts_voice,
            language=self.settings.agent_tts_language or self.settings.agent_default_language,
        )
        self._log("provider_connected", provider=self.providers.tts.provider_name)
        self._log(
            "turn_detection_models",
            vad="ready" if self._vad_stream is not None else "unavailable",
            smart_turn=(
                "ready"
                if self.turn_detection_models is not None
                and self.turn_detection_models.smart_turn is not None
                else "unavailable"
            ),
        )

        self.tasks = {
            "receive_audio_loop": self._create_task("receive_audio_loop", self._receive_audio_loop),
            "stt_sender_loop": self._create_task("stt_sender_loop", self._stt_sender_loop),
            "stt_receiver_loop": self._create_task("stt_receiver_loop", self._stt_receiver_loop),
            "stt_speech_loop": self._create_task("stt_speech_loop", self._stt_speech_loop),
            "vad_processor_loop": self._create_task(
                "vad_processor_loop",
                (
                    self._vad_processor_loop
                    if self._vad_stream is not None
                    else lambda: self._drain_loop(self.queues.vad_audio)
                ),
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
        self._log("call_listening")
        await self._save_live_state()
        await self._enqueue_agent_greeting()

    async def run(self) -> SessionStats:
        await self.start()
        await self.wait_closed()
        return self.stats

    async def _enqueue_agent_greeting(self) -> None:
        greeting = (self.settings.agent_greeting or "").strip()
        if not greeting:
            return

        sequence_id = self.sequence_manager.create_sequence()
        message_id = f"{self.call_id}-greeting-{sequence_id}"
        response_id = f"{self.call_id}-greeting-response-{sequence_id}"
        self.playback_tracker.start_message(message_id=message_id, sequence_id=sequence_id)
        self.playback_tracker.append_generated_text(message_id, greeting)
        self.context_manager.start_assistant_turn(message_id=message_id, sequence_id=sequence_id)
        self.context_manager.append_assistant_text(message_id, greeting)
        if self.settings.allow_interrupt_welcome_message:
            self.interruption_manager.track_response(sequence_id, response_id, message_id)
        self._log(
            "agent_greeting_started",
            sequence_id=sequence_id,
            message_id=message_id,
            text_length=len(greeting),
        )
        await put_packet(
            self.queues.tts_request,
            self._packet(
                "llm_sentence",
                {"text": greeting, "message_id": message_id},
                sequence_id=sequence_id,
                request_id=response_id,
            ),
            BackpressurePolicy.DROP_OLDEST,
        )
        await put_packet(
            self.queues.tts_request,
            self._packet(
                "llm_response_end",
                {"message_id": message_id},
                sequence_id=sequence_id,
                request_id=response_id,
            ),
            BackpressurePolicy.DROP_OLDEST,
        )

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
        self._cancel_turn_check()
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
            if not self._first_media_frame_seen:
                self._first_media_frame_seen = True
                self._log(
                    "media_first_frame",
                    sequence_id=frame.sequence_id,
                    provider=self.providers.telephony.provider_name,
                    codec=frame.codec,
                    sample_rate=frame.sample_rate,
                )
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
            self.latency_tracker.mark_transcript(None, now_ms(), is_final=transcript.is_final)
            self._log(
                "final_transcript" if transcript.is_final else "interim_transcript",
                provider=transcript.provider,
                confidence=transcript.confidence,
                language=transcript.language,
                text=transcript.text if self.settings.log_full_transcripts else None,
            )
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

    async def _stt_speech_loop(self) -> None:
        async for speech_event in self.providers.stt.speech_events():
            if self._vad_stream is not None:
                self._log(
                    "provider_speech_event_ignored",
                    provider=speech_event.source,
                    reason="local_silero_vad_active",
                )
                continue
            await self._handle_speech_event(speech_event, run_smart_turn=False)

        await put_packet(
            self.queues.speech_event,
            AgentPacket.eos_packet(self.call_id),
            BackpressurePolicy.DROP_OLDEST,
        )

    async def _vad_processor_loop(self) -> None:
        if self._vad_stream is None:
            await self._drain_loop(self.queues.vad_audio)
            return

        while True:
            packet = await self.queues.vad_audio.get()
            if packet.eos:
                stop_event = self._vad_stream.flush()
                if stop_event is not None:
                    await self._handle_speech_event(stop_event, run_smart_turn=True)
                self.queues.vad_audio.task_done()
                break

            frame = packet.data["frame"]
            if not isinstance(frame, AudioFrame):
                raise TypeError("vad_audio packet must contain an AudioFrame.")

            events = self._vad_stream.process_frame(frame)
            for event in events:
                await self._handle_speech_event(event, run_smart_turn=True)
            self.queues.vad_audio.task_done()

    async def _handle_speech_event(
        self,
        speech_event: SpeechStart | SpeechStop,
        *,
        run_smart_turn: bool,
    ) -> None:
        if isinstance(speech_event, SpeechStart):
            self._cancel_turn_check()
            self.latency_tracker.mark_speech_start(None, speech_event.ts_ms)
            self._log(
                "speech_start",
                provider=speech_event.source,
                confidence=speech_event.confidence,
            )
        else:
            self.latency_tracker.mark_speech_stop(None, speech_event.ts_ms)
            self._log(
                "speech_stop",
                provider=speech_event.source,
                confidence=speech_event.confidence,
            )

        packet = self._packet("speech_event", {"event": speech_event})
        await put_packet(self.queues.speech_event, packet, BackpressurePolicy.DROP_OLDEST)
        await put_packet(
            self.queues.interruption_event,
            packet,
            BackpressurePolicy.DROP_OLDEST,
        )

        if isinstance(speech_event, SpeechStart):
            self.turn_manager.handle_speech_start(speech_event)
            return

        self.turn_manager.handle_speech_stop(speech_event)
        if run_smart_turn:
            await self._run_smart_turn_for_current_turn()
        await self._emit_turn_if_ready()

    async def _run_smart_turn_for_current_turn(self) -> None:
        if (
            not self.settings.smart_turn_enabled
            or self.turn_detection_models is None
            or self.turn_detection_models.smart_turn is None
        ):
            return

        turn_audio = self.rolling_audio_buffer.frame_since(self.turn_manager.state.user_started_ms)
        if not turn_audio.data:
            return

        started_ms = now_ms()
        decision = await asyncio.to_thread(self.turn_detection_models.smart_turn.classify, turn_audio)
        result = SmartTurnResult(
            call_id=self.call_id,
            turn_id=self.turn_manager.state.turn_id + 1,
            is_complete=decision.is_complete,
            confidence=decision.confidence,
            reason=decision.reason,
        )
        self.turn_manager.handle_smart_turn(result)
        self._log(
            "smart_turn_result",
            turn_id=result.turn_id,
            confidence=result.confidence,
            is_complete=result.is_complete,
            reason=result.reason,
            latency_ms=now_ms() - started_ms,
            audio_duration_ms=turn_audio.duration_ms,
        )
        await put_packet(
            self.queues.metrics,
            self._packet("smart_turn_result", {"event": result}, turn_id=result.turn_id),
            BackpressurePolicy.DROP_METRICS,
        )

    async def _turn_manager_loop(self) -> None:
        while True:
            packet = await self.queues.transcript_event.get()
            if packet.eos:
                self._cancel_turn_check()
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

            if self._vad_stream is not None and self.turn_manager.state.user_started_ms is None:
                self._log(
                    "late_transcript_ignored",
                    provider=transcript.provider,
                    text=transcript.text if self.settings.log_full_transcripts else None,
                )
                self.queues.transcript_event.task_done()
                continue

            self.turn_manager.handle_transcript(transcript, received_ms=packet.timestamp_ms)
            await self._emit_turn_if_ready()
            self.queues.transcript_event.task_done()

    async def _emit_turn_if_ready(self) -> None:
        turn = self.turn_manager.emit_turn(now_ms())
        if turn is not None:
            await self._emit_user_turn(turn)
            return
        self._schedule_turn_check()

    def _schedule_turn_check(self) -> None:
        delay_ms = self._next_turn_check_delay_ms()
        if delay_ms is None:
            return
        self._cancel_turn_check()
        self._turn_check_task = asyncio.create_task(
            self._delayed_turn_check(delay_ms),
            name=f"{self.call_id}:turn_check",
        )

    def _cancel_turn_check(self) -> None:
        task = self._turn_check_task
        self._turn_check_task = None
        if task is not None and not task.done():
            task.cancel()

    async def _delayed_turn_check(self, delay_ms: int) -> None:
        try:
            await asyncio.sleep(delay_ms / 1000)
            if self._turn_check_task is asyncio.current_task():
                self._turn_check_task = None
            await self._emit_turn_if_ready()
        except asyncio.CancelledError:
            raise

    def _next_turn_check_delay_ms(self) -> int | None:
        state = self.turn_manager.state
        if state.emitted_turn or state.is_user_speaking or state.user_started_ms is None:
            return None
        if not state.text:
            return None

        ts_ms = now_ms()
        decision = self.turn_manager.evaluate(ts_ms)
        if decision.should_emit:
            return 0

        speech_duration_ms = max(0, (state.last_speech_ms or ts_ms) - state.user_started_ms)
        if decision.reason == "speech_too_short":
            return max(1, self.settings.min_user_speech_ms - speech_duration_ms)

        silence_start_ms = state.last_speech_ms or state.last_transcript_ms or ts_ms
        silence_ms = max(0, ts_ms - silence_start_ms)
        if decision.reason == "not_enough_silence":
            return max(1, self.settings.min_silence_for_turn_end_ms - silence_ms)
        if decision.reason == "waiting_for_final_transcript":
            transcript_age_ms = max(0, ts_ms - (state.last_transcript_ms or ts_ms))
            return max(1, self.settings.max_silence_before_force_end_ms - transcript_age_ms)
        if decision.reason in {"smart_turn_incomplete", "incomplete_connector"}:
            return max(1, self.settings.max_silence_before_force_end_ms - silence_ms)
        return None

    async def _emit_user_turn(self, turn: UserTurnFinal) -> None:
        self._cancel_turn_check()
        self.stats.user_turns_finalized += 1
        if self.interruption_manager.state.agent_is_speaking and self.settings.interruption_enabled:
            await self.output_gate.set_wait()
            self._log("turn_waiting_for_interruption_decision", turn_id=turn.turn_id)
        self.latency_tracker.mark_end_of_turn(turn.turn_id, now_ms())
        self._log(
            "user_turn_final",
            turn_id=turn.turn_id,
            confidence=turn.confidence,
            language=turn.language,
            text=turn.text if self.settings.log_full_transcripts else None,
        )
        await self._save_live_state()
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

            self._active_llm_task = asyncio.create_task(
                self._run_llm_response(turn),
                name=f"{self.call_id}:llm_response:{turn.turn_id}",
            )
            try:
                await self._active_llm_task
            except asyncio.CancelledError:
                if self._shutdown_started:
                    raise
            finally:
                self._active_llm_task = None
                self._active_llm_response_id = None
                self._active_llm_sequence_id = None
                self.queues.turn_event.task_done()

    async def _run_llm_response(self, turn: UserTurnFinal) -> None:
        await self._wait_for_output_resume(turn.turn_id)
        await self._invalidate_prior_output_for_new_turn(turn.turn_id)
        self.state = CallState.THINKING
        sequence_id = self.sequence_manager.create_sequence()
        response_id = f"{self.call_id}-response-{sequence_id}"
        message_id = f"{self.call_id}-message-{sequence_id}"
        self._active_llm_response_id = response_id
        self._active_llm_sequence_id = sequence_id
        self.context_manager.append_user_turn(turn)
        self.playback_tracker.start_message(message_id=message_id, sequence_id=sequence_id)
        self.context_manager.start_assistant_turn(message_id=message_id, sequence_id=sequence_id)
        await self.output_gate.set_send()
        self.interruption_manager.track_response(sequence_id, response_id, message_id)
        self.stats.llm_responses_started += 1
        started_ms = now_ms()
        self.latency_tracker.mark_llm_start(turn.turn_id, started_ms)
        self._log(
            "agent_response_started",
            turn_id=turn.turn_id,
            sequence_id=sequence_id,
            message_id=message_id,
            response_id=response_id,
        )
        self._log("llm_start", turn_id=turn.turn_id, sequence_id=sequence_id, provider=self.providers.llm.provider_name)
        await self._save_live_state()
        first_token_seen = False
        token_stream = self.providers.llm.stream_response(
            call_id=self.call_id,
            messages=self._llm_messages_for_turn(turn),
            response_id=response_id,
        )
        tracked_stream = self._tracked_llm_tokens(
            token_stream,
            started_ms,
            first_token_seen,
            turn_id=turn.turn_id,
            sequence_id=sequence_id,
        )
        try:
            async for text in aggregate_token_stream(
                tracked_stream,
                min_chars=self.settings.llm_sentence_min_chars,
                max_chars=self.settings.llm_sentence_max_chars,
                timeout_ms=self.settings.llm_sentence_timeout_ms,
            ):
                if not self.sequence_manager.is_valid(sequence_id):
                    await self.providers.llm.cancel(response_id)
                    break
                self.stats.llm_sentences_created += 1
                self.playback_tracker.append_generated_text(message_id, text)
                self.context_manager.append_assistant_text(message_id, text)
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
            if self.sequence_manager.is_valid(sequence_id):
                await put_packet(
                    self.queues.tts_request,
                    self._packet(
                        "llm_response_end",
                        {"message_id": message_id},
                        turn_id=turn.turn_id,
                        sequence_id=sequence_id,
                        request_id=response_id,
                    ),
                    BackpressurePolicy.DROP_OLDEST,
                )
            self.latency_tracker.mark_llm_end(turn.turn_id, now_ms())
            self._log("llm_end", turn_id=turn.turn_id, sequence_id=sequence_id, provider=self.providers.llm.provider_name)
        except asyncio.CancelledError:
            await self.providers.llm.cancel(response_id)
            self._log("llm_cancel_sent", turn_id=turn.turn_id, sequence_id=sequence_id, provider=self.providers.llm.provider_name)
            raise

    async def _wait_for_output_resume(self, turn_id: int) -> None:
        timeout_seconds = max(
            0.1,
            (
                self.settings.hard_interrupt_after_audio_ms
                + self.settings.output_gate_wait_timeout_ms
                + 1000
            )
            / 1000,
        )
        started = asyncio.get_running_loop().time()
        while (
            not self._interruption_cleanup_done.is_set()
            or self.output_gate.state != OutputGateState.SEND
            or self.interruption_manager.state.user_may_be_interrupting
        ):
            if asyncio.get_running_loop().time() - started >= timeout_seconds:
                self._log("interruption_resume_wait_timeout", turn_id=turn_id)
                break
            await asyncio.sleep(0.01)

    async def _invalidate_prior_output_for_new_turn(self, turn_id: int) -> None:
        invalidated = self.sequence_manager.invalidate_pending("new_user_turn")
        if not invalidated:
            return
        await self.output_gate.block_sequences(invalidated)
        self.stats.pending_tts_requests_purged += self._purge_invalid_packets(self.queues.tts_request)
        self.stats.pending_tts_audio_purged += self._purge_invalid_packets(self.queues.tts_audio)
        active_response = self.interruption_manager.active_response
        if active_response is not None and active_response.sequence_id in invalidated:
            await self.providers.tts.cancel(active_response.message_id, "new_user_turn")
            await self.providers.llm.cancel(active_response.response_id)
            self.interruption_manager.mark_agent_response_finished(active_response.sequence_id)
            self._log(
                "active_response_cancelled_for_new_turn",
                turn_id=turn_id,
                sequence_id=active_response.sequence_id,
                message_id=active_response.message_id,
            )
        self._log(
            "pending_output_invalidated_for_new_turn",
            turn_id=turn_id,
            sequence_id=max(invalidated),
            invalidated_count=len(invalidated),
        )

    async def _tracked_llm_tokens(
        self,
        token_stream: AsyncIterator[str],
        started_ms: int,
        first_token_seen: bool,
        *,
        turn_id: int | None = None,
        sequence_id: int | None = None,
    ) -> AsyncIterator[str]:
        async for token in token_stream:
            if not token:
                continue
            self.stats.llm_tokens_received += 1
            if not first_token_seen:
                token_ms = now_ms()
                self.stats.llm_first_token_latency_ms = token_ms - started_ms
                self.latency_tracker.mark_llm_first_token(turn_id, token_ms)
                self._log("llm_first_token", turn_id=turn_id, sequence_id=sequence_id, provider=self.providers.llm.provider_name)
                first_token_seen = True
            yield token

    def _llm_messages_for_turn(self, turn: UserTurnFinal) -> list[dict[str, Any]]:
        return self.context_manager.build_llm_messages(current_user_turn=turn)

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

            if packet.packet_type == "llm_response_end":
                sequence_id = packet.sequence_id or 0
                if not self.sequence_manager.is_valid(sequence_id):
                    self.stats.stale_tts_requests_dropped += 1
                    self.latency_tracker.mark_audio_drop()
                    self._log("old_audio_chunk_dropped", turn_id=packet.turn_id, sequence_id=sequence_id, packet_type=packet.packet_type)
                    self.queues.tts_request.task_done()
                    continue
                await put_packet(
                    self.queues.tts_audio,
                    self._packet(
                        "tts_response_end",
                        {"message_id": str(packet.data["message_id"])},
                        turn_id=packet.turn_id,
                        sequence_id=sequence_id,
                        request_id=packet.request_id,
                    ),
                    BackpressurePolicy.DROP_OLDEST,
                )
                self.queues.tts_request.task_done()
                continue

            self.state = CallState.SPEAKING
            text = str(packet.data["text"])
            message_id = str(packet.data["message_id"])
            sequence_id = packet.sequence_id or 0
            if not self.sequence_manager.is_valid(sequence_id):
                self.stats.stale_tts_requests_dropped += 1
                self.latency_tracker.mark_audio_drop()
                self._log("old_audio_chunk_dropped", turn_id=packet.turn_id, sequence_id=sequence_id, packet_type=packet.packet_type)
                self.queues.tts_request.task_done()
                continue

            self.playback_tracker.mark_text_sent_to_tts(message_id, text)
            self.latency_tracker.mark_tts_start(packet.turn_id, now_ms())
            self._log(
                "tts_start",
                turn_id=packet.turn_id,
                sequence_id=sequence_id,
                message_id=message_id,
                provider=self.providers.tts.provider_name,
                text_length=len(text),
            )
            first_audio_seen = False
            async for frame in self.providers.tts.synthesize(text, message_id, sequence_id):
                if not self.sequence_manager.is_valid(sequence_id):
                    self.stats.stale_audio_chunks_dropped += 1
                    self.latency_tracker.mark_audio_drop()
                    self._log("old_audio_chunk_dropped", turn_id=packet.turn_id, sequence_id=sequence_id, message_id=message_id)
                    await self.providers.tts.cancel(message_id, "sequence_invalidated")
                    self._log("tts_cancel_sent", turn_id=packet.turn_id, sequence_id=sequence_id, message_id=message_id)
                    break
                if not first_audio_seen:
                    first_audio_seen = True
                    self.latency_tracker.mark_tts_first_audio(packet.turn_id, now_ms())
                    self._log(
                        "tts_first_audio",
                        turn_id=packet.turn_id,
                        sequence_id=sequence_id,
                        message_id=message_id,
                        provider=self.providers.tts.provider_name,
                    )
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
            self.latency_tracker.mark_tts_end(packet.turn_id, now_ms())
            self._log("tts_end", turn_id=packet.turn_id, sequence_id=sequence_id, message_id=message_id)
            self.queues.tts_request.task_done()

    async def _output_loop(self) -> None:
        while True:
            packet = await self.queues.tts_audio.get()
            if packet.eos:
                await self.providers.telephony.stop("normal_eos")
                await self._send_eos_to_idle_queues()
                self.queues.tts_audio.task_done()
                break

            if packet.packet_type == "tts_response_end":
                if not self.sequence_manager.is_valid(packet.sequence_id):
                    self.stats.stale_audio_chunks_dropped += 1
                    self.latency_tracker.mark_audio_drop()
                    self._log("old_audio_chunk_dropped", turn_id=packet.turn_id, sequence_id=packet.sequence_id, packet_type=packet.packet_type)
                    self.queues.tts_audio.task_done()
                    continue
                message_id = str(packet.data["message_id"])
                await self.providers.telephony.send_checkpoint(message_id)
                self.playback_tracker.mark_checkpoint_sent(message_id, message_id)
                self._log("checkpoint_sent", turn_id=packet.turn_id, sequence_id=packet.sequence_id, message_id=message_id)
                self.queues.tts_audio.task_done()
                continue

            frame = packet.data["frame"]
            if not isinstance(frame, AudioFrame):
                raise TypeError("tts_audio packet must contain an AudioFrame.")
            if not self.sequence_manager.is_valid(packet.sequence_id):
                self.stats.stale_audio_chunks_dropped += 1
                self.latency_tracker.mark_audio_drop()
                self._log("old_audio_chunk_dropped", turn_id=packet.turn_id, sequence_id=packet.sequence_id)
                self.queues.tts_audio.task_done()
                continue

            decision = self.output_gate.decision_for(packet.sequence_id)
            if decision == OutputDecision.WAIT:
                decision = await self.output_gate.wait_until_released(
                    self.settings.output_gate_wait_timeout_ms / 1000
                )
            if decision == OutputDecision.DROP:
                self.stats.blocked_audio_chunks_dropped += 1
                self.latency_tracker.mark_audio_drop()
                self.queues.tts_audio.task_done()
                continue
            if decision == OutputDecision.WAIT:
                self.stats.waited_audio_chunks_dropped += 1
                self.latency_tracker.mark_audio_drop()
                self.queues.tts_audio.task_done()
                continue

            await self.providers.telephony.send_audio(frame)
            self.playback_tracker.mark_audio_sent(frame, timestamp_ms=now_ms())
            self.latency_tracker.mark_first_audio_sent(packet.turn_id, now_ms())
            self.interruption_manager.mark_agent_audio_sent(packet.sequence_id)
            self.stats.audio_chunks_sent += 1
            self._log(
                "play_audio_sent",
                turn_id=packet.turn_id,
                sequence_id=packet.sequence_id,
                message_id=str(frame.meta.get("message_id", "")) or None,
                provider=self.providers.telephony.provider_name,
                duration_ms=frame.duration_ms,
            )
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
            elif isinstance(event, SpeechStop):
                decision = await self.interruption_manager.handle_speech_stop(event)
            elif isinstance(event, TranscriptEvent):
                decision = await self.interruption_manager.handle_transcript(event)
            else:
                self.queues.interruption_event.task_done()
                continue

            if decision.outcome == InterruptionOutcome.CANDIDATE:
                self.stats.interruption_candidates_started += 1
                self._log("interruption_candidate_started")
            elif decision.outcome == InterruptionOutcome.CONFIRMED:
                self.stats.interruptions_confirmed += 1
                self.state = CallState.INTERRUPTED
                if isinstance(decision.event, InterruptionStarted):
                    self.latency_tracker.mark_interruption(decision.event.turn_id, decision.event.ts_ms)
                    self._log(
                        "interruption_confirmed",
                        sequence_id=decision.event.sequence_id,
                        reason=decision.event.reason,
                        transcript=decision.event.transcript if self.settings.log_full_transcripts else None,
                    )
                    await put_packet(
                        self.queues.metrics,
                        self._packet("interruption_started", {"event": decision.event}),
                        BackpressurePolicy.DROP_METRICS,
                    )
                self._interruption_cleanup_done.set()
                await self.output_gate.set_send()
            elif decision.outcome == InterruptionOutcome.REJECTED:
                self.stats.interruptions_rejected += 1
                if isinstance(decision.event, InterruptionRejected):
                    self._log(
                        "interruption_rejected",
                        sequence_id=decision.event.sequence_id,
                        reason=decision.event.reason,
                    )
                    await put_packet(
                        self.queues.metrics,
                        self._packet("interruption_rejected", {"event": decision.event}),
                        BackpressurePolicy.DROP_METRICS,
                    )
                self._interruption_cleanup_done.set()
            self.queues.interruption_event.task_done()

    async def _handle_confirmed_interruption(self, event: InterruptionStarted) -> None:
        self._interruption_cleanup_done.clear()
        self.stats.pending_tts_requests_purged += self._purge_invalid_packets(self.queues.tts_request)
        self.stats.pending_tts_audio_purged += self._purge_invalid_packets(self.queues.tts_audio)
        playback = self.playback_tracker.mark_interrupted(event)
        if playback is not None:
            self.context_manager.update_assistant_from_playback(playback)
        if self.settings.clear_audio_on_confirmed_interrupt:
            self.latency_tracker.mark_clear_sent(event.turn_id, now_ms())
            self._log("clear_playback_sent", sequence_id=event.sequence_id, reason=event.reason)

        active_task = self._active_llm_task
        if (
            active_task is not None
            and not active_task.done()
            and self._active_llm_sequence_id == event.sequence_id
        ):
            active_task.cancel()

    def _purge_invalid_packets(self, queue: asyncio.Queue[AgentPacket]) -> int:
        retained: list[AgentPacket] = []
        dropped = 0
        while True:
            try:
                packet = queue.get_nowait()
            except asyncio.QueueEmpty:
                break

            queue.task_done()
            if packet.eos or self.sequence_manager.is_valid(packet.sequence_id):
                retained.append(packet)
            else:
                dropped += 1
                self.latency_tracker.mark_audio_drop()
                self._log("old_audio_chunk_dropped", sequence_id=packet.sequence_id, packet_type=packet.packet_type)

        for packet in retained:
            queue.put_nowait(packet)
        return dropped

    async def _playback_loop(self) -> None:
        async for event in self.providers.telephony.playback_events():
            self.stats.playback_events_received += 1
            playback = self.playback_tracker.handle_playback_event(event)
            if playback is not None:
                self.context_manager.update_assistant_from_playback(playback)
            if event.event_type == "started":
                self.latency_tracker.mark_first_audio_played(None, event.ts_ms)
            elif event.event_type == "checkpoint_played":
                self.latency_tracker.mark_final_audio_played(None, event.ts_ms)
                if playback is not None:
                    self.interruption_manager.mark_agent_response_finished(playback.sequence_id)
                    self.sequence_manager.retire(playback.sequence_id)
                self._log(
                    "checkpoint_played",
                    sequence_id=event.sequence_id,
                    message_id=event.message_id,
                    checkpoint_id=event.checkpoint_id,
                )
            elif event.event_type == "cleared":
                self.latency_tracker.mark_clear_ack(None, event.ts_ms)
                self._log("clear_playback_ack", sequence_id=event.sequence_id)
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
                self.latency_tracker.mark_provider_error()
                self._log(
                    "provider_error",
                    provider=error.provider,
                    error_type=error.error_type,
                    error_code=error.error_code,
                    retryable=error.retryable,
                )
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
            self._live_state_payload(),
        )

    async def _finalize_closed(self, reason: str = "closed") -> None:
        if self.state == CallState.CLOSED:
            return
        self._cancel_turn_check()
        self.state = CallState.CLOSED
        self._session_ended_ms = now_ms()
        self._log("call_ended", reason=reason, stats=asdict(self.stats))
        self.final_record = self._final_call_record(reason)
        if self.providers.final_store is not None:
            await self.providers.final_store.save_call(
                self.call_id,
                self.final_record,
            )
        if self.providers.live_store is not None:
            await self.providers.live_store.delete_call_state(self.call_id)
        await self.call_logger.stop(self.settings.call_log_flush_timeout_ms / 1000)

    def _log(
        self,
        event_name: str,
        *,
        turn_id: int | None = None,
        sequence_id: int | None = None,
        message_id: str | None = None,
        provider: str | None = None,
        **details: Any,
    ) -> None:
        self.call_logger.emit(
            event_name,
            turn_id=turn_id,
            sequence_id=sequence_id,
            message_id=message_id,
            provider=provider,
            state=self.state.value if hasattr(self, "state") else None,
            **details,
        )

    def _live_state_payload(self) -> dict[str, Any]:
        return {
            "call_id": self.call_id,
            "state": self.state.value,
            "updated_ms": now_ms(),
            "current_sequence_id": self.sequence_manager.current_sequence_id,
            "active_response": {
                "response_id": self._active_llm_response_id,
                "sequence_id": self._active_llm_sequence_id,
            },
            "stats": asdict(self.stats),
            "metrics": self.latency_tracker.summary().as_dict(),
            "turns": self._turn_records(),
            "errors": [asdict(error) for error in self.errors],
        }

    def _final_call_record(self, reason: str) -> dict[str, Any]:
        metrics = self.latency_tracker.summary().as_dict()
        metrics["audio_drop_count"] = (
            self.stats.stale_audio_chunks_dropped
            + self.stats.blocked_audio_chunks_dropped
            + self.stats.waited_audio_chunks_dropped
            + self.stats.pending_tts_requests_purged
            + self.stats.pending_tts_audio_purged
        )
        metrics["provider_error_count"] = len(self.errors)
        metrics["interruption_count"] = self.stats.interruptions_confirmed
        turns = self._turn_records()
        return {
            "call_id": self.call_id,
            "reason": reason,
            "state": self.state.value,
            "started_ms": self._session_started_ms,
            "ended_ms": self._session_ended_ms or now_ms(),
            "stats": asdict(self.stats),
            "metrics": metrics,
            "turns": turns,
            "transcript_summary": self.context_manager.summary_text or _summarize_turns(turns),
            "errors": [error.message for error in self.errors],
            "provider_errors": [asdict(error) for error in self.errors],
            "playback": {
                message_id: asdict(playback)
                for message_id, playback in self.playback_tracker.messages.items()
            },
        }

    def _turn_records(self) -> list[dict[str, Any]]:
        records: list[tuple[int, int, dict[str, Any]]] = []
        for index, user_turn in enumerate(self.context_manager.user_turns):
            records.append(
                (
                    user_turn.timestamp_ms,
                    index,
                    {
                        "speaker": "user",
                        "turn_id": user_turn.turn_id,
                        "text": user_turn.text,
                        "timestamp_ms": user_turn.timestamp_ms,
                        "confidence": user_turn.confidence,
                        "language": user_turn.language,
                    },
                )
            )
        for index, assistant_turn in enumerate(self.context_manager.assistant_turns):
            records.append(
                (
                    assistant_turn.created_ms,
                    index,
                    {
                        "speaker": "assistant",
                        "message_id": assistant_turn.message_id,
                        "sequence_id": assistant_turn.sequence_id,
                        "text": assistant_turn.heard_text,
                        "full_text": assistant_turn.full_text,
                        "heard_text": assistant_turn.heard_text,
                        "interrupted": assistant_turn.interrupted,
                        "created_ms": assistant_turn.created_ms,
                        "fully_played_ms": assistant_turn.fully_played_ms,
                    },
                )
            )
        records.sort(key=lambda item: (item[0], item[1]))
        return [record for _, _, record in records]


def _summarize_turns(turns: list[dict[str, Any]], max_chars: int = 1000) -> str:
    text = "\n".join(
        f"{turn.get('speaker', 'unknown')}: {turn.get('heard_text') or turn.get('text') or ''}".strip()
        for turn in turns
        if turn.get("heard_text") or turn.get("text")
    )
    return text[:max_chars].rstrip()
