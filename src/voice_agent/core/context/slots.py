"""Conversation slot tracking for structured call context."""

from dataclasses import dataclass
from typing import Any

from voice_agent.contracts.packets import now_ms


@dataclass(frozen=True, slots=True)
class SlotValue:
    name: str
    value: Any
    confidence: float
    source: str
    updated_ms: int


class SlotTracker:
    def __init__(self) -> None:
        self._slots: dict[str, SlotValue] = {}

    def update(
        self,
        name: str,
        value: Any,
        *,
        confidence: float = 1.0,
        source: str = "runtime",
        updated_ms: int | None = None,
    ) -> SlotValue:
        normalized_name = _normalize_name(name)
        if not normalized_name:
            raise ValueError("Slot name cannot be empty.")
        slot = SlotValue(
            name=normalized_name,
            value=value,
            confidence=max(0.0, min(1.0, confidence)),
            source=source,
            updated_ms=updated_ms or now_ms(),
        )
        self._slots[normalized_name] = slot
        return slot

    def get(self, name: str) -> SlotValue | None:
        return self._slots.get(_normalize_name(name))

    def remove(self, name: str) -> None:
        self._slots.pop(_normalize_name(name), None)

    def clear(self) -> None:
        self._slots.clear()

    def as_dict(self) -> dict[str, Any]:
        return {name: slot.value for name, slot in sorted(self._slots.items())}

    def to_prompt_text(self) -> str:
        lines: list[str] = []
        for name, slot in sorted(self._slots.items()):
            if slot.value is None or slot.value == "":
                continue
            lines.append(f"{name}: {slot.value}")
        return "\n".join(lines)

    def __bool__(self) -> bool:
        return bool(self._slots)


def _normalize_name(name: str) -> str:
    return "_".join(str(name).strip().lower().split())
