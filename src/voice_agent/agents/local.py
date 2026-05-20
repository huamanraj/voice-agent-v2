"""Local file-backed agent adapter.

The adapter keeps the call pipeline independent from where agent profiles live.
Today it reads JSON from disk; later the same boundary can load profiles from a
database without changing the orchestrator.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from voice_agent.config import Settings
from voice_agent.agents.profile import AgentProfile, fallback_profile, profile_from_mapping


class LocalAgentAdapter:
    def __init__(self, settings: Settings, *, path: str | Path | None = None) -> None:
        self.settings = settings
        self.path = Path(path or settings.agent_config_path)

    def get(self, agent_id: str | None = None) -> AgentProfile:
        payload = self._load_payload()
        agents = self._agents_from_payload(payload)
        requested_id = agent_id or self.settings.default_agent_id or self._default_agent_id(payload)

        if not agents:
            return fallback_profile(self.settings, requested_id)
        if requested_id not in agents:
            available = ", ".join(sorted(agents))
            raise LookupError(f"Agent '{requested_id}' is not configured. Available agents: {available}")
        return profile_from_mapping(requested_id, agents[requested_id], self.settings)

    def _load_payload(self) -> dict[str, Any]:
        if not self.path.exists():
            return {}
        try:
            loaded = json.loads(self.path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid agent config JSON at {self.path}: {exc}") from exc
        if not isinstance(loaded, dict):
            raise ValueError(f"Agent config at {self.path} must be a JSON object.")
        return loaded

    def _default_agent_id(self, payload: dict[str, Any]) -> str | None:
        value = payload.get("default_agent_id")
        return str(value).strip() if value else None

    def _agents_from_payload(self, payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
        agents = payload.get("agents")
        if isinstance(agents, dict):
            return {
                str(agent_id): agent_payload
                for agent_id, agent_payload in agents.items()
                if isinstance(agent_payload, dict)
            }
        if isinstance(agents, list):
            by_id: dict[str, dict[str, Any]] = {}
            for agent_payload in agents:
                if not isinstance(agent_payload, dict):
                    continue
                agent_id = agent_payload.get("id")
                if agent_id:
                    by_id[str(agent_id)] = agent_payload
            return by_id
        return {}


def resolve_agent_profile(settings: Settings, agent_id: str | None = None) -> AgentProfile:
    return LocalAgentAdapter(settings).get(agent_id)
