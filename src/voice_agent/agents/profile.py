"""Agent profile models and settings projection."""

from dataclasses import dataclass, field
from typing import Any

from voice_agent.config import Settings


@dataclass(frozen=True, slots=True)
class AgentProviders:
    telephony: str | None = None
    stt: str | None = None
    tts: str | None = None
    llm: str | None = None
    live_store: str | None = None
    final_store: str | None = None
    logger: str | None = None


@dataclass(frozen=True, slots=True)
class AgentLLM:
    talker_model: str | None = None
    listener_model: str | None = None
    talker_max_tokens: int | None = None
    talker_temperature: float | None = None
    listener_max_tokens: int | None = None
    listener_temperature: float | None = None
    sentence_min_chars: int | None = None
    sentence_max_chars: int | None = None
    sentence_timeout_ms: int | None = None


@dataclass(frozen=True, slots=True)
class AgentSTT:
    language: str | None = None
    deepgram_model: str | None = None
    deepgram_endpointing_ms: int | None = None
    deepgram_utterance_end_ms: int | None = None
    sarvam_model: str | None = None
    sarvam_mode: str | None = None
    sarvam_high_vad_sensitivity: bool | None = None


@dataclass(frozen=True, slots=True)
class AgentTTS:
    voice: str | None = None
    language: str | None = None
    cartesia_voice_id: str | None = None
    cartesia_model: str | None = None
    cartesia_max_buffer_delay_ms: int | None = None
    sarvam_model: str | None = None


@dataclass(frozen=True, slots=True)
class AgentBehavior:
    interruption_enabled: bool | None = None
    min_interrupt_words: int | None = None
    hard_interrupt_after_audio_ms: int | None = None
    allow_interrupt_welcome_message: bool | None = None
    force_interrupt_phrases: tuple[str, ...] = field(default_factory=tuple)
    backchannel_phrases: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class AgentProfile:
    agent_id: str
    name: str
    system_prompt: str
    greeting: str | None = None
    default_language: str | None = None
    providers: AgentProviders = field(default_factory=AgentProviders)
    llm: AgentLLM = field(default_factory=AgentLLM)
    stt: AgentSTT = field(default_factory=AgentSTT)
    tts: AgentTTS = field(default_factory=AgentTTS)
    behavior: AgentBehavior = field(default_factory=AgentBehavior)
    metadata: dict[str, Any] = field(default_factory=dict)


def profile_from_mapping(agent_id: str, payload: dict[str, Any], settings: Settings) -> AgentProfile:
    return AgentProfile(
        agent_id=agent_id,
        name=_string(payload.get("name"), default=agent_id),
        system_prompt=_string(payload.get("system_prompt"), default=settings.llm_system_prompt),
        greeting=_optional_string(payload.get("greeting")),
        default_language=_optional_string(payload.get("default_language") or payload.get("language")),
        providers=_providers_from_mapping(_mapping(payload.get("providers"))),
        llm=_llm_from_mapping(_mapping(payload.get("llm"))),
        stt=_stt_from_mapping(_mapping(payload.get("stt"))),
        tts=_tts_from_mapping(_mapping(payload.get("tts"))),
        behavior=_behavior_from_mapping(_mapping(payload.get("behavior"))),
        metadata=_mapping(payload.get("metadata")),
    )


def fallback_profile(settings: Settings, agent_id: str | None = None) -> AgentProfile:
    resolved_agent_id = agent_id or settings.default_agent_id
    return AgentProfile(
        agent_id=resolved_agent_id,
        name=settings.agent_name,
        system_prompt=settings.llm_system_prompt,
        greeting=settings.agent_greeting,
        default_language=settings.agent_default_language,
        tts=AgentTTS(
            voice=settings.agent_tts_voice,
            language=settings.agent_tts_language or settings.agent_default_language,
            cartesia_voice_id=settings.cartesia_voice_id,
            cartesia_model=settings.cartesia_model,
            sarvam_model=settings.sarvam_tts_model,
        ),
        stt=AgentSTT(language=settings.deepgram_language, deepgram_model=settings.deepgram_model),
        llm=AgentLLM(
            talker_model=settings.talker_model,
            listener_model=settings.listener_model,
            talker_max_tokens=settings.talker_max_tokens,
            talker_temperature=settings.talker_temperature,
            listener_max_tokens=settings.listener_max_tokens,
            listener_temperature=settings.listener_temperature,
        ),
    )


