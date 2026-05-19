"""Helpers for post-call transcript formatting."""

from typing import Any


def transcript_text(final_record: dict[str, Any]) -> str:
    lines: list[str] = []
    for turn in final_record.get("turns", []):
        speaker = str(turn.get("speaker", "unknown")).title()
        text = turn.get("heard_text") or turn.get("text") or ""
        if text:
            suffix = " [interrupted]" if turn.get("interrupted") else ""
            lines.append(f"{speaker}: {text}{suffix}")
    return "\n".join(lines)
