import json
from pathlib import Path
from tempfile import NamedTemporaryFile

from voice_agent.agents import LocalAgentAdapter, apply_agent_profile
from voice_agent.config import Settings


def test_local_agent_profile_overrides_runtime_settings() -> None:
    config_path = _write_temp_agent_config(
        {
            "agents": {
                "sales": {
                    "name": "Sales agent",
                    "system_prompt": "Ask one sales question at a time.",
                    "greeting": "Hello from sales.",
                    "default_language": "hi-IN",
                    "providers": {
                        "stt": "deepgram",
                        "tts": "cartesia",
                        "llm": "litellm",
                    },
                    "llm": {
                        "talker_model": "openai/gpt-4.1-mini",
                        "listener_model": "openai/gpt-4.1-mini",
                        "talker_max_tokens": 64,
                    },
                    "stt": {
                        "language": "multi",
                        "deepgram_model": "nova-3",
                    },
                    "tts": {
                        "voice": "voice-from-profile",
                        "language": "hi-IN",
                        "cartesia_model": "sonic-3.5",
                    },
                    "behavior": {
                        "min_interrupt_words": 2,
                        "force_interrupt_phrases": ["ruk jao"],
                    },
                }
            }
        }
    )
    try:
        settings = Settings(agent_config_path=str(config_path), default_agent_id="sales")

        profile = LocalAgentAdapter(settings).get()
        runtime_settings = apply_agent_profile(settings, profile)

        assert runtime_settings.agent_id == "sales"
        assert runtime_settings.agent_name == "Sales agent"
        assert runtime_settings.llm_system_prompt == "Ask one sales question at a time."
        assert runtime_settings.agent_greeting == "Hello from sales."
        assert runtime_settings.stt_provider == "deepgram"
        assert runtime_settings.tts_provider == "cartesia"
        assert runtime_settings.llm_provider == "litellm"
        assert runtime_settings.talker_model == "openai/gpt-4.1-mini"
        assert runtime_settings.agent_tts_voice == "voice-from-profile"
        assert runtime_settings.deepgram_language == "multi"
        assert runtime_settings.cartesia_model == "sonic-3.5"
        assert runtime_settings.min_interrupt_words == 2
        assert runtime_settings.force_interrupt_phrases == ("ruk jao",)
    finally:
        config_path.unlink(missing_ok=True)


def test_env_default_agent_id_wins_over_json_default_agent_id() -> None:
    config_path = _write_temp_agent_config(
        {
            "default_agent_id": "legacy_default",
            "agents": {
                "legacy_default": {
                    "name": "Legacy default",
                    "system_prompt": "Legacy prompt.",
                    "providers": {"llm": "mock"},
                },
                "production": {
                    "name": "Production agent",
                    "system_prompt": "Production prompt.",
                    "providers": {
                        "stt": "deepgram",
                        "tts": "cartesia",
                        "llm": "litellm",
                    },
                },
            },
        }
    )
    try:
        settings = Settings(
            agent_config_path=str(config_path),
            default_agent_id="production",
            llm_provider="mock",
        )
        profile = LocalAgentAdapter(settings).get()
        runtime_settings = apply_agent_profile(settings, profile)

        assert profile.agent_id == "production"
        assert runtime_settings.llm_provider == "litellm"
        assert runtime_settings.llm_system_prompt == "Production prompt."
    finally:
        config_path.unlink(missing_ok=True)


def test_local_agent_adapter_falls_back_when_file_is_missing() -> None:
    settings = Settings(
        agent_config_path="missing-agent-test-file.json",
        default_agent_id="fallback",
        llm_system_prompt="Fallback prompt.",
    )

    profile = LocalAgentAdapter(settings).get()

    assert profile.agent_id == "fallback"
    assert profile.system_prompt == "Fallback prompt."


def _write_temp_agent_config(payload: dict) -> Path:
    temp_file = NamedTemporaryFile("w", encoding="utf-8", suffix=".json", delete=False)
    with temp_file:
        json.dump(payload, temp_file)
    return Path(temp_file.name)
