"""Resolve runtime provider selections from settings and agent overrides."""

from dataclasses import dataclass

from voice_agent.config import Settings


@dataclass(frozen=True, slots=True)
class ProviderSelection:
    telephony: str
    stt: str
    tts: str
    llm: str
    live_store: str
    final_store: str
    logger: str


def resolve_provider_selection(
    settings: Settings,
    agent_overrides: dict[str, str] | None = None,
) -> ProviderSelection:
    overrides = agent_overrides or {}
    return ProviderSelection(
        telephony=overrides.get("telephony_provider", settings.telephony_provider),
        stt=overrides.get("stt_provider", settings.stt_provider),
        tts=overrides.get("tts_provider", settings.tts_provider),
        llm=overrides.get("llm_provider", settings.llm_provider),
        live_store=overrides.get("live_store_provider", settings.live_store_provider),
        final_store=overrides.get("final_store_provider", settings.final_store_provider),
        logger=overrides.get("logger_provider", settings.logger_provider),
    )
