from voice_agent.core.metrics.latency_tracker import LatencyTracker


def test_latency_tracker_builds_turn_summary() -> None:
    tracker = LatencyTracker()
    tracker.mark_speech_start(1, 1000)
    tracker.mark_transcript(1, 1300, is_final=False)
    tracker.mark_speech_stop(1, 1500)
    tracker.mark_transcript(1, 1700, is_final=True)
    tracker.mark_end_of_turn(1, 1900)
    tracker.mark_llm_start(1, 2000)
    tracker.mark_llm_first_token(1, 2600)
    tracker.mark_tts_start(1, 2700)
    tracker.mark_tts_first_audio(1, 3000)
    tracker.mark_first_audio_sent(1, 3100)
    tracker.mark_interruption(1, 3300)
    tracker.mark_clear_sent(1, 3380)
    tracker.mark_clear_ack(1, 3420)
    tracker.mark_audio_drop()
    tracker.mark_provider_error()

    summary = tracker.summary().as_dict()

    assert summary["avg_stt_first_interim_latency_ms"] == 300
    assert summary["avg_stt_final_latency_ms"] == 200
    assert summary["avg_end_of_turn_delay_ms"] == 400
    assert summary["avg_llm_first_token_ms"] == 600
    assert summary["avg_tts_first_audio_ms"] == 300
    assert summary["avg_voice_to_voice_ms"] == 1600
    assert summary["avg_barge_in_clear_latency_ms"] == 80
    assert summary["avg_clear_ack_latency_ms"] == 40
    assert summary["interruption_count"] == 1
    assert summary["audio_drop_count"] == 1
    assert summary["provider_error_count"] == 1
