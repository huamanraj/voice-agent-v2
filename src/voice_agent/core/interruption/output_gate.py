"""Outbound audio gate used to pause or block assistant playback."""

import asyncio
from dataclasses import dataclass, field
from enum import StrEnum


class OutputGateState(StrEnum):
    SEND = "send"
    WAIT = "wait"
    BLOCK = "block"


class OutputDecision(StrEnum):
    SEND = "send"
    WAIT = "wait"
    DROP = "drop"


@dataclass(slots=True)
class OutputGate:
    state: OutputGateState = OutputGateState.SEND
    blocked_sequence_ids: set[int] = field(default_factory=set)
    _condition: asyncio.Condition = field(default_factory=asyncio.Condition)

    def decision_for(self, sequence_id: int | None) -> OutputDecision:
        if sequence_id in self.blocked_sequence_ids:
            return OutputDecision.DROP
        if self.state == OutputGateState.BLOCK:
            return OutputDecision.DROP
        if self.state == OutputGateState.WAIT:
            return OutputDecision.WAIT
        return OutputDecision.SEND

    async def set_send(self) -> None:
        async with self._condition:
            self.state = OutputGateState.SEND
            self._condition.notify_all()

    async def set_wait(self) -> None:
        async with self._condition:
            self.state = OutputGateState.WAIT

    async def set_block(self) -> None:
        async with self._condition:
            self.state = OutputGateState.BLOCK
            self._condition.notify_all()

    async def block_sequence(self, sequence_id: int) -> None:
        async with self._condition:
            self.blocked_sequence_ids.add(sequence_id)
            self._condition.notify_all()

    async def block_sequences(self, sequence_ids: set[int]) -> None:
        async with self._condition:
            self.blocked_sequence_ids.update(sequence_ids)
            self._condition.notify_all()

    async def wait_until_released(self, timeout_seconds: float) -> OutputDecision:
        async with self._condition:
            if self.state != OutputGateState.WAIT:
                return OutputDecision.DROP if self.state == OutputGateState.BLOCK else OutputDecision.SEND

            try:
                await asyncio.wait_for(
                    self._condition.wait_for(lambda: self.state != OutputGateState.WAIT),
                    timeout=timeout_seconds,
                )
            except TimeoutError:
                return OutputDecision.WAIT

            return OutputDecision.DROP if self.state == OutputGateState.BLOCK else OutputDecision.SEND
