from voice_agent.contracts.events import UserTurnFinal
from voice_agent.core.context.context_manager import ContextManager
from voice_agent.core.playback.playback_tracker import MessagePlayback


def user_turn(turn_id: int, text: str, end_ms: int = 1000) -> UserTurnFinal:
    return UserTurnFinal(
        call_id="call-1",
        turn_id=turn_id,
        text=text,
        language="en-IN",
        confidence=0.9,
        start_ms=end_ms - 500,
        end_ms=end_ms,
    )


def test_context_uses_partial_heard_text_for_interrupted_assistant_turn() -> None:
    context = ContextManager(system_prompt="You are helpful.")
    context.append_user_turn(user_turn(1, "Book it for tomorrow."))
    context.start_assistant_turn(message_id="message-1", sequence_id=1)
    context.append_assistant_text("message-1", "Your appointment is confirmed for tomorrow at 5 PM.")
    context.update_assistant_from_playback(
        MessagePlayback(
            call_id="call-1",
            message_id="message-1",
            sequence_id=1,
            full_text="Your appointment is confirmed for tomorrow at 5 PM.",
            audio_ms_sent=1000,
            started_ms=1000,
            interrupted_ms=1550,
            interrupted=True,
            word_timestamps={
                "words": ["Your", "appointment", "is", "confirmed", "for", "tomorrow", "at", "5", "PM"],
                "end": [0.1, 0.25, 0.35, 0.5, 0.62, 0.75, 0.84, 0.92, 1.0],
            },
        )
    )

    messages = context.build_llm_messages(user_turn(2, "Actually make it Friday.", end_ms=2000))

    assistant_messages = [message["content"] for message in messages if message["role"] == "assistant"]
    assert assistant_messages == ["Your appointment is confirmed [interrupted]"]
    assert "tomorrow at 5 PM" not in assistant_messages[0]


def test_unplayed_generated_text_is_not_added_to_llm_history() -> None:
    context = ContextManager(system_prompt="You are helpful.")
    context.append_user_turn(user_turn(1, "What happened?"))
    context.start_assistant_turn(message_id="message-1", sequence_id=1)
    context.append_assistant_text("message-1", "This was generated but never played.")

    messages = context.build_llm_messages(user_turn(2, "Hello?", end_ms=2000))

    assert {"role": "assistant", "content": "This was generated but never played."} not in messages
    assert messages[-1] == {"role": "user", "content": "Hello?"}


def test_context_includes_known_slots_when_set() -> None:
    context = ContextManager(system_prompt="You are helpful.")
    context.slots.update("appointment_date", "Friday", confidence=0.95, source="listener")

    messages = context.build_llm_messages(user_turn(1, "What day is it booked for?"))

    assert {"role": "system", "content": "Known call details:\nappointment_date: Friday"} in messages


def test_old_context_summary_preserves_heard_text_only() -> None:
    context = ContextManager(system_prompt="You are helpful.", max_recent_turns=1)
    context.append_user_turn(user_turn(1, "First question.", end_ms=1000))
    context.start_assistant_turn(message_id="message-1", sequence_id=1)
    context.update_assistant_from_playback(
        MessagePlayback(
            call_id="call-1",
            message_id="message-1",
            sequence_id=1,
            full_text="Heard part plus hidden tail",
            audio_ms_sent=1000,
            started_ms=1000,
            interrupted_ms=1500,
            interrupted=True,
            word_timestamps={"words": ["Heard", "part", "plus", "hidden", "tail"], "end": [0.1, 0.3, 0.6, 0.8, 1.0]},
        )
    )
    context.append_user_turn(user_turn(2, "Second question.", end_ms=2000))
    context.start_assistant_turn(message_id="message-2", sequence_id=2)

    messages = context.build_llm_messages()
    summary = next(message["content"] for message in messages if message["content"].startswith("Earlier call context:"))

    assert "First question." in summary
    assert "Heard part [interrupted]" in summary
    assert "hidden tail" not in summary
