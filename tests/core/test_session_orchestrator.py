import asyncio
import json
from collections.abc import AsyncIterator, Callable

from voice_agent.config import Settings
from voice_agent.contracts.audio import AudioFrame
from voice_agent.contracts.errors import CallEndedError
from voice_agent.contracts.events import (
    InterruptionStarted,
    SmartTurnResult,
    SpeechStart,
    SpeechStop,
    TranscriptEvent,
    UserTurnFinal,
)
from voice_agent.contracts.packets import AgentPacket, now_ms
from voice_agent.core.interruption.output_gate import OutputGateState
from voice_agent.core.session_orchestrator import SessionOrchestrator, SessionProviders
from voice_agent.core.state_machine import CallState
from voice_agent.core.turn_detection.local_models import TurnDetectionModels
from voice_agent.core.turn_detection.smart_turn_runner import SmartTurnDecision
from voice_agent.providers.llm import MockLLM
from voice_agent.providers.storage import MemoryStore
from voice_agent.providers.stt import MockSTT
from voice_agent.providers.telephony import MockTelephony
from voice_agent.providers.tts import MockTTS


def test_mock_session_runs_to_clean_shutdown() -> None:
    async def scenario() -> None:
        live_store = MemoryStore()
        final_store = MemoryStore()
        telephony = MockTelephony(call_id="call-1")
        stt = MockSTT()
        tts = MockTTS(chunk_words=2)
        llm = MockLLM(responses=["Absolutely, I can help."])
        orchestrator = SessionOrchestrator(
            call_id="call-1",
            providers=SessionProviders(
                telephony=telephony,
                stt=stt,
                tts=tts,
                llm=llm,
                live_store=live_store,
                final_store=final_store,
            ),
        )

        await telephony.enqueue_audio(
            AudioFrame(
                call_id="call-1",
                data=b"mock-audio",
                timestamp_ms=now_ms(),
                sample_rate=8000,
                codec="mulaw_8k",
                duration_ms=20,
                meta={"transcript": "I need help", "language": "en-IN"},
            )
        )
        await telephony.finish_input()

        stats = await asyncio.wait_for(orchestrator.run(), timeout=2)

        assert orchestrator.state == CallState.CLOSED
        assert telephony.stopped
        assert stats.audio_frames_received == 1
        assert stats.transcripts_received == 1
        assert stats.user_turns_finalized == 1
        assert stats.llm_responses_started == 1
        assert stats.audio_chunks_sent >= 1
        assert telephony.checkpoints == ["call-1-message-1"]
        assert orchestrator.playback_tracker.heard_text("call-1-message-1") == "Absolutely, I can help."
        assert orchestrator.context_manager.assistant_turns[-1].heard_text == "Absolutely, I can help."
        assert not orchestrator.context_manager.assistant_turns[-1].interrupted
        assert await live_store.get_call_state("call-1") is None
        assert final_store.call_records["call-1"]["state"] == "closed"
        assert final_store.call_records["call-1"]["turns"]
        assert "metrics" in final_store.call_records["call-1"]
        assert final_store.call_records["call-1"]["transcript_summary"]

    asyncio.run(scenario())


def test_mock_session_start_then_shutdown_does_not_hang() -> None:
    async def scenario() -> None:
        telephony = MockTelephony(call_id="call-2")
        orchestrator = SessionOrchestrator(
            call_id="call-2",
            providers=SessionProviders(
                telephony=telephony,
                stt=MockSTT(),
                tts=MockTTS(),
                llm=MockLLM(),
                live_store=MemoryStore(),
                final_store=MemoryStore(),
            ),
        )

        await orchestrator.start()
        await asyncio.wait_for(orchestrator.shutdown("test_shutdown"), timeout=2)

        assert orchestrator.state == CallState.CLOSED
        assert telephony.stop_reason == "test_shutdown"
        assert all(task.done() for task in orchestrator.tasks.values())

    asyncio.run(scenario())


