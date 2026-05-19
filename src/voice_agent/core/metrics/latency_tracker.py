"""Per-turn latency tracking and summary aggregation."""

from dataclasses import asdict, dataclass, field
from statistics import fmean


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

    def as_dict(self) -> dict[str, int | None]:
        return asdict(self)


@dataclass(slots=True)
class LatencySummary:
    avg_stt_first_interim_latency_ms: float | None = None
    avg_stt_final_latency_ms: float | None = None
    avg_end_of_turn_delay_ms: float | None = None
    avg_llm_first_token_ms: float | None = None
    avg_tts_first_audio_ms: float | None = None
    avg_voice_to_voice_ms: float | None = None
    avg_barge_in_clear_latency_ms: float | None = None
    avg_clear_ack_latency_ms: float | None = None
    interruption_count: int = 0
    agent_interrupted_user_count: int = 0
    audio_drop_count: int = 0
    provider_error_count: int = 0
    turns: list[dict[str, int | None]] = field(default_factory=list)

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


class LatencyTracker:
    def __init__(self) -> None:
        self.turns: dict[int, TurnLatency] = {}
        self._current_turn_id: int | None = None
        self.interruption_count = 0
        self.agent_interrupted_user_count = 0
        self.audio_drop_count = 0
        self.provider_error_count = 0

    def current_turn(self) -> TurnLatency:
        if self._current_turn_id is None:
            self._current_turn_id = 0
        return self.for_turn(self._current_turn_id)

    def for_turn(self, turn_id: int | None) -> TurnLatency:
        key = turn_id or self._current_turn_id or 0
        self._current_turn_id = key
        return self.turns.setdefault(key, TurnLatency())

    def mark_speech_start(self, turn_id: int | None, ts_ms: int) -> None:
        self.for_turn(turn_id).user_speech_start_ms = ts_ms

    def mark_speech_stop(self, turn_id: int | None, ts_ms: int) -> None:
        self.for_turn(turn_id).user_speech_end_ms = ts_ms

    def mark_transcript(self, turn_id: int | None, ts_ms: int, *, is_final: bool) -> None:
        turn = self.for_turn(turn_id)
        if is_final:
            turn.first_final_ms = turn.first_final_ms or ts_ms
        else:
            turn.first_interim_ms = turn.first_interim_ms or ts_ms

    def mark_end_of_turn(self, turn_id: int, ts_ms: int) -> None:
        self.for_turn(turn_id).end_of_turn_decision_ms = ts_ms
        self._current_turn_id = turn_id

    def mark_llm_start(self, turn_id: int | None, ts_ms: int) -> None:
        self.for_turn(turn_id).llm_request_start_ms = ts_ms

    def mark_llm_first_token(self, turn_id: int | None, ts_ms: int) -> None:
        turn = self.for_turn(turn_id)
        turn.llm_first_token_ms = turn.llm_first_token_ms or ts_ms

    def mark_llm_end(self, turn_id: int | None, ts_ms: int) -> None:
        self.for_turn(turn_id).llm_stream_end_ms = ts_ms

    def mark_tts_start(self, turn_id: int | None, ts_ms: int) -> None:
        turn = self.for_turn(turn_id)
        turn.tts_request_start_ms = turn.tts_request_start_ms or ts_ms

    def mark_tts_first_audio(self, turn_id: int | None, ts_ms: int) -> None:
        turn = self.for_turn(turn_id)
        turn.tts_first_audio_ms = turn.tts_first_audio_ms or ts_ms

    def mark_tts_end(self, turn_id: int | None, ts_ms: int) -> None:
        self.for_turn(turn_id).tts_stream_end_ms = ts_ms

    def mark_first_audio_sent(self, turn_id: int | None, ts_ms: int) -> None:
        turn = self.for_turn(turn_id)
        turn.first_audio_sent_ms = turn.first_audio_sent_ms or ts_ms

    def mark_first_audio_played(self, turn_id: int | None, ts_ms: int) -> None:
        turn = self.for_turn(turn_id)
        turn.first_audio_played_ms = turn.first_audio_played_ms or ts_ms

    def mark_final_audio_played(self, turn_id: int | None, ts_ms: int) -> None:
        self.for_turn(turn_id).final_audio_played_ms = ts_ms

    def mark_interruption(self, turn_id: int | None, ts_ms: int) -> None:
        self.interruption_count += 1
        self.for_turn(turn_id).interruption_start_ms = ts_ms

    def mark_clear_sent(self, turn_id: int | None, ts_ms: int) -> None:
        self.for_turn(turn_id).playback_clear_sent_ms = ts_ms

    def mark_clear_ack(self, turn_id: int | None, ts_ms: int) -> None:
        self.for_turn(turn_id).playback_clear_ack_ms = ts_ms

    def mark_audio_drop(self) -> None:
        self.audio_drop_count += 1

    def mark_provider_error(self) -> None:
        self.provider_error_count += 1

    def summary(self) -> LatencySummary:
        turns = list(self.turns.values())
        return LatencySummary(
            avg_stt_first_interim_latency_ms=_avg_delta(turns, "user_speech_start_ms", "first_interim_ms"),
            avg_stt_final_latency_ms=_avg_delta(turns, "user_speech_end_ms", "first_final_ms"),
            avg_end_of_turn_delay_ms=_avg_delta(turns, "user_speech_end_ms", "end_of_turn_decision_ms"),
            avg_llm_first_token_ms=_avg_delta(turns, "llm_request_start_ms", "llm_first_token_ms"),
            avg_tts_first_audio_ms=_avg_delta(turns, "tts_request_start_ms", "tts_first_audio_ms"),
            avg_voice_to_voice_ms=_avg_delta(turns, "user_speech_end_ms", "first_audio_sent_ms"),
            avg_barge_in_clear_latency_ms=_avg_delta(turns, "interruption_start_ms", "playback_clear_sent_ms"),
            avg_clear_ack_latency_ms=_avg_delta(turns, "playback_clear_sent_ms", "playback_clear_ack_ms"),
            interruption_count=self.interruption_count,
            agent_interrupted_user_count=self.agent_interrupted_user_count,
            audio_drop_count=self.audio_drop_count,
            provider_error_count=self.provider_error_count,
            turns=[turn.as_dict() for turn in turns],
        )


def _avg_delta(turns: list[TurnLatency], start_attr: str, end_attr: str) -> float | None:
    values: list[int] = []
    for turn in turns:
        start = getattr(turn, start_attr)
        end = getattr(turn, end_attr)
        if start is not None and end is not None and end >= start:
            values.append(end - start)
    return round(fmean(values), 2) if values else None
