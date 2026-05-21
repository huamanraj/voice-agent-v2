"""Provider-neutral user turn detection."""

from dataclasses import dataclass, field

from voice_agent.config import Settings
from voice_agent.contracts.events import (
    SmartTurnResult,
    SpeechStart,
    SpeechStop,
    TranscriptEvent,
    UserTurnFinal,
)
from voice_agent.contracts.packets import now_ms
from voice_agent.core.turn_detection.expected_answer import (
    FREE_TEXT_EXPECTED,
    ExpectedAnswer,
)
from voice_agent.core.turn_detection.rules import (
    ends_with_incomplete_connector,
    is_complete_short_answer,
    normalize_text,
    word_count,
)
from voice_agent.core.turn_detection.smart_turn_runner import (
    HeuristicSmartTurnRunner,
    SmartTurnDecision,
)


@dataclass(slots=True)
class TurnState:
    call_id: str
    turn_id: int = 0
    is_user_speaking: bool = False
    user_started_ms: int | None = None
    last_speech_ms: int | None = None
    last_transcript_ms: int | None = None
    interim_text: str = ""
    final_fragments: list[str] = field(default_factory=list)
    last_final_ms: int | None = None
    stt_speech_final_seen: bool = False
    vad_stop_seen: bool = False
    smart_turn_complete: bool = False
    smart_turn_confidence: float = 0.0
    smart_turn_ms: int | None = None
    smart_turn_skipped: bool = False
    language: str | None = None
    confidence: float = 1.0
    emitted_turn: bool = False

    @property
    def final_text(self) -> str:
        return " ".join(fragment for fragment in self.final_fragments if fragment).strip()

    @property
    def text(self) -> str:
        return merge_turn_text(self.final_text, self.interim_text)

    @property
    def has_final_text(self) -> bool:
        return any(fragment.strip() for fragment in self.final_fragments)

    @property
    def has_unfinalized_interim_tail(self) -> bool:
        if not self.interim_text.strip():
            return False
        if not self.final_text:
            return True
        return normalize_text(self.text) != normalize_text(self.final_text)


@dataclass(frozen=True, slots=True)
class TurnDecision:
    should_emit: bool
    reason: str