def test_session_logs_agent_response_text(tmp_path) -> None:
    async def scenario() -> None:
        telephony = MockTelephony(call_id="call-log-agent")
        orchestrator = SessionOrchestrator(
            call_id="call-log-agent",
            providers=SessionProviders(
                telephony=telephony,
                stt=MockSTT(),
                tts=MockTTS(),
                llm=MockLLM(responses=["Sure, I can help with that."]),
            ),
            settings=Settings(
                log_dir=str(tmp_path),
                min_user_speech_ms=0,
                min_silence_for_turn_end_ms=0,
                llm_sentence_timeout_ms=1,
                end_call_listener_enabled=False,
            ),
        )

        await telephony.enqueue_audio(
            AudioFrame(
                call_id="call-log-agent",
                data=b"mock-audio",
                timestamp_ms=now_ms(),
                sample_rate=8000,
                codec="mulaw_8k",
                duration_ms=20,
                meta={"transcript": "I need help", "language": "en-IN"},
            )
        )
        await telephony.finish_input()

        await asyncio.wait_for(orchestrator.run(), timeout=2)

        log_files = list(tmp_path.glob("*/*.jsonl"))
        assert len(log_files) == 1
        rows = [json.loads(line) for line in log_files[0].read_text(encoding="utf-8").splitlines()]
        generated = [row for row in rows if row["event_name"] == "agent_response_text"]
        played = [row for row in rows if row["event_name"] == "agent_response_played"]
        assert generated[-1]["details"]["text"] == "Sure, I can help with that."
        assert played[-1]["details"]["text"] == "Sure, I can help with that."

    asyncio.run(scenario())


def test_session_uses_local_vad_and_smart_turn_for_turn_end() -> None:
    async def scenario() -> None:
        telephony = MockTelephony(call_id="call-local-turn")
        orchestrator = SessionOrchestrator(
            call_id="call-local-turn",
            providers=SessionProviders(
                telephony=telephony,
                stt=MockSTT(),
                tts=MockTTS(),
                llm=MockLLM(responses=["Done."]),
            ),
            settings=Settings(
                min_user_speech_ms=0,
                min_silence_for_turn_end_ms=0,
                llm_sentence_timeout_ms=1,
            ),
            turn_detection_models=TurnDetectionModels(
                vad=FakeVADModel(),
                smart_turn=FakeSmartTurnModel(),
            ),
        )

        await telephony.enqueue_audio(
            AudioFrame(
                call_id="call-local-turn",
                data=b"\xff" * 160,
                timestamp_ms=1000,
                sample_rate=8000,
                codec="mulaw_8k",
                duration_ms=20,
                meta={"transcript": "I need help", "language": "en-IN"},
            )
        )
        await telephony.finish_input()

        stats = await asyncio.wait_for(orchestrator.run(), timeout=2)

        assert stats.user_turns_finalized == 1
        assert stats.llm_responses_started == 1
        assert orchestrator.context_manager.user_turns[-1].text == "I need help"

    asyncio.run(scenario())


def test_completed_speech_without_transcript_prompts_retry() -> None:
    async def scenario() -> None:
        orchestrator = SessionOrchestrator(
            call_id="call-empty-transcript",
            providers=SessionProviders(
                telephony=MockTelephony(call_id="call-empty-transcript"),
                stt=MockSTT(),
                tts=MockTTS(),
                llm=MockLLM(),
            ),
            settings=Settings(
                empty_transcript_retry_delay_ms=1,
                empty_transcript_min_audio_ms=100,
                min_user_speech_ms=0,
                end_of_turn_grace_ms=0,
            ),
        )

        orchestrator.turn_manager.handle_speech_start(
            SpeechStart("call-empty-transcript", 1000, "vad", 0.95)
        )
        orchestrator.turn_manager.handle_speech_stop(
            SpeechStop("call-empty-transcript", 1900, "vad", 0.95)
        )
        orchestrator.turn_manager.handle_smart_turn(
            SmartTurnResult(
                call_id="call-empty-transcript",
                turn_id=1,
                is_complete=True,
                confidence=0.95,
                reason="smart_turn_v3_onnx",
            )
        )

        await orchestrator._emit_turn_if_ready()
        turn_check_task = orchestrator._turn_check_task
        assert turn_check_task is not None
        await asyncio.wait_for(turn_check_task, timeout=0.2)

        packet = await asyncio.wait_for(orchestrator.queues.tts_request.get(), timeout=0.2)

        assert packet.packet_type == "llm_sentence"
        assert packet.turn_id == 1
        assert packet.data["text"] == orchestrator.settings.empty_transcript_retry_text
        assert orchestrator.stats.user_turns_finalized == 0
        assert orchestrator.context_manager.user_turns == []
        assert orchestrator.turn_manager.state.turn_id == 0

    asyncio.run(scenario())


