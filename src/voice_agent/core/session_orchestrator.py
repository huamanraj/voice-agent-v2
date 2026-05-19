"""Session orchestrator placeholder for Phase 3.

Phase 0/1 intentionally define contracts first; concrete orchestration starts
after mock providers exist.
"""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SessionOrchestrator:
    call_id: str
