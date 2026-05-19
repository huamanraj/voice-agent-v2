"""Turn-related contracts."""

from dataclasses import dataclass, field


@dataclass(slots=True)
class TurnContext:
    call_id: str
    turn_id: int
    expected_answer_type: str | None = None
    language_hint: str | None = None
    meta: dict[str, str] = field(default_factory=dict)
