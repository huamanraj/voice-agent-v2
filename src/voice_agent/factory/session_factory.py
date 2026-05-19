"""Session construction boundary for future orchestration phases."""

from dataclasses import dataclass

from voice_agent.config import Settings
from voice_agent.factory.config_resolver import ProviderSelection, resolve_provider_selection


@dataclass(frozen=True, slots=True)
class SessionBlueprint:
    call_id: str
    providers: ProviderSelection


def build_session_blueprint(
    call_id: str,
    settings: Settings,
    agent_overrides: dict[str, str] | None = None,
) -> SessionBlueprint:
    return SessionBlueprint(
        call_id=call_id,
        providers=resolve_provider_selection(settings, agent_overrides),
    )
