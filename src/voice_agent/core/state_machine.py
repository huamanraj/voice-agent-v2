"""Call state definitions."""

from enum import StrEnum


class CallState(StrEnum):
    NEW = "new"
    STARTING = "starting"
    LISTENING = "listening"
    THINKING = "thinking"
    SPEAKING = "speaking"
    INTERRUPTED = "interrupted"
    CLOSING = "closing"
    CLOSED = "closed"
