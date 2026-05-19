import asyncio

from voice_agent.config import Settings
from voice_agent.contracts.audio import AudioFrame
from voice_agent.contracts.events import InterruptionStarted
from voice_agent.contracts.packets import AgentPacket, now_ms
from voice_agent.core.interruption.output_gate import OutputGateState
from voice_agent.core.session_orchestrator import SessionOrchestrator, SessionProviders
from voice_agent.core.state_machine import CallState
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
