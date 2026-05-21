"""Session construction boundary for future orchestration phases."""

from dataclasses import dataclass

from voice_agent.agents import AgentProfile, apply_agent_profile, resolve_agent_profile
from voice_agent.config import Settings
from voice_agent.contracts.ports import FinalStorePort, LLMPort, LiveStorePort, STTPort, TTSPort, TelephonyPort
from voice_agent.core.session_orchestrator import SessionOrchestrator, SessionProviders
from voice_agent.core.turn_detection.local_models import TurnDetectionModels
from voice_agent.factory.config_resolver import ProviderSelection, resolve_provider_selection
from voice_agent.factory.provider_registry import ProviderRegistry, create_default_registry


@dataclass(frozen=True, slots=True)
class SessionBlueprint:
    call_id: str
    providers: ProviderSelection
    agent: AgentProfile


@dataclass(frozen=True, slots=True)
class SessionProviderBundle:
    settings: Settings
    agent: AgentProfile
    stt: STTPort
    tts: TTSPort
    llm: LLMPort
    live_store: LiveStorePort | None
    final_store: FinalStorePort | None


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


def create_session_provider_bundle(
    settings: Settings,
    registry: ProviderRegistry | None = None,
    agent_overrides: dict[str, str] | None = None,
    agent_id: str | None = None,
) -> SessionProviderBundle:
    provider_registry = registry or create_default_registry()
    agent = resolve_agent_profile(settings, agent_id)
    runtime_settings = apply_agent_profile(settings, agent)
    selection = resolve_provider_selection(runtime_settings, agent_overrides)
    return SessionProviderBundle(
        settings=runtime_settings,
        agent=agent,
        stt=_create_provider(provider_registry, "stt", selection.stt, runtime_settings),
        tts=_create_provider(provider_registry, "tts", selection.tts, runtime_settings),
        llm=_create_provider(provider_registry, "llm", selection.llm, runtime_settings),
        live_store=_create_live_store(provider_registry, selection.live_store, runtime_settings),
        final_store=_create_final_store(provider_registry, selection.final_store, runtime_settings),
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
    bundle = create_session_provider_bundle(settings, provider_registry, agent_overrides, agent_id)
    selection = resolve_provider_selection(bundle.settings, agent_overrides)
    providers = SessionProviders(
        telephony=provider_registry.create("telephony", selection.telephony, call_id=call_id),
        stt=bundle.stt,
        tts=bundle.tts,
        llm=bundle.llm,
        live_store=bundle.live_store,
        final_store=bundle.final_store,
    )
    return SessionOrchestrator(
        call_id=call_id,
        providers=providers,
        settings=bundle.settings,
        agent=bundle.agent,
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
    provider_bundle: SessionProviderBundle | None = None,
) -> SessionOrchestrator:
    provider_registry = registry or create_default_registry()
    bundle = provider_bundle or create_session_provider_bundle(
        settings,
        provider_registry,
        agent_overrides,
        agent_id,
    )
    _bind_provider_call_id(bundle.stt, call_id)
    _bind_provider_call_id(bundle.tts, call_id)
    providers = SessionProviders(
        telephony=telephony,
        stt=bundle.stt,
        tts=bundle.tts,
        llm=bundle.llm,
        live_store=bundle.live_store,
        final_store=bundle.final_store,
    )
    return SessionOrchestrator(
        call_id=call_id,
        providers=providers,
        settings=bundle.settings,
        agent=bundle.agent,
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
        ("stt", "sarvam"),
        ("tts", "cartesia"),
        ("tts", "sarvam"),
        ("llm", "litellm"),
    }:
        return provider_registry.create(category, provider_name, settings=settings)
    return provider_registry.create(category, provider_name)


def _bind_provider_call_id(provider, call_id: str) -> None:
    if hasattr(provider, "call_id"):
        setattr(provider, "call_id", call_id)


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
