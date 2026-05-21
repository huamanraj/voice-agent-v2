from voice_agent.contracts.audio import AudioFrame
from voice_agent.contracts.events import InterruptionStarted, PlaybackEvent
from voice_agent.core.playback.playback_tracker import PlaybackTracker


def test_checkpoint_played_marks_full_message_as_heard() -> None:
    tracker = PlaybackTracker(call_id="call-1")
    tracker.start_message(message_id="message-1", sequence_id=1, started_ms=1000)
    tracker.append_generated_text("message-1", "Your appointment is confirmed.")
    tracker.mark_audio_sent(
        AudioFrame(
            call_id="call-1",
            data=b"audio",
            timestamp_ms=1000,
            sample_rate=8000,
            codec="mulaw_8k",
            sequence_id=1,
            duration_ms=800,
            meta={"message_id": "message-1"},
        ),
        timestamp_ms=1000,
    )
    tracker.mark_checkpoint_sent("message-1", "message-1", timestamp_ms=1800)

    playback = tracker.handle_playback_event(
        PlaybackEvent(
            call_id="call-1",
            message_id="message-1",
            sequence_id=1,
            checkpoint_id="message-1",
            event_type="checkpoint_played",
            ts_ms=1900,
        )
    )

    assert playback is not None
    assert tracker.heard_text("message-1") == "Your appointment is confirmed."
    assert playback.checkpoints_played == ["message-1"]
    assert not playback.interrupted
    assert playback.checkpoint_ack_latency_ms == [100]


def test_estimated_playback_completion_marks_full_message_as_heard() -> None:
    tracker = PlaybackTracker(call_id="call-estimated")
    tracker.start_message(message_id="message-estimated", sequence_id=1, started_ms=1000)
    tracker.append_generated_text("message-estimated", "Your appointment is confirmed.")
    tracker.mark_audio_sent(
        AudioFrame(
            call_id="call-estimated",
            data=b"audio",
            timestamp_ms=1000,
            sample_rate=8000,
            codec="mulaw_8k",
            sequence_id=1,
            duration_ms=800,
            meta={"message_id": "message-estimated"},
        ),
        timestamp_ms=1000,
    )
    tracker.mark_checkpoint_sent("message-estimated", "message-estimated", timestamp_ms=1800)

    playback = tracker.mark_estimated_fully_played("message-estimated", timestamp_ms=2600)

    assert playback is not None
    assert tracker.heard_text("message-estimated") == "Your appointment is confirmed."


def test_interruption_estimates_partial_text_from_played_audio_ratio() -> None:
    tracker = PlaybackTracker(call_id="call-2")
    full_text = "Your appointment is confirmed for tomorrow at 5 PM."
    tracker.start_message(message_id="message-2", sequence_id=2, started_ms=1000)
    tracker.append_generated_text("message-2", full_text)
    tracker.mark_audio_sent(
        AudioFrame(
            call_id="call-2",
            data=b"audio",
            timestamp_ms=1000,
            sample_rate=8000,
            codec="mulaw_8k",
            sequence_id=2,
            duration_ms=1000,
            meta={"message_id": "message-2"},
        ),
        timestamp_ms=1000,
    )

    playback = tracker.mark_interrupted(
        InterruptionStarted(
            call_id="call-2",
            turn_id=1,
            sequence_id=2,
            reason="word_count_threshold",
            transcript="wait",
            ts_ms=1500,
        )
    )

    assert playback is not None
    heard = tracker.heard_text("message-2")
    assert heard
    assert heard != full_text
    assert full_text.startswith(heard)
    assert "5 PM" not in heard


def test_interruption_uses_word_timestamps_when_available() -> None:
    tracker = PlaybackTracker(call_id="call-3")
    tracker.start_message(message_id="message-3", sequence_id=3, started_ms=1000)
    tracker.append_generated_text("message-3", "hello world again")
    tracker.mark_audio_sent(
        AudioFrame(
            call_id="call-3",
            data=b"audio",
            timestamp_ms=1000,
            sample_rate=8000,
            codec="mulaw_8k",
            sequence_id=3,
            duration_ms=1000,
            meta={
                "message_id": "message-3",
                "word_timestamps": {
                    "words": ["hello", "world", "again"],
                    "end": [0.2, 0.5, 0.9],
                },
            },
        ),
        timestamp_ms=1000,
    )

    tracker.mark_interrupted(
        InterruptionStarted(
            call_id="call-3",
            turn_id=1,
            sequence_id=3,
            reason="word_count_threshold",
            transcript="stop",
            ts_ms=1600,
        )
    )

    assert tracker.heard_text("message-3") == "hello world"


def test_cleared_audio_marks_unfinished_messages_interrupted() -> None:
    tracker = PlaybackTracker(call_id="call-4")
    tracker.start_message(message_id="message-4", sequence_id=4, started_ms=1000)
    tracker.append_generated_text("message-4", "This answer is still playing.")
    tracker.mark_audio_sent(
        AudioFrame(
            call_id="call-4",
            data=b"audio",
            timestamp_ms=1000,
            sample_rate=8000,
            codec="mulaw_8k",
            sequence_id=4,
            duration_ms=1000,
            meta={"message_id": "message-4"},
        ),
        timestamp_ms=1000,
    )

    playback = tracker.handle_playback_event(
        PlaybackEvent(
            call_id="call-4",
            message_id="vobiz-clear",
            sequence_id=0,
            checkpoint_id=None,
            event_type="cleared",
            ts_ms=1200,
        )
    )

    assert playback is not None
    assert playback.message_id == "message-4"
    assert playback.interrupted
    assert tracker.heard_text("message-4")
