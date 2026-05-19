import asyncio

from voice_agent.config import Settings
from voice_agent.contracts.events import SpeechStart, SpeechStop, TranscriptEvent
from voice_agent.core.interruption.interruption_manager import (
    InterruptionManager,
    InterruptionOutcome,
)
from voice_agent.core.interruption.output_gate import OutputDecision, OutputGate, OutputGateState
from voice_agent.core.interruption.sequence_manager import SequenceManager
from voice_agent.providers.llm import MockLLM
from voice_agent.providers.stt import MockSTT
from voice_agent.providers.telephony import MockTelephony
from voice_agent.providers.tts import MockTTS


def final_transcript(text: str, *, start_ms: int = 1100, end_ms: int = 1400) -> TranscriptEvent:
    return TranscriptEvent(
        call_id="call-interrupt",
        text=text,
        is_final=True,
        confidence=0.9,
        language="hi-IN",
        start_ms=start_ms,
        end_ms=end_ms,
        provider="mock",
    )


def build_manager(settings: Settings | None = None) -> tuple[
    InterruptionManager,
    SequenceManager,
    OutputGate,
    MockTelephony,
    MockTTS,
    MockLLM,
]:
    settings = settings or Settings()
    sequence_manager = SequenceManager()
    output_gate = OutputGate()
    telephony = MockTelephony("call-interrupt")
    tts = MockTTS()
    llm = MockLLM()
    manager = InterruptionManager(
        call_id="call-interrupt",
        settings=settings,
        output_gate=output_gate,
        sequence_manager=sequence_manager,
        telephony=telephony,
        tts=tts,
        llm=llm,
    )
    sequence_id = sequence_manager.create_sequence()
    manager.track_response(sequence_id, "response-1", "message-1")
    manager.mark_agent_audio_sent(sequence_id)
    return manager, sequence_manager, output_gate, telephony, tts, llm


def test_speech_start_sets_output_gate_wait() -> None:
    async def scenario() -> None:
        manager, _, output_gate, _, _, _ = build_manager()

        decision = await manager.handle_speech_start(
            SpeechStart("call-interrupt", 1000, "vad", 0.9)
        )

        assert decision.outcome == InterruptionOutcome.CANDIDATE
        assert output_gate.state == OutputGateState.WAIT
        assert manager.state.user_may_be_interrupting

    asyncio.run(scenario())


def test_backchannel_rejects_without_cancel_or_clear() -> None:
    async def scenario() -> None:
        manager, sequence_manager, output_gate, telephony, tts, llm = build_manager()

        await manager.handle_speech_start(SpeechStart("call-interrupt", 1000, "vad", 0.9))
        decision = await manager.handle_transcript(final_transcript("haan"))

        assert decision.outcome == InterruptionOutcome.REJECTED
        assert decision.reason == "backchannel_phrase"
        assert output_gate.state == OutputGateState.SEND
        assert sequence_manager.is_valid(1)
        assert telephony.clear_reasons == []
        assert tts.cancelled_message_ids == set()
        assert llm.cancelled_response_ids == set()

    asyncio.run(scenario())


def test_force_phrase_confirms_and_cancels_everything() -> None:
    async def scenario() -> None:
        manager, sequence_manager, output_gate, telephony, tts, llm = build_manager()

        await manager.handle_speech_start(SpeechStart("call-interrupt", 1000, "vad", 0.9))
        decision = await manager.handle_transcript(final_transcript("wait"))

        assert decision.outcome == InterruptionOutcome.CONFIRMED
        assert decision.reason == "force_interrupt_phrase"
        assert not sequence_manager.is_valid(1)
        assert output_gate.decision_for(1) == OutputDecision.DROP
        assert telephony.clear_reasons == ["force_interrupt_phrase"]
        assert tts.cancelled_message_ids == {"message-1"}
        assert llm.cancelled_response_ids == {"response-1"}

    asyncio.run(scenario())


def test_three_word_user_speech_confirms_interruption() -> None:
    async def scenario() -> None:
        settings = Settings(min_interrupt_words=3)
        manager, _, _, telephony, _, _ = build_manager(settings)

        await manager.handle_speech_start(SpeechStart("call-interrupt", 1000, "vad", 0.9))
        decision = await manager.handle_transcript(final_transcript("I need help"))

        assert decision.outcome == InterruptionOutcome.CONFIRMED
        assert decision.reason == "word_count_threshold"
        assert telephony.clear_reasons == ["word_count_threshold"]

    asyncio.run(scenario())


def test_short_noise_stays_pending_not_confirmed() -> None:
    async def scenario() -> None:
        settings = Settings(min_interrupt_words=3, hard_interrupt_after_audio_ms=350)
        manager, sequence_manager, output_gate, telephony, tts, llm = build_manager(settings)

        await manager.handle_speech_start(SpeechStart("call-interrupt", 1000, "vad", 0.9))
        decision = await manager.handle_transcript(final_transcript("uh", end_ms=1120))

        assert decision.outcome == InterruptionOutcome.PENDING
        assert decision.reason == "not_enough_words"
        assert sequence_manager.is_valid(1)
        assert output_gate.state == OutputGateState.WAIT
        assert telephony.clear_reasons == []
        assert tts.cancelled_message_ids == set()
        assert llm.cancelled_response_ids == set()

    asyncio.run(scenario())


def test_speech_stop_releases_candidate_without_cancel_or_clear() -> None:
    async def scenario() -> None:
        manager, sequence_manager, output_gate, telephony, tts, llm = build_manager()

        await manager.handle_speech_start(SpeechStart("call-interrupt", 1000, "vad", 0.9))
        decision = await manager.handle_speech_stop(SpeechStop("call-interrupt", 1120, "vad", 0.9))

        assert decision.outcome == InterruptionOutcome.REJECTED
        assert decision.reason == "speech_stop_without_confirmation"
        assert output_gate.state == OutputGateState.SEND
        assert sequence_manager.is_valid(1)
        assert telephony.clear_reasons == []
        assert tts.cancelled_message_ids == set()
        assert llm.cancelled_response_ids == set()

    asyncio.run(scenario())
