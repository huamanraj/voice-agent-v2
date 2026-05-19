"""Assistant response sequence validity tracking."""

from dataclasses import dataclass, field

SYSTEM_SEQUENCE_ID = -1


@dataclass(slots=True)
class SequenceManager:
    _current_sequence_id: int = 0
    _valid_sequence_ids: set[int] = field(default_factory=lambda: {SYSTEM_SEQUENCE_ID})
    _invalidated_sequence_ids: set[int] = field(default_factory=set)

    @property
    def current_sequence_id(self) -> int:
        return self._current_sequence_id

    def create_sequence(self) -> int:
        self._current_sequence_id += 1
        self._valid_sequence_ids.add(self._current_sequence_id)
        return self._current_sequence_id

    def is_valid(self, sequence_id: int | None) -> bool:
        if sequence_id is None:
            return False
        return sequence_id in self._valid_sequence_ids

    def invalidate(self, sequence_id: int, reason: str) -> bool:
        if sequence_id == SYSTEM_SEQUENCE_ID:
            return False
        was_valid = sequence_id in self._valid_sequence_ids
        self._valid_sequence_ids.discard(sequence_id)
        self._invalidated_sequence_ids.add(sequence_id)
        return was_valid

    def invalidate_pending(self, reason: str) -> set[int]:
        invalidated = {
            sequence_id
            for sequence_id in self._valid_sequence_ids
            if sequence_id != SYSTEM_SEQUENCE_ID
        }
        self._valid_sequence_ids = {SYSTEM_SEQUENCE_ID}
        self._invalidated_sequence_ids.update(invalidated)
        return invalidated

    def valid_sequences(self) -> frozenset[int]:
        return frozenset(self._valid_sequence_ids)

    def invalidated_sequences(self) -> frozenset[int]:
        return frozenset(self._invalidated_sequence_ids)
