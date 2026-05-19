"""Session construction boundary for future orchestration phases."""

from dataclasses import dataclass

from voice_agent.config import Settings
from voice_agent.core.session_orchestrator import SessionOrchestrator, SessionProviders
from voice_agent.factory.config_resolver import ProviderSelection, resolve_provider_selection
from voice_agent.factory.provider_registry import ProviderRegistry, create_default_registry


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


def create_session_orchestrator(
    call_id: str,
    settings: Settings,
    registry: ProviderRegistry | None = None,
    agent_overrides: dict[str, str] | None = None,
) -> SessionOrchestrator:
    provider_registry = registry or create_default_registry()
    selection = resolve_provider_selection(settings, agent_overrides)
    providers = SessionProviders(
        telephony=provider_registry.create("telephony", selection.telephony, call_id=call_id),
        stt=provider_registry.create("stt", selection.stt),
        tts=provider_registry.create("tts", selection.tts),
        llm=provider_registry.create("llm", selection.llm),
        live_store=provider_registry.create("live_store", selection.live_store),
        final_store=provider_registry.create("final_store", selection.final_store),
    )
    return SessionOrchestrator(call_id=call_id, providers=providers, settings=settings)
