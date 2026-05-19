"""Transcript rules for robust end-of-turn decisions."""

import re

INCOMPLETE_ENDINGS = frozenset(
    {
        "aur",
        "ki",
        "ke",
        "to",
        "phir",
        "matlab",
        "jaise",
        "kyunki",
        "but",
        "and",
        "so",
        "because",
        "then",
        "actually",
    }
)

COMPLETE_SHORT_ANSWERS = frozenset(
    {
        "haan",
        "ha",
        "nahi",
        "nahin",
        "yes",
        "no",
        "ji",
        "ok",
        "okay",
        "theek hai",
        "thik hai",
        "kal",
        "aaj",
        "abhi",
    }
)

TERMINAL_PUNCTUATION = (".", "?", "!", "।")
_WORD_RE = re.compile(r"[\w']+", flags=re.UNICODE)


def normalize_text(text: str) -> str:
    return " ".join(text.casefold().strip().split())


def words(text: str) -> list[str]:
    return _WORD_RE.findall(normalize_text(text))


def word_count(text: str) -> int:
    return len(words(text))


def ends_with_incomplete_connector(text: str) -> bool:
    tokens = words(text)
    return bool(tokens and tokens[-1] in INCOMPLETE_ENDINGS)


def is_complete_short_answer(text: str) -> bool:
    normalized = normalize_text(text).strip(".,!?। ")
    return normalized in COMPLETE_SHORT_ANSWERS


def has_terminal_punctuation(text: str) -> bool:
    return normalize_text(text).endswith(TERMINAL_PUNCTUATION)