def apply_agent_profile(settings: Settings, profile: AgentProfile) -> Settings:
    updates: dict[str, Any] = {
        "agent_id": profile.agent_id,
        "agent_name": profile.name,
        "agent_greeting": profile.greeting,
        "llm_system_prompt": profile.system_prompt,
    }
    _put(updates, "agent_default_language", profile.default_language)
    _put(updates, "agent_tts_voice", profile.tts.voice)
    _put(updates, "agent_tts_language", profile.tts.language or profile.default_language)

    _put(updates, "telephony_provider", profile.providers.telephony)
    _put(updates, "stt_provider", profile.providers.stt)
    _put(updates, "tts_provider", profile.providers.tts)
    _put(updates, "llm_provider", profile.providers.llm)
    _put(updates, "live_store_provider", profile.providers.live_store)
    _put(updates, "final_store_provider", profile.providers.final_store)
    _put(updates, "logger_provider", profile.providers.logger)

    _put(updates, "talker_model", profile.llm.talker_model)
    _put(updates, "listener_model", profile.llm.listener_model)
    _put(updates, "talker_max_tokens", profile.llm.talker_max_tokens)
    _put(updates, "talker_temperature", profile.llm.talker_temperature)
    _put(updates, "listener_max_tokens", profile.llm.listener_max_tokens)
    _put(updates, "listener_temperature", profile.llm.listener_temperature)
    _put(updates, "llm_sentence_min_chars", profile.llm.sentence_min_chars)
    _put(updates, "llm_sentence_max_chars", profile.llm.sentence_max_chars)
    _put(updates, "llm_sentence_timeout_ms", profile.llm.sentence_timeout_ms)

    _put(updates, "deepgram_language", profile.stt.language)
    _put(updates, "deepgram_model", profile.stt.deepgram_model)
    _put(updates, "deepgram_endpointing_ms", profile.stt.deepgram_endpointing_ms)
    _put(updates, "deepgram_utterance_end_ms", profile.stt.deepgram_utterance_end_ms)
    _put(updates, "sarvam_stt_language_code", profile.stt.language)
    _put(updates, "sarvam_stt_model", profile.stt.sarvam_model)
    _put(updates, "sarvam_stt_mode", profile.stt.sarvam_mode)
    _put(updates, "sarvam_stt_high_vad_sensitivity", profile.stt.sarvam_high_vad_sensitivity)

    _put(updates, "cartesia_voice_id", profile.tts.cartesia_voice_id)
    _put(updates, "cartesia_model", profile.tts.cartesia_model)
    _put(updates, "cartesia_language", profile.tts.language)
    _put(updates, "cartesia_max_buffer_delay_ms", profile.tts.cartesia_max_buffer_delay_ms)
    _put(updates, "sarvam_tts_model", profile.tts.sarvam_model)
    _put(updates, "sarvam_tts_target_language_code", profile.tts.language)
    _put(updates, "sarvam_tts_speaker", profile.tts.voice)

    _put(updates, "interruption_enabled", profile.behavior.interruption_enabled)
    _put(updates, "min_interrupt_words", profile.behavior.min_interrupt_words)
    _put(updates, "hard_interrupt_after_audio_ms", profile.behavior.hard_interrupt_after_audio_ms)
    _put(updates, "allow_interrupt_welcome_message", profile.behavior.allow_interrupt_welcome_message)
    if profile.behavior.force_interrupt_phrases:
        updates["force_interrupt_phrases"] = profile.behavior.force_interrupt_phrases
    if profile.behavior.backchannel_phrases:
        updates["backchannel_phrases"] = profile.behavior.backchannel_phrases

    return settings.model_copy(update=updates)