def test_late_final_transcript_restarts_thinking_llm_with_amended_turn() -> None:
    async def scenario() -> None:
        llm = SlowLLM()
        orchestrator = SessionOrchestrator(
            call_id="call-late-repair",
            providers=SessionProviders(
                telephony=MockTelephony(call_id="call-late-repair"),
                stt=MockSTT(),
                tts=MockTTS(),
                llm=llm,
            ),
            settings=Settings(
                min_user_speech_ms=0,
                min_silence_for_turn_end_ms=0,
                end_of_turn_grace_ms=0,
            ),
        )
        orchestrator._vad_stream = object()

        turn_task = asyncio.create_task(orchestrator._turn_manager_loop())
        llm_task = asyncio.create_task(orchestrator._llm_loop())
        try:
            orchestrator.turn_manager.handle_speech_start(
                SpeechStart("call-late-repair", 1000, "vad", 0.9)
            )
            orchestrator.turn_manager.handle_speech_stop(
                SpeechStop("call-late-repair", 1800, "vad", 0.9)
            )
            orchestrator.turn_manager.handle_smart_turn(
                SmartTurnResult(
                    call_id="call-late-repair",
                    turn_id=1,
                    is_complete=True,
                    confidence=0.95,
                    reason="smart_turn_v3_onnx",
                )
            )
            await orchestrator.queues.transcript_event.put(
                orchestrator._packet(
                    "transcript_final",
                    {
                        "event": TranscriptEvent(
                            call_id="call-late-repair",
                            text="I think कि I am trying to solve the issue where हिंदी",
                            is_final=True,
                            confidence=0.95,
                            language="hi-IN",
                            start_ms=1000,
                            end_ms=1800,
                            provider="mock",
                        )
                    },
                )
            )

            await _wait_for(lambda: orchestrator._active_llm_response_id is not None)
            first_response_id = orchestrator._active_llm_response_id

            await orchestrator.queues.transcript_event.put(
                orchestrator._packet(
                    "transcript_final",
                    {
                        "event": TranscriptEvent(
                            call_id="call-late-repair",
                            text="is not supported by you. So can you please speak in हिंदी?",
                            is_final=True,
                            confidence=0.98,
                            language="hi-IN",
                            start_ms=1800,
                            end_ms=2600,
                            provider="mock",
                        )
                    },
                )
            )

            await _wait_for(lambda: len(llm.requests) >= 2)

            assert first_response_id in llm.cancelled_response_ids
            assert orchestrator.stats.late_transcript_repairs == 1
            assert (
                orchestrator.context_manager.user_turns[-1].text
                == "I think कि I am trying to solve the issue where हिंदी "
                "is not supported by you. So can you please speak in हिंदी?"
            )
            prompt = llm.requests[-1]["messages"][-1]["content"]
            assert len(llm.requests[-1]["messages"]) == 1
            assert llm.requests[-1]["messages"][-1]["role"] == "system"
            assert f"User: {orchestrator.context_manager.user_turns[-1].text}" in prompt
            assert (
                f'The user\'s last message: "{orchestrator.context_manager.user_turns[-1].text}"'
                in prompt
            )
        finally:
            orchestrator._shutdown_started = True
            turn_task.cancel()
            llm_task.cancel()
            await asyncio.gather(turn_task, llm_task, return_exceptions=True)

    asyncio.run(scenario())


