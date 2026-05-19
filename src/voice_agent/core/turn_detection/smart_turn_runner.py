"""Smart-turn runner interface and lightweight heuristic fallback."""

from dataclasses import dataclass

from voice_agent.core.turn_detection.rules import (
    ends_with_incomplete_connector,
    has_terminal_punctuation,
    is_complete_short_answer,
    word_count,
)


@dataclass(frozen=True, slots=True)
class SmartTurnDecision:
    is_complete: bool
    confidence: float
    reason: str


class HeuristicSmartTurnRunner:
    def classify(self, text: str) -> SmartTurnDecision:
        if not text.strip():
            return SmartTurnDecision(False, 0.0, "empty_text")
        if ends_with_incomplete_connector(text):
            return SmartTurnDecision(False, 0.85, "incomplete_connector")
        if is_complete_short_answer(text):
            return SmartTurnDecision(False, 0.6, "short_answer_requires_expected_context")
        if has_terminal_punctuation(text):
            return SmartTurnDecision(True, 0.75, "terminal_punctuation")
        if word_count(text) >= 5:
            return SmartTurnDecision(True, 0.65, "word_count_heuristic")
        return SmartTurnDecision(False, 0.55, "low_confidence_fragment")
