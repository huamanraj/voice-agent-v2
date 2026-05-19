"""Phrase-level interruption classification."""

from dataclasses import dataclass

from voice_agent.core.turn_detection.rules import normalize_text, word_count


@dataclass(frozen=True, slots=True)
class PhraseDecision:
    text: str
    normalized_text: str
    word_count: int
    is_force_interrupt: bool = False
    is_backchannel: bool = False
    matched_phrase: str | None = None


class PhraseClassifier:
    def __init__(
        self,
        force_interrupt_phrases: tuple[str, ...],
        backchannel_phrases: tuple[str, ...],
    ) -> None:
        self.force_interrupt_phrases = self._normalize_phrases(force_interrupt_phrases)
        self.backchannel_phrases = self._normalize_phrases(backchannel_phrases)

    def decide(self, text: str) -> PhraseDecision:
        normalized = normalize_text(text).strip(".,!?। ")
        matched_force = self._match_phrase(normalized, self.force_interrupt_phrases)
        matched_backchannel = self._match_phrase(normalized, self.backchannel_phrases)
        return PhraseDecision(
            text=text,
            normalized_text=normalized,
            word_count=word_count(normalized),
            is_force_interrupt=matched_force is not None,
            is_backchannel=matched_force is None and matched_backchannel is not None,
            matched_phrase=matched_force or matched_backchannel,
        )

    @staticmethod
    def _normalize_phrases(phrases: tuple[str, ...]) -> frozenset[str]:
        return frozenset(normalize_text(phrase).strip(".,!?। ") for phrase in phrases)

    @staticmethod
    def _match_phrase(text: str, phrases: frozenset[str]) -> str | None:
        if not text:
            return None
        for phrase in sorted(phrases, key=len, reverse=True):
            if text == phrase:
                return phrase
            if text.startswith(f"{phrase} "):
                return phrase
        return None
