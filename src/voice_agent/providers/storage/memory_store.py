"""In-memory live, final, and conversation memory store."""

from copy import deepcopy
from typing import Any


class MemoryStore:
    provider_name = "memory"

    def __init__(self) -> None:
        self.call_states: dict[str, dict[str, Any]] = {}
        self.call_records: dict[str, dict[str, Any]] = {}
        self.memories: dict[str, list[dict[str, Any]]] = {}

    async def get_call_state(self, call_id: str) -> dict[str, Any] | None:
        state = self.call_states.get(call_id)
        return deepcopy(state) if state is not None else None

    async def set_call_state(self, call_id: str, state: dict[str, Any]) -> None:
        self.call_states[call_id] = deepcopy(state)

    async def delete_call_state(self, call_id: str) -> None:
        self.call_states.pop(call_id, None)

    async def save_call(self, call_id: str, record: dict[str, Any]) -> None:
        self.call_records[call_id] = deepcopy(record)

    async def load(self, call_id: str) -> list[dict[str, Any]]:
        return deepcopy(self.memories.get(call_id, []))

    async def append(self, call_id: str, item: dict[str, Any]) -> None:
        self.memories.setdefault(call_id, []).append(deepcopy(item))