def test_final_turn_does_not_wait_on_pending_short_interruption() -> None:
    async def scenario() -> None:
        llm = MockLLM(responses=["Done."])
        tts = MockTTS()
        orchestrator = SessionOrchestrator(
            call_id="call-fast-resume",
            providers=SessionProviders(
                telephony=MockTelephony(call_id="call-fast-resume"),
                stt=MockSTT(),
                tts=tts,
                llm=llm,
            ),
            settings=Settings(
                hard_interrupt_after_audio_ms=1000,
                output_gate_wait_timeout_ms=500,
            ),
        )
        old_sequence_id = orchestrator.sequence_manager.create_sequence()
        orchestrator.interruption_manager.track_response(
            old_sequence_id,
            "old-response",
            "old-message",
        )
        orchestrator.interruption_manager.mark_agent_audio_sent(old_sequence_id)

        await orchestrator.interruption_manager.handle_speech_start(
            SpeechStart("call-fast-resume", 1000, "vad", 0.9)
        )
        assert orchestrator.output_gate.state == OutputGateState.WAIT
        assert orchestrator.interruption_manager.state.user_may_be_interrupting

        await asyncio.wait_for(
            orchestrator._run_llm_response(
                UserTurnFinal(
                    call_id="call-fast-resume",
                    turn_id=1,
                    text="hello",
                    language="en-IN",
                    confidence=0.9,
                    start_ms=1000,
                    end_ms=1250,
                )
            ),
            timeout=0.5,
        )

        assert len(llm.requests) == 1
        assert "old-response" in llm.cancelled_response_ids
        assert "old-message" in tts.cancelled_message_ids
        assert not orchestrator.sequence_manager.is_valid(old_sequence_id)
        assert orchestrator.output_gate.state == OutputGateState.SEND
        assert not orchestrator.interruption_manager.state.user_may_be_interrupting

    asyncio.run(scenario())


def test_turn_manager_accepts_final_transcript_when_local_vad_misses_start() -> None:
    async def scenario() -> None:
        orchestrator = SessionOrchestrator(
            call_id="call-vad-miss",
            providers=SessionProviders(
                telephony=MockTelephony(call_id="call-vad-miss"),
                stt=MockSTT(),
                tts=MockTTS(),
                llm=MockLLM(),
            ),
            settings=Settings(
                min_user_speech_ms=0,
                min_silence_for_turn_end_ms=0,
            ),
        )
        orchestrator._vad_stream = object()
        orchestrator.turn_manager.smart_turn_available = True

        turn_task = asyncio.create_task(orchestrator._turn_manager_loop())
        try:
            await orchestrator.queues.transcript_event.put(
                orchestrator._packet(
                    "transcript_final",
                    {
                        "event": TranscriptEvent(
                            call_id="call-vad-miss",
                            text="I need help",
                            is_final=True,
                            confidence=0.95,
                            language="en-IN",
                            start_ms=1000,
                            end_ms=1400,
                            provider="mock",
                        )
                    },
                )
            )

            packet = await asyncio.wait_for(orchestrator.queues.turn_event.get(), timeout=0.2)

            assert packet.packet_type == "user_turn_final"
            assert packet.data["event"].text == "I need help"
        finally:
            orchestrator._shutdown_started = True
            turn_task.cancel()
            await asyncio.gather(turn_task, return_exceptions=True)

    asyncio.run(scenario())


