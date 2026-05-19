"""Playback tracking contracts."""

from dataclasses import dataclass
from enum import StrEnum


class PlaybackStatus(StrEnum):
    PENDING = "pending"
    SENT = "sent"
    CHECKPOINT_PLAYED = "checkpoint_played"
    FULLY_PLAYED = "fully_played"
    CLEARED = "cleared"


@dataclass(slots=True)
class PlaybackSegment:
    call_id: str
    message_id: str
    sequence_id: int
    checkpoint_id: str | None
    text: str | None
    status: PlaybackStatus = PlaybackStatus.PENDING
