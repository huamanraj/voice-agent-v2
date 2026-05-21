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

    assert messages[0]["role"] == "system"
    prompt = messages[0]["content"]
    assert len(messages) == 1
    assert "Agent: Your appointment is confirmed [interrupted]" in prompt
    assert 'User interrupted with:\n"Actually make it Friday."' in prompt
    assert "Do not restart the interrupted sentence." in prompt
    assert "tomorrow at 5 PM" not in prompt


def test_unplayed_generated_text_is_not_added_to_llm_history() -> None:
    context = ContextManager(system_prompt="You are helpful.")
    context.append_user_turn(user_turn(1, "What happened?"))
    context.start_assistant_turn(message_id="message-1", sequence_id=1)
    context.append_assistant_text("message-1", "This was generated but never played.")

    messages = context.build_llm_messages(user_turn(2, "Hello?", end_ms=2000))

    prompt = messages[0]["content"]
    assert "This was generated but never played." not in prompt
    assert "User: Hello?" in prompt
    assert 'The user\'s last message: "Hello?"' in prompt


def test_context_includes_known_slots_when_set() -> None:
    context = ContextManager(system_prompt="You are helpful.")
    context.slots.update("appointment_date", "Friday", confidence=0.95, source="listener")

    messages = context.build_llm_messages(user_turn(1, "What day is it booked for?"))

    assert "Known call details:\nappointment_date: Friday" in messages[0]["content"]


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
    prompt = messages[0]["content"]

    assert "Older call summary:" in prompt
    assert "First question." in prompt
    assert "Heard part [interrupted]" in prompt
    assert "hidden tail" not in prompt


def test_context_prompt_combines_history_latest_context_and_call_rules() -> None:
    context = ContextManager(system_prompt="You are helpful.")
    context.append_user_turn(user_turn(1, "Hello"))
    context.start_assistant_turn(message_id="message-1", sequence_id=1)
    context.update_assistant_from_playback(
        MessagePlayback(
            call_id="call-1",
            message_id="message-1",
            sequence_id=1,
            full_text="Hi, how can I help?",
            audio_ms_sent=1000,
            started_ms=1000,
            fully_played_ms=2000,
        )
    )

    messages = context.build_llm_messages(user_turn(2, "I need car insurance.", end_ms=3000))
    prompt = messages[0]["content"]

    assert messages == [{"role": "system", "content": prompt}]
    assert "# SYSTEM INSTRUCTIONS\nYou are helpful." in prompt
    assert "# CONVERSATION HISTORY" in prompt
    assert "User: Hello" in prompt
    assert "Agent: Hi, how can I help?" in prompt
    assert "User: I need car insurance." in prompt
    assert "# LATEST CONTEXT" in prompt
    assert 'The last thing you said: "Hi, how can I help?"' in prompt
    assert 'The user\'s last message: "I need car insurance."' in prompt
    assert "# COVERAGE CHECKLIST" in prompt
    assert "# WHEN TO END CALL" in prompt
    assert "# CLOSING LINE" in prompt
    assert "# GOODBYE RULES" in prompt
