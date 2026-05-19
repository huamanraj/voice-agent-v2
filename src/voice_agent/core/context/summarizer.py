"""Compact older heard conversation context for LLM prompts."""

from collections.abc import Iterable
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SummaryTurn:
    role: str
    content: str


class ConversationSummarizer:
    """Deterministic summarizer for old turns.

    This intentionally does not call an LLM in the hot path. It preserves only
    text that the caller actually said or heard, and trims from the front when
    the summary grows beyond the configured budget.
    """

    def __init__(self, max_chars: int = 1200) -> None:
        self.max_chars = max_chars

    def update(self, current_summary: str, turns: Iterable[SummaryTurn]) -> str:
        pieces = [current_summary.strip()] if current_summary.strip() else []
        for turn in turns:
            content = _clean_content(turn.content)
            if not content:
                continue
            role = "User" if turn.role == "user" else "Assistant"
            pieces.append(f"{role}: {content}")
        return _trim_summary("\n".join(pieces), self.max_chars)


def _clean_content(content: str) -> str:
    return " ".join(content.split())


def _trim_summary(summary: str, max_chars: int) -> str:
    if max_chars <= 0:
        return ""
    if len(summary) <= max_chars:
        return summary

    lines = summary.splitlines()
    while lines and len("\n".join(lines)) > max_chars:
        lines.pop(0)
    trimmed = "\n".join(lines)
    if len(trimmed) <= max_chars:
        return trimmed
    return trimmed[-max_chars:].lstrip()
