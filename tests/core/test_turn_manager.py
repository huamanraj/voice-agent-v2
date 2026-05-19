from voice_agent.config import Settings
from voice_agent.contracts.events import SpeechStart, SpeechStop, TranscriptEvent
from voice_agent.core.turn_detection.expected_answer import ExpectedAnswer
from voice_agent.core.turn_detection.turn_manager import TurnManager


def transcript(
    text: str,
    *,
    is_final: bool = True,
    start_ms: int = 1000,
    end_ms: int = 1400,
) -> TranscriptEvent:
    return TranscriptEvent(
        call_id="call-turn",
        text=text,
        is_final=is_final,
        confidence=0.9,
        language="hi-IN",
        start_ms=start_ms,
        end_ms=end_ms,
        provider="mock",
    )


def test_turn_manager_waits_on_hinglish_incomplete_connector() -> None:
    settings = Settings(
        min_user_speech_ms=100,
        min_silence_for_turn_end_ms=300,
        max_silence_before_force_end_ms=1200,
    )
    manager = TurnManager("call-turn", settings)

    manager.handle_transcript(transcript("mujhe problem hai ki"))

    decision = manager.evaluate(timestamp_ms=1800)

    assert not decision.should_emit
    assert decision.reason == "incomplete_connector"


def test_turn_manager_forces_incomplete_after_max_silence() -> None:
    settings = Settings(
        min_user_speech_ms=100,
        min_silence_for_turn_end_ms=300,
        max_silence_before_force_end_ms=900,
    )
    manager = TurnManager("call-turn", settings)

    manager.handle_transcript(transcript("mujhe problem hai ki"))
    turn = manager.emit_turn(timestamp_ms=2400)

    assert turn is not None
    assert turn.text == "mujhe problem hai ki"


def test_turn_manager_allows_expected_short_yes_no_answer() -> None:
    settings = Settings(min_user_speech_ms=100, min_silence_for_turn_end_ms=250)
    manager = TurnManager(
        "call-turn",
        settings,
        expected_answer=ExpectedAnswer(
            answer_type="yes_no",
            short_answer_allowed=True,
            min_words=1,
        ),
    )

    manager.handle_transcript(transcript("haan", end_ms=1300))
    turn = manager.emit_turn(timestamp_ms=1600)

    assert turn is not None
    assert turn.text == "haan"
    assert turn.language == "hi-IN"


def test_turn_manager_rejects_short_answer_without_expected_context() -> None:
    settings = Settings(
        min_user_speech_ms=100,
        min_silence_for_turn_end_ms=250,
        max_silence_before_force_end_ms=1000,
    )
    manager = TurnManager("call-turn", settings)

    manager.handle_transcript(transcript("haan", end_ms=1300))
    decision = manager.evaluate(timestamp_ms=1600)

    assert not decision.should_emit
    assert decision.reason == "smart_turn_incomplete"


def test_turn_manager_uses_vad_stop_when_smart_turn_disabled() -> None:
    settings = Settings(
        smart_turn_enabled=False,
        min_user_speech_ms=100,
        min_silence_for_turn_end_ms=250,
    )
    manager = TurnManager("call-turn", settings)

    manager.handle_speech_start(SpeechStart("call-turn", 1000, "vad", 0.9))
    manager.handle_transcript(transcript("I want policy details", start_ms=1000, end_ms=1400))
    manager.handle_speech_stop(SpeechStop("call-turn", 1400, "vad", 0.9))
    turn = manager.emit_turn(timestamp_ms=1700)

    assert turn is not None
    assert turn.text == "I want policy details"