class TurnManager:
    def __init__(
        self,
        call_id: str,
        settings: Settings,
        expected_answer: ExpectedAnswer = FREE_TEXT_EXPECTED,
        smart_turn_runner: HeuristicSmartTurnRunner | None = None,
        smart_turn_available: bool | None = None,
    ) -> None:
        self.call_id = call_id
        self.settings = settings
        self.expected_answer = expected_answer
        self.smart_turn_runner = smart_turn_runner
        self.smart_turn_available = (
            settings.smart_turn_enabled if smart_turn_available is None else smart_turn_available
        )
        self.state = TurnState(call_id=call_id)
        self._last_emitted_text: str = ""
        self._last_emitted_ms: int | None = None
        self._last_emitted_turn: UserTurnFinal | None = None

    @property
    def uses_smart_turn(self) -> bool:
        return self.settings.smart_turn_enabled and self.smart_turn_available

    def set_expected_answer(self, expected_answer: ExpectedAnswer) -> None:
        self.expected_answer = expected_answer

    def discard_current_turn(self) -> None:
        self._reset_for_next_turn(keep_turn_id=True)

    def skip_smart_turn_for_current_turn(self) -> None:
        self.state.smart_turn_skipped = True
        self.state.smart_turn_complete = False
        self.state.smart_turn_confidence = 0.0
        self.state.smart_turn_ms = None

    def handle_speech_start(self, event: SpeechStart) -> None:
        self.state.is_user_speaking = True
        if self.state.user_started_ms is None:
            self.state.user_started_ms = event.ts_ms
        self.state.last_speech_ms = event.ts_ms
        self.state.vad_stop_seen = False
        self.state.smart_turn_skipped = False
        self.state.smart_turn_complete = False
        self.state.smart_turn_confidence = 0.0
        self.state.smart_turn_ms = None
        self.state.emitted_turn = False

    def handle_speech_stop(self, event: SpeechStop) -> None:
        self.state.is_user_speaking = False
        self.state.last_speech_ms = event.ts_ms
        self.state.vad_stop_seen = event.source == "vad"
        if event.source == "stt":
            self.state.stt_speech_final_seen = True

    def handle_transcript(self, event: TranscriptEvent, *, received_ms: int | None = None) -> None:
        event_ms = received_ms or event.end_ms or event.start_ms or now_ms()
        if self.state.user_started_ms is None and self._is_late_duplicate(event.text, event_ms):
            return
        if self.state.user_started_ms is None:
            self.state.user_started_ms = received_ms or event.start_ms or event_ms
        self.state.last_transcript_ms = event_ms

        if event.is_final:
            text = event.text.strip()
            if not text:
                self.state.stt_speech_final_seen = True
                self.state.language = event.language or self.state.language
                self.state.confidence = event.confidence
                return
            if text:
                is_new_fragment = not self.state.final_fragments or (
                    normalize_text(self.state.final_fragments[-1]) != normalize_text(text)
                )
                if is_new_fragment:
                    self.state.final_fragments.append(text)
                self.state.last_final_ms = event_ms
                self.state.interim_text = ""
                self.state.stt_speech_final_seen = True
                self.state.language = event.language
                self.state.confidence = event.confidence
                if self.smart_turn_runner is not None:
                    self._apply_smart_turn(self.state.text)
        else:
            self.state.interim_text = event.text.strip()

    def handle_smart_turn(self, result: SmartTurnResult) -> None:
        self.state.smart_turn_complete = result.is_complete
        self.state.smart_turn_confidence = result.confidence
        self.state.smart_turn_ms = now_ms()

    def evaluate(self, timestamp_ms: int | None = None) -> TurnDecision:
        ts_ms = timestamp_ms or now_ms()
        if self.state.emitted_turn:
            return TurnDecision(False, "already_emitted")
        if self.state.user_started_ms is None:
            return TurnDecision(False, "no_speech_start")

        text = self.state.text
        if not text:
            return TurnDecision(False, "no_text")
        if not self.state.has_final_text or self.state.has_unfinalized_interim_tail:
            transcript_age_ms = max(0, ts_ms - (self.state.last_transcript_ms or ts_ms))
            if transcript_age_ms < self.settings.max_silence_before_force_end_ms:
                return TurnDecision(False, "waiting_for_final_transcript")

        speech_duration_ms = max(0, (self.state.last_speech_ms or ts_ms) - self.state.user_started_ms)
        if speech_duration_ms < self.settings.min_user_speech_ms:
            return TurnDecision(False, "speech_too_short")

        silence_start_ms = self.state.last_speech_ms or self.state.last_transcript_ms or ts_ms
        silence_ms = max(0, ts_ms - silence_start_ms)
        if silence_ms < self.settings.min_silence_for_turn_end_ms:
            return TurnDecision(False, "not_enough_silence")

        text_word_count = word_count(text)
        if is_complete_short_answer(text) and self.expected_answer.accepts_short_answer(text_word_count):
            return TurnDecision(True, "expected_short_answer")

        if (
            ends_with_incomplete_connector(text)
            and silence_ms < self.settings.max_silence_before_force_end_ms
        ):
            return TurnDecision(False, "incomplete_connector")

        if self.uses_smart_turn and not self.state.smart_turn_skipped:
            if (
                self.state.smart_turn_complete
                and self.state.smart_turn_confidence >= self.settings.smart_turn_threshold
            ):
                if self._inside_end_of_turn_grace(ts_ms):
                    return TurnDecision(False, "end_of_turn_grace")
                return TurnDecision(True, "smart_turn_complete")
            if silence_ms >= self.settings.max_silence_before_force_end_ms:
                return TurnDecision(True, "max_silence_force_end")
            return TurnDecision(False, "smart_turn_incomplete")

        if self.state.vad_stop_seen or self.state.stt_speech_final_seen:
            return TurnDecision(True, "speech_final_seen")
        return TurnDecision(False, "no_end_signal")

    def emit_turn(self, timestamp_ms: int | None = None) -> UserTurnFinal | None:
        decision = self.evaluate(timestamp_ms)
        if not decision.should_emit:
            return None
        return self._build_turn(timestamp_ms)

    def force_emit(self, reason: str, timestamp_ms: int | None = None) -> UserTurnFinal | None:
        if not self.state.text:
            return None
        return self._build_turn(timestamp_ms)

    def _build_turn(self, timestamp_ms: int | None = None) -> UserTurnFinal:
        self.state.turn_id += 1
        self.state.emitted_turn = True
        turn = UserTurnFinal(
            call_id=self.call_id,
            turn_id=self.state.turn_id,
            text=self.state.text,
            language=self.state.language,
            confidence=self.state.confidence,
            start_ms=self.state.user_started_ms,
            end_ms=timestamp_ms or now_ms(),
        )
        self._last_emitted_text = _dedupe_text(turn.text)
        self._last_emitted_ms = turn.end_ms
        self._last_emitted_turn = turn
        self._reset_for_next_turn(keep_turn_id=True)
        return turn

    def amend_last_emitted_turn(
        self,
        event: TranscriptEvent,
        *,
        received_ms: int | None = None,
    ) -> UserTurnFinal | None:
        if self._last_emitted_turn is None or self._last_emitted_ms is None:
            return None
        event_ms = received_ms or event.end_ms or event.start_ms or now_ms()
        if event_ms - self._last_emitted_ms > self.settings.max_silence_before_force_end_ms:
            return None
        if self._is_late_duplicate(event.text, event_ms):
            return None

        text = event.text.strip()
        if not text:
            return None

        amended_text = merge_turn_text(self._last_emitted_turn.text, text)
        if _dedupe_text(amended_text) == self._last_emitted_text:
            return None

        turn = UserTurnFinal(
            call_id=self.call_id,
            turn_id=self._last_emitted_turn.turn_id,
            text=amended_text,
            language=event.language or self._last_emitted_turn.language,
            confidence=event.confidence,
            start_ms=self._last_emitted_turn.start_ms,
            end_ms=event_ms,
        )
        self._last_emitted_turn = turn
        self._last_emitted_text = _dedupe_text(turn.text)
        self._last_emitted_ms = event_ms
        return turn

    def _apply_smart_turn(self, text: str) -> None:
        decision: SmartTurnDecision = self.smart_turn_runner.classify(text)
        self.state.smart_turn_complete = decision.is_complete
        self.state.smart_turn_confidence = decision.confidence
        self.state.smart_turn_ms = now_ms()

    def _reset_for_next_turn(self, keep_turn_id: bool) -> None:
        turn_id = self.state.turn_id if keep_turn_id else 0
        self.state = TurnState(call_id=self.call_id, turn_id=turn_id)

    def _is_late_duplicate(self, text: str, event_ms: int) -> bool:
        if not self._last_emitted_text or self._last_emitted_ms is None:
            return False
        if event_ms - self._last_emitted_ms > self.settings.max_silence_before_force_end_ms:
            return False
        return _dedupe_text(text) == self._last_emitted_text

    def _inside_end_of_turn_grace(self, ts_ms: int) -> bool:
        if self.settings.end_of_turn_grace_ms <= 0 or self.state.smart_turn_ms is None:
            return False
        return ts_ms - self.state.smart_turn_ms < self.settings.end_of_turn_grace_ms


def merge_turn_text(existing: str, addition: str) -> str:
    existing = existing.strip()
    addition = addition.strip()
    if not existing:
        return addition
    if not addition:
        return existing

    normalized_existing = normalize_text(existing).strip(".,!?à¥¤ ")
    normalized_addition = normalize_text(addition).strip(".,!?à¥¤ ")
    if normalized_addition in normalized_existing:
        return existing
    if normalized_existing in normalized_addition:
        return addition

    existing_parts = existing.split()
    addition_parts = addition.split()
    existing_norm = [normalize_text(part).strip(".,!?à¥¤ ") for part in existing_parts]
    addition_norm = [normalize_text(part).strip(".,!?à¥¤ ") for part in addition_parts]
    max_overlap = min(len(existing_norm), len(addition_norm))
    for overlap in range(max_overlap, 0, -1):
        if existing_norm[-overlap:] == addition_norm[:overlap]:
            return " ".join(existing_parts + addition_parts[overlap:]).strip()
    return f"{existing} {addition}".strip()


def _dedupe_text(text: str) -> str:
    return normalize_text(text).strip(".,!?। ")