def _providers_from_mapping(payload: dict[str, Any]) -> AgentProviders:
    return AgentProviders(
        telephony=_optional_string(payload.get("telephony")),
        stt=_optional_string(payload.get("stt")),
        tts=_optional_string(payload.get("tts")),
        llm=_optional_string(payload.get("llm")),
        live_store=_optional_string(payload.get("live_store")),
        final_store=_optional_string(payload.get("final_store")),
        logger=_optional_string(payload.get("logger")),
    )


def _llm_from_mapping(payload: dict[str, Any]) -> AgentLLM:
    return AgentLLM(
        talker_model=_optional_string(payload.get("talker_model")),
        listener_model=_optional_string(payload.get("listener_model")),
        talker_max_tokens=_optional_int(payload.get("talker_max_tokens")),
        talker_temperature=_optional_float(payload.get("talker_temperature")),
        listener_max_tokens=_optional_int(payload.get("listener_max_tokens")),
        listener_temperature=_optional_float(payload.get("listener_temperature")),
        sentence_min_chars=_optional_int(payload.get("sentence_min_chars")),
        sentence_max_chars=_optional_int(payload.get("sentence_max_chars")),
        sentence_timeout_ms=_optional_int(payload.get("sentence_timeout_ms")),
    )


def _stt_from_mapping(payload: dict[str, Any]) -> AgentSTT:
    return AgentSTT(
        language=_optional_string(payload.get("language")),
        deepgram_model=_optional_string(payload.get("deepgram_model")),
        deepgram_endpointing_ms=_optional_int(payload.get("deepgram_endpointing_ms")),
        deepgram_utterance_end_ms=_optional_int(payload.get("deepgram_utterance_end_ms")),
        sarvam_model=_optional_string(payload.get("sarvam_model")),
        sarvam_mode=_optional_string(payload.get("sarvam_mode")),
        sarvam_high_vad_sensitivity=_optional_bool(payload.get("sarvam_high_vad_sensitivity")),
    )


def _tts_from_mapping(payload: dict[str, Any]) -> AgentTTS:
    return AgentTTS(
        voice=_optional_string(payload.get("voice")),
        language=_optional_string(payload.get("language")),
        cartesia_voice_id=_optional_string(payload.get("cartesia_voice_id")),
        cartesia_model=_optional_string(payload.get("cartesia_model")),
        cartesia_max_buffer_delay_ms=_optional_int(payload.get("cartesia_max_buffer_delay_ms")),
        sarvam_model=_optional_string(payload.get("sarvam_model")),
    )


def _behavior_from_mapping(payload: dict[str, Any]) -> AgentBehavior:
    return AgentBehavior(
        interruption_enabled=_optional_bool(payload.get("interruption_enabled")),
        min_interrupt_words=_optional_int(payload.get("min_interrupt_words")),
        hard_interrupt_after_audio_ms=_optional_int(payload.get("hard_interrupt_after_audio_ms")),
        allow_interrupt_welcome_message=_optional_bool(payload.get("allow_interrupt_welcome_message")),
        force_interrupt_phrases=_string_tuple(payload.get("force_interrupt_phrases")),
        backchannel_phrases=_string_tuple(payload.get("backchannel_phrases")),
    )


def _put(updates: dict[str, Any], key: str, value: Any) -> None:
    if value is not None:
        updates[key] = value


def _mapping(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _optional_string(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _string(value: Any, *, default: str) -> str:
    return _optional_string(value) or default


def _optional_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    return int(value)


def _optional_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    return float(value)


def _optional_bool(value: Any) -> bool | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return value
    return str(value).strip().casefold() in {"1", "true", "yes", "on"}


def _string_tuple(value: Any) -> tuple[str, ...]:
    if not isinstance(value, list | tuple):
        return ()
    return tuple(text for item in value if (text := _optional_string(item)))
