"""Expected answer hints used by turn detection."""

from dataclasses import dataclass
from typing import Literal

AnswerType = Literal["yes_no", "name", "number", "date", "confirmation", "free_text"]


@dataclass(frozen=True, slots=True)
class ExpectedAnswer:
    answer_type: AnswerType = "free_text"
    short_answer_allowed: bool = False
    min_words: int = 1

    def accepts_short_answer(self, word_count: int) -> bool:
        if not self.short_answer_allowed:
            return False
        return word_count >= self.min_words


FREE_TEXT_EXPECTED = ExpectedAnswer()