def test_estimated_playback_completion_releases_late_vobiz_checkpoint_state() -> None:
    orchestrator = SessionOrchestrator(
        call_id="call-playback-fallback",
        providers=SessionProviders(
            telephony=MockTelephony(call_id="call-playback-fallback"),
            stt=MockSTT(),
            tts=MockTTS(),
            llm=MockLLM(),
        ),
        settings=Settings(playback_completion_fallback_grace_ms=0),
    )
    started_ms = now_ms() - 1000
    sequence_id = orchestrator.sequence_manager.create_sequence()
    message_id = "call-playback-fallback-message-1"
    orchestrator.interruption_manager.track_response(sequence_id, "response-1", message_id)
    orchestrator.interruption_manager.mark_agent_audio_sent(sequence_id)
    orchestrator.playback_tracker.start_message(
        message_id=message_id,
        sequence_id=sequence_id,
        started_ms=started_ms,
    )
    orchestrator.playback_tracker.append_generated_text(message_id, "Done.")
    orchestrator.context_manager.start_assistant_turn(message_id=message_id, sequence_id=sequence_id)
    orchestrator.context_manager.append_assistant_text(message_id, "Done.")
    orchestrator.playback_tracker.mark_audio_sent(
        AudioFrame(
            call_id="call-playback-fallback",
            data=b"audio",
            timestamp_ms=started_ms,
            sample_rate=8000,
            codec="mulaw_8k",
            sequence_id=sequence_id,
            duration_ms=100,
            meta={"message_id": message_id},
        ),
        timestamp_ms=started_ms,
    )
    orchestrator.playback_tracker.mark_checkpoint_sent(message_id, message_id, timestamp_ms=started_ms + 100)

    playback = orchestrator._release_agent_if_estimated_playback_complete("test")

    assert playback is not None
    assert not orchestrator.interruption_manager.state.agent_is_speaking
    assert orchestrator.interruption_manager.active_response is None
    assert not orchestrator.sequence_manager.is_valid(sequence_id)
    assert orchestrator.context_manager.assistant_turns[-1].heard_text == "Done."


def test_interruption_disabled_suppresses_overlap_transcript() -> None:
    async def scenario() -> None:
        orchestrator = SessionOrchestrator(
            call_id="call-no-barge",
            providers=SessionProviders(
                telephony=MockTelephony(call_id="call-no-barge"),
                stt=MockSTT(),
                tts=MockTTS(),
                llm=MockLLM(),
            ),
            settings=Settings(interruption_enabled=False),
        )
        sequence_id = orchestrator.sequence_manager.create_sequence()
        orchestrator.interruption_manager.track_response(sequence_id, "response-1", "message-1")
        orchestrator.interruption_manager.mark_agent_audio_sent(sequence_id)

        await orchestrator._handle_speech_event(
            SpeechStart("call-no-barge", 1000, "vad", 0.9),
            run_smart_turn=False,
        )
        assert orchestrator._suppress_overlap_turn

        turn_task = asyncio.create_task(orchestrator._turn_manager_loop())
        try:
            await orchestrator.queues.transcript_event.put(
                orchestrator._packet(
                    "transcript_final",
                    {
                        "event": TranscriptEvent(
                            call_id="call-no-barge",
                            text="this should not answer the next question",
                            is_final=True,
                            confidence=0.95,
                            language="en-IN",
                            start_ms=1000,
                            end_ms=1500,
                            provider="mock",
                        )
                    },
                )
            )
            await asyncio.sleep(0.05)

            assert orchestrator.stats.user_turns_finalized == 0
            assert orchestrator.queues.turn_event.empty()
        finally:
            orchestrator._shutdown_started = True
            turn_task.cancel()
            await asyncio.gather(turn_task, return_exceptions=True)

    asyncio.run(scenario())


