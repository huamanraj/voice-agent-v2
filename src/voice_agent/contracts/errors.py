"""Error contracts."""

from dataclasses import dataclass, field
from typing import Any


class VoiceAgentError(Exception):
    """Base exception for expected voice agent failures."""


@dataclass(frozen=True, slots=True)
class ProviderErrorInfo:
    provider: str
    error_type: str
    message: str
    retryable: bool
    error_code: str | None = None
    details: dict[str, Any] = field(default_factory=dict)
