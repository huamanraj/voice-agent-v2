"""Latency contracts for future metrics aggregation."""

from dataclasses import dataclass


@dataclass(slots=True)
class TurnLatency:
    user_speech_start_ms: int | None = None
    first_interim_ms: int | None = None
    first_final_ms: int | None = None
    user_speech_end_ms: int | None = None
    end_of_turn_decision_ms: int | None = None
    llm_request_start_ms: int | None = None
    llm_first_token_ms: int | None = None
    llm_stream_end_ms: int | None = None
    tts_request_start_ms: int | None = None
    tts_first_audio_ms: int | None = None
    tts_stream_end_ms: int | None = None
    first_audio_sent_ms: int | None = None
    first_audio_played_ms: int | None = None
    final_audio_played_ms: int | None = None
    interruption_start_ms: int | None = None
    playback_clear_sent_ms: int | None = None
    playback_clear_ack_ms: int | None = None