def test_output_loop_drops_stale_sequence_audio() -> None:
    async def scenario() -> None:
        telephony = MockTelephony(call_id="call-3")
        orchestrator = SessionOrchestrator(
            call_id="call-3",
            providers=SessionProviders(
                telephony=telephony,
                stt=MockSTT(),
                tts=MockTTS(),
                llm=MockLLM(),
            ),
        )
        stale_frame = AudioFrame(
            call_id="call-3",
            data=b"stale",
            timestamp_ms=now_ms(),
            sample_rate=8000,
            codec="mulaw_8k",
            sequence_id=99,
        )

        await orchestrator.queues.tts_audio.put(
            AgentPacket(
                packet_type="tts_audio_chunk",
                call_id="call-3",
                turn_id=None,
                sequence_id=99,
                request_id=None,
                timestamp_ms=now_ms(),
                data={"frame": stale_frame},
            )
        )
        await orchestrator.queues.tts_audio.put(AgentPacket.eos_packet("call-3"))

        await asyncio.wait_for(orchestrator._output_loop(), timeout=1)

        assert telephony.sent_audio == []
        assert orchestrator.stats.stale_audio_chunks_dropped == 1

    asyncio.run(scenario())


def test_output_loop_closes_cleanly_when_call_already_ended() -> None:
    async def scenario() -> None:
        telephony = ClosedOnSendTelephony(call_id="call-ended")
        orchestrator = SessionOrchestrator(
            call_id="call-ended",
            providers=SessionProviders(
                telephony=telephony,
                stt=MockSTT(),
                tts=MockTTS(),
                llm=MockLLM(),
            ),
        )
        sequence_id = orchestrator.sequence_manager.create_sequence()
        frame = AudioFrame(
            call_id="call-ended",
            data=b"audio",
            timestamp_ms=now_ms(),
            sample_rate=8000,
            codec="mulaw_8k",
            sequence_id=sequence_id,
        )

        await orchestrator.queues.tts_audio.put(
            AgentPacket(
                packet_type="tts_audio_chunk",
                call_id="call-ended",
                turn_id=None,
                sequence_id=sequence_id,
                request_id=None,
                timestamp_ms=now_ms(),
                data={"frame": frame},
            )
        )

        await asyncio.wait_for(orchestrator._output_loop(), timeout=1)

        assert orchestrator.state == CallState.CLOSED
        assert orchestrator.stats.errors == 0
        assert telephony.stop_reason == "telephony_closed"

    asyncio.run(scenario())


def test_end_call_listener_hangs_up_after_user_goodbye() -> None:
    async def scenario() -> None:
        telephony = MockTelephony(call_id="call-goodbye")
        orchestrator = SessionOrchestrator(
            call_id="call-goodbye",
            providers=SessionProviders(
                telephony=telephony,
                stt=MockSTT(),
                tts=MockTTS(chunk_words=3),
                llm=MockLLM(responses=["All the best, keep pushing! Byy!"]),
            ),
            settings=Settings(
                min_user_speech_ms=0,
                min_silence_for_turn_end_ms=0,
                smart_turn_enabled=False,
                llm_sentence_timeout_ms=1,
            ),
        )

        await telephony.enqueue_audio(
            AudioFrame(
                call_id="call-goodbye",
                data=b"mock-audio",
                timestamp_ms=now_ms(),
                sample_rate=8000,
                codec="mulaw_8k",
                duration_ms=20,
                meta={"transcript": "ठीक है bye", "language": "hi-IN"},
            )
        )
        await telephony.finish_input()

        stats = await asyncio.wait_for(orchestrator.run(), timeout=2)

        assert telephony.hangup_count == 1
        assert telephony.hangup_reason == "end_call_listener"
        assert stats.end_call_listener_hangups == 1
        assert orchestrator.final_record is not None
        assert orchestrator.final_record["reason"] == "end_call_listener"

    asyncio.run(scenario())


class SlowLLM(MockLLM):
    async def stream_response(
        self,
        call_id: str,
        messages: list[dict[str, str]],
        response_id: str,
    ) -> AsyncIterator[str]:
        self.requests.append(
            {"call_id": call_id, "messages": messages, "response_id": response_id}
        )
        await asyncio.sleep(60)
        yield "unreachable"


