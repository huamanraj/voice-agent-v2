"""Session construction boundary for future orchestration phases."""

from dataclasses import dataclass

from voice_agent.agents import AgentProfile, apply_agent_profile, resolve_agent_profile
from voice_agent.config import Settings
from voice_agent.contracts.ports import TelephonyPort
from voice_agent.core.session_orchestrator import SessionOrchestrator, SessionProviders
from voice_agent.core.turn_detection.local_models import TurnDetectionModels
from voice_agent.factory.config_resolver import ProviderSelection, resolve_provider_selection
from voice_agent.factory.provider_registry import ProviderRegistry, create_default_registry


@dataclass(frozen=True, slots=True)
class SessionBlueprint:
    call_id: str
    providers: ProviderSelection
    agent: AgentProfile


def build_session_blueprint(
    call_id: str,
    settings: Settings,
    agent_overrides: dict[str, str] | None = None,
    agent_id: str | None = None,
) -> SessionBlueprint:
    agent = resolve_agent_profile(settings, agent_id)
    runtime_settings = apply_agent_profile(settings, agent)
    return SessionBlueprint(
        call_id=call_id,
        providers=resolve_provider_selection(runtime_settings, agent_overrides),
        agent=agent,
    )


def create_session_orchestrator(
    call_id: str,
    settings: Settings,
    registry: ProviderRegistry | None = None,
    agent_overrides: dict[str, str] | None = None,
    agent_id: str | None = None,
    turn_detection_models: TurnDetectionModels | None = None,
) -> SessionOrchestrator:
    provider_registry = registry or create_default_registry()
    agent = resolve_agent_profile(settings, agent_id)
    runtime_settings = apply_agent_profile(settings, agent)
    selection = resolve_provider_selection(runtime_settings, agent_overrides)
    providers = SessionProviders(
        telephony=provider_registry.create("telephony", selection.telephony, call_id=call_id),
        stt=_create_provider(provider_registry, "stt", selection.stt, runtime_settings),
        tts=_create_provider(provider_registry, "tts", selection.tts, runtime_settings),
        llm=_create_provider(provider_registry, "llm", selection.llm, runtime_settings),
        live_store=_create_live_store(provider_registry, selection.live_store, runtime_settings),
        final_store=_create_final_store(provider_registry, selection.final_store, runtime_settings),
    )
    return SessionOrchestrator(
        call_id=call_id,
        providers=providers,
        settings=runtime_settings,
        agent=agent,
        turn_detection_models=turn_detection_models,
    )


def create_session_orchestrator_with_telephony(
    call_id: str,
    settings: Settings,
    telephony: TelephonyPort,
    registry: ProviderRegistry | None = None,
    agent_overrides: dict[str, str] | None = None,
    agent_id: str | None = None,
    turn_detection_models: TurnDetectionModels | None = None,
) -> SessionOrchestrator:
    provider_registry = registry or create_default_registry()
    agent = resolve_agent_profile(settings, agent_id)
    runtime_settings = apply_agent_profile(settings, agent)
    selection = resolve_provider_selection(runtime_settings, agent_overrides)
    providers = SessionProviders(
        telephony=telephony,
        stt=_create_provider(provider_registry, "stt", selection.stt, runtime_settings),
        tts=_create_provider(provider_registry, "tts", selection.tts, runtime_settings),
        llm=_create_provider(provider_registry, "llm", selection.llm, runtime_settings),
        live_store=_create_live_store(provider_registry, selection.live_store, runtime_settings),
        final_store=_create_final_store(provider_registry, selection.final_store, runtime_settings),
    )
    return SessionOrchestrator(
        call_id=call_id,
        providers=providers,
        settings=runtime_settings,
        agent=agent,
        turn_detection_models=turn_detection_models,
    )


def _create_provider(
    provider_registry: ProviderRegistry,
    category: str,
    provider_name: str,
    settings: Settings,
):
    if (category, provider_name) in {
        ("stt", "deepgram"),
        ("tts", "cartesia"),
        ("llm", "litellm"),
    }:
        return provider_registry.create(category, provider_name, settings=settings)
    return provider_registry.create(category, provider_name)


def _create_live_store(provider_registry: ProviderRegistry, provider_name: str, settings: Settings):
    if provider_name == "redis":
        return provider_registry.create(
            "live_store",
            provider_name,
            redis_url=settings.redis_url,
            ttl_seconds=settings.redis_live_ttl_seconds,
        )
    return provider_registry.create("live_store", provider_name)


def _create_final_store(provider_registry: ProviderRegistry, provider_name: str, settings: Settings):
    if provider_name == "postgres":
        return provider_registry.create(
            "final_store",
            provider_name,
            dsn=settings.postgres_dsn,
            connect_timeout_seconds=settings.postgres_connect_timeout_seconds,
            save_timeout_seconds=settings.postgres_save_timeout_seconds,
            retry_dir=settings.postgres_retry_dir,
        )
    return provider_registry.create("final_store", provider_name)
