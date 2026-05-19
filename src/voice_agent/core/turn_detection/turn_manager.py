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
    language: str | None = None
    confidence: float = 1.0
    emitted_turn: bool = False

    @property
    def text(self) -> str:
        final_text = " ".join(fragment for fragment in self.final_fragments if fragment).strip()
        return final_text or self.interim_text.strip()


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
    ) -> None:
        self.call_id = call_id
        self.settings = settings
        self.expected_answer = expected_answer
        self.smart_turn_runner = smart_turn_runner or HeuristicSmartTurnRunner()
        self.state = TurnState(call_id=call_id)

    def set_expected_answer(self, expected_answer: ExpectedAnswer) -> None:
        self.expected_answer = expected_answer

    def handle_speech_start(self, event: SpeechStart) -> None:
        self.state.is_user_speaking = True
        self.state.user_started_ms = event.ts_ms
        self.state.last_speech_ms = event.ts_ms
        self.state.vad_stop_seen = False
        self.state.emitted_turn = False

    def handle_speech_stop(self, event: SpeechStop) -> None:
        self.state.is_user_speaking = False
        self.state.last_speech_ms = event.ts_ms
        self.state.vad_stop_seen = event.source == "vad"
        if event.source == "stt":
            self.state.stt_speech_final_seen = True

    def handle_transcript(self, event: TranscriptEvent) -> None:
        event_ms = event.end_ms or event.start_ms or now_ms()
        if self.state.user_started_ms is None:
            self.state.user_started_ms = event.start_ms or event_ms
        self.state.last_transcript_ms = event_ms

        if event.is_final:
            text = event.text.strip()
            if text:
                self.state.final_fragments.append(text)
                self.state.last_final_ms = event_ms
                self.state.stt_speech_final_seen = True
                self.state.language = event.language
                self.state.confidence = event.confidence
                self._apply_smart_turn(self.state.text)
        else:
            self.state.interim_text = event.text.strip()

    def handle_smart_turn(self, result: SmartTurnResult) -> None:
        self.state.smart_turn_complete = result.is_complete
        self.state.smart_turn_confidence = result.confidence

    def evaluate(self, timestamp_ms: int | None = None) -> TurnDecision:
        ts_ms = timestamp_ms or now_ms()
        if self.state.emitted_turn:
            return TurnDecision(False, "already_emitted")
        if self.state.user_started_ms is None:
            return TurnDecision(False, "no_speech_start")

        text = self.state.text
        if not text:
            return TurnDecision(False, "no_text")

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

        if self.settings.smart_turn_enabled:
            if (
                self.state.smart_turn_complete
                and self.state.smart_turn_confidence >= self.settings.smart_turn_threshold
            ):
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
        self._reset_for_next_turn(keep_turn_id=True)
        return turn

    def _apply_smart_turn(self, text: str) -> None:
        decision: SmartTurnDecision = self.smart_turn_runner.classify(text)
        self.state.smart_turn_complete = decision.is_complete
        self.state.smart_turn_confidence = decision.confidence

    def _reset_for_next_turn(self, keep_turn_id: bool) -> None:
        turn_id = self.state.turn_id if keep_turn_id else 0
        self.state = TurnState(call_id=self.call_id, turn_id=turn_id)