class ClosedOnSendTelephony(MockTelephony):
    async def send_audio(self, frame: AudioFrame) -> None:
        raise CallEndedError("caller hung up")


async def _wait_for(predicate: Callable[[], bool]) -> None:
    for _ in range(100):
        if predicate():
            return
        await asyncio.sleep(0.01)
    raise AssertionError("condition was not met before timeout")


class FakeVADModel:
    def create_stream(self, call_id: str, settings: Settings) -> "FakeVADStream":
        return FakeVADStream(call_id)


class FakeVADStream:
    def __init__(self, call_id: str) -> None:
        self.call_id = call_id
        self.used = False

    def process_frame(self, frame: AudioFrame):
        if self.used:
            return []
        self.used = True
        from voice_agent.contracts.events import SpeechStart, SpeechStop

        return [
            SpeechStart(self.call_id, frame.timestamp_ms, "vad", 0.95),
            SpeechStop(self.call_id, frame.timestamp_ms + (frame.duration_ms or 20), "vad", 0.95),
        ]

    def flush(self):
        return None


class FakeSmartTurnModel:
    def classify(self, frame: AudioFrame) -> SmartTurnDecision:
        assert frame.codec == "pcm16_16k"
        return SmartTurnDecision(True, 0.95, "smart_turn_v3_onnx")


def test_output_loop_drops_audio_after_pending_sequences_invalidated() -> None:
    async def scenario() -> None:
        telephony = MockTelephony(call_id="call-4")
        orchestrator = SessionOrchestrator(
            call_id="call-4",
            providers=SessionProviders(
                telephony=telephony,
                stt=MockSTT(),
                tts=MockTTS(),
                llm=MockLLM(),
            ),
        )
        sequence_id = orchestrator.sequence_manager.create_sequence()
        await orchestrator.invalidate_pending_output("interruption")
        frame = AudioFrame(
            call_id="call-4",
            data=b"old-audio",
            timestamp_ms=now_ms(),
            sample_rate=8000,
            codec="mulaw_8k",
            sequence_id=sequence_id,
        )

        await orchestrator.queues.tts_audio.put(
            AgentPacket(
                packet_type="tts_audio_chunk",
                call_id="call-4",
                turn_id=None,
                sequence_id=sequence_id,
                request_id=None,
                timestamp_ms=now_ms(),
                data={"frame": frame},
            )
        )
        await orchestrator.queues.tts_audio.put(AgentPacket.eos_packet("call-4"))

        await asyncio.wait_for(orchestrator._output_loop(), timeout=1)

        assert telephony.sent_audio == []
        assert orchestrator.stats.stale_audio_chunks_dropped == 1

    asyncio.run(scenario())


def test_output_loop_drops_audio_when_gate_wait_times_out() -> None:
    async def scenario() -> None:
        telephony = MockTelephony(call_id="call-5")
        orchestrator = SessionOrchestrator(
            call_id="call-5",
            providers=SessionProviders(
                telephony=telephony,
                stt=MockSTT(),
                tts=MockTTS(),
                llm=MockLLM(),
            ),
            settings=Settings(output_gate_wait_timeout_ms=1),
        )
        sequence_id = orchestrator.sequence_manager.create_sequence()
        await orchestrator.output_gate.set_wait()
        frame = AudioFrame(
            call_id="call-5",
            data=b"waiting-audio",
            timestamp_ms=now_ms(),
            sample_rate=8000,
            codec="mulaw_8k",
            sequence_id=sequence_id,
        )

        await orchestrator.queues.tts_audio.put(
            AgentPacket(
                packet_type="tts_audio_chunk",
                call_id="call-5",
                turn_id=None,
                sequence_id=sequence_id,
                request_id=None,
                timestamp_ms=now_ms(),
                data={"frame": frame},
            )
        )
        await orchestrator.queues.tts_audio.put(AgentPacket.eos_packet("call-5"))

        await asyncio.wait_for(orchestrator._output_loop(), timeout=1)

        assert telephony.sent_audio == []
        assert orchestrator.output_gate.state == OutputGateState.WAIT
        assert orchestrator.stats.waited_audio_chunks_dropped == 1

    asyncio.run(scenario())


