"""Queue packet envelope used across the runtime."""

from dataclasses import dataclass, field
from time import time
from typing import Any


def now_ms() -> int:
    return int(time() * 1000)


@dataclass(slots=True)
class AgentPacket:
    packet_type: str
    call_id: str
    turn_id: int | None
    sequence_id: int | None
    request_id: str | None
    timestamp_ms: int
    data: dict[str, Any] = field(default_factory=dict)
    meta: dict[str, Any] = field(default_factory=dict)
    eos: bool = False

    @classmethod
    def eos_packet(cls, call_id: str, packet_type: str = "eos") -> "AgentPacket":
        return cls(
            packet_type=packet_type,
            call_id=call_id,
            turn_id=None,
            sequence_id=None,
            request_id=None,
            timestamp_ms=now_ms(),
            eos=True,
        )