def test_confirmed_interruption_purges_stale_tts_packets() -> None:
    async def scenario() -> None:
        orchestrator = SessionOrchestrator(
            call_id="call-6",
            providers=SessionProviders(
                telephony=MockTelephony(call_id="call-6"),
                stt=MockSTT(),
                tts=MockTTS(),
                llm=MockLLM(),
            ),
        )
        sequence_id = orchestrator.sequence_manager.create_sequence()
        frame = AudioFrame(
            call_id="call-6",
            data=b"old-audio",
            timestamp_ms=now_ms(),
            sample_rate=8000,
            codec="mulaw_8k",
            sequence_id=sequence_id,
        )
        await orchestrator.queues.tts_request.put(
            AgentPacket(
                packet_type="llm_sentence",
                call_id="call-6",
                turn_id=1,
                sequence_id=sequence_id,
                request_id="response-1",
                timestamp_ms=now_ms(),
                data={"text": "old text", "message_id": "message-1"},
            )
        )
        await orchestrator.queues.tts_audio.put(
            AgentPacket(
                packet_type="tts_audio_chunk",
                call_id="call-6",
                turn_id=1,
                sequence_id=sequence_id,
                request_id="response-1",
                timestamp_ms=now_ms(),
                data={"frame": frame},
            )
        )

        orchestrator.sequence_manager.invalidate_pending("interruption")
        await orchestrator._handle_confirmed_interruption(
            InterruptionStarted(
                call_id="call-6",
                turn_id=1,
                sequence_id=sequence_id,
                reason="force_interrupt_phrase",
                transcript="wait",
                ts_ms=now_ms(),
            )
        )

        assert orchestrator.queues.tts_request.empty()
        assert orchestrator.queues.tts_audio.empty()
        assert orchestrator.stats.pending_tts_requests_purged == 1
        assert orchestrator.stats.pending_tts_audio_purged == 1

    asyncio.run(scenario())


def test_confirmed_interruption_updates_context_with_heard_partial_text() -> None:
    async def scenario() -> None:
        orchestrator = SessionOrchestrator(
            call_id="call-7",
            providers=SessionProviders(
                telephony=MockTelephony(call_id="call-7"),
                stt=MockSTT(),
                tts=MockTTS(),
                llm=MockLLM(),
            ),
        )
        sequence_id = orchestrator.sequence_manager.create_sequence()
        message_id = "call-7-message-1"
        orchestrator.playback_tracker.start_message(message_id=message_id, sequence_id=sequence_id)
        orchestrator.context_manager.start_assistant_turn(message_id=message_id, sequence_id=sequence_id)
        orchestrator.playback_tracker.append_generated_text(message_id, "hello world again")
        orchestrator.context_manager.append_assistant_text(message_id, "hello world again")
        orchestrator.playback_tracker.mark_audio_sent(
            AudioFrame(
                call_id="call-7",
                data=b"audio",
                timestamp_ms=1000,
                sample_rate=8000,
                codec="mulaw_8k",
                sequence_id=sequence_id,
                duration_ms=1000,
                meta={
                    "message_id": message_id,
                    "word_timestamps": {
                        "words": ["hello", "world", "again"],
                        "end": [0.2, 0.5, 0.9],
                    },
                },
            ),
            timestamp_ms=1000,
        )

        await orchestrator._handle_confirmed_interruption(
            InterruptionStarted(
                call_id="call-7",
                turn_id=1,
                sequence_id=sequence_id,
                reason="word_count_threshold",
                transcript="wait",
                ts_ms=1600,
            )
        )

        assistant = orchestrator.context_manager.assistant_turns[-1]
        assert assistant.heard_text == "hello world"
        assert assistant.full_text == "hello world again"
        assert assistant.interrupted

    asyncio.run(scenario())
