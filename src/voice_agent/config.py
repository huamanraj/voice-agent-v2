"""Application configuration.

Environment variables intentionally stay flat so deployment systems can map
secrets and provider choices without touching core code.
"""

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

ProviderName = Literal[
    "mock",
    "vobiz",
    "deepgram",
    "sarvam",
    "cartesia",
    "litellm",
    "redis",
    "postgres",
    "memory",
    "file",
    "otel",
    "noop",
]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        frozen=True,
    )

    app_env: str = "development"
    api_host: str = "0.0.0.0"
    api_port: int = 8080
    public_ws_base_url: str = "ws://localhost:8080"

    telephony_provider: ProviderName = "mock"
    stt_provider: ProviderName = "mock"
    tts_provider: ProviderName = "mock"
    llm_provider: ProviderName = "mock"
    live_store_provider: ProviderName = "memory"
    final_store_provider: ProviderName = "memory"
    logger_provider: ProviderName = "file"

    vobiz_api_base_url: str = "https://api.vobiz.ai"
    vobiz_auth_id: str | None = None
    vobiz_auth_token: str | None = None
    vobiz_from_number: str | None = None
    vobiz_answer_url: str | None = None
    vobiz_answer_method: str = "POST"
    vobiz_stream_ws_path: str = "/ws/vobiz"
    vobiz_stream_auth_token: str | None = None
    vobiz_start_timeout_ms: int = 3000
    deepgram_api_key: str | None = None
    sarvam_api_key: str | None = None
    cartesia_api_key: str | None = None
    groq_api_key: str | None = None
    openai_api_key: str | None = None

    redis_url: str = "redis://localhost:6379/0"
    postgres_dsn: str = "postgresql://user:pass@localhost:5432/voice_agent"

    max_concurrent_calls_per_worker: int = 5
    queue_audio_in_max: int = 100
    queue_stt_audio_max: int = 150
    queue_vad_audio_max: int = 150
    queue_rolling_audio_max: int = 150
    queue_transcript_event_max: int = 500
    queue_speech_event_max: int = 500
    queue_turn_event_max: int = 100
    queue_interruption_event_max: int = 100
    queue_llm_request_max: int = 100
    queue_llm_output_max: int = 500
    queue_tts_request_max: int = 100
    queue_tts_audio_max: int = 200
    queue_telephony_audio_out_max: int = 200
    queue_playback_event_max: int = 500
    queue_metrics_max: int = 1000
    queue_dtmf_max: int = 100
    queue_error_max: int = 100
    shutdown_grace_seconds: int = 10
    output_gate_wait_timeout_ms: int = 250

    telephony_codec: str = "mulaw_8k"
    telephony_sample_rate: int = 8000
    outbound_chunk_ms: int = 20

    vad_enabled: bool = True
    vad_start_min_ms: int = 80
    vad_stop_min_ms: int = 350
    vad_confidence_threshold: float = 0.55
    min_user_speech_ms: int = 250
    min_silence_for_turn_end_ms: int = 450
    max_silence_before_force_end_ms: int = 1200
    smart_turn_enabled: bool = True
    smart_turn_threshold: float = 0.65
    end_of_turn_grace_ms: int = 250

    interruption_enabled: bool = True
    min_interrupt_words: int = 3
    min_interruption_audio_ms: int = 180
    hard_interrupt_after_audio_ms: int = 350
    wait_gate_on_speech_start: bool = True
    clear_audio_on_confirmed_interrupt: bool = True
    preemptive_clear_audio: bool = False
    preemptive_clear_after_ms: int = 220
    allow_interrupt_welcome_message: bool = False

    talker_model: str = "mock-talker"
    listener_model: str = "mock-listener"
    llm_system_prompt: str = (
        "You are a real-time phone voice agent. Reply briefly, naturally, "
        "and with one question at a time. Match the user's language style. "
        "Do not use markdown, bullets, code formatting, or long paragraphs."
    )
    litellm_api_key: str | None = None
    litellm_api_base: str | None = None
    litellm_api_version: str | None = None
    talker_max_tokens: int = 80
    talker_temperature: float = 0.2
    listener_max_tokens: int = 120
    listener_temperature: float = 0.0
    llm_first_token_timeout_ms: int = 3000
    llm_total_timeout_ms: int = 15000
    llm_sentence_min_chars: int = 80
    llm_sentence_max_chars: int = 160
    llm_sentence_timeout_ms: int = 500

    deepgram_ws_url: str = "wss://api.deepgram.com/v1/listen"
    deepgram_model: str = "nova-3"
    deepgram_language: str = "multi"
    deepgram_endpointing_ms: int = 100
    deepgram_utterance_end_ms: int = 1000
    deepgram_keepalive_seconds: int = 3

    cartesia_ws_url: str = "wss://api.cartesia.ai/tts/websocket"
    cartesia_version: str = "2026-03-01"
    cartesia_voice_id: str | None = None
    cartesia_language: str = "en"
    cartesia_model: str = "sonic-3.5"
    cartesia_output_encoding: str = "pcm_mulaw"
    cartesia_sample_rate: int = 8000
    cartesia_max_buffer_delay_ms: int = 100
    cartesia_add_timestamps: bool = True
    tts_first_audio_timeout_ms: int = 3000

    log_dir: str = "./logs"
    log_level: str = "INFO"
    log_full_transcripts: bool = True
    mask_phone_in_shared_logs: bool = True

    force_interrupt_phrases: tuple[str, ...] = Field(
        default=(
            "stop",
            "wait",
            "ruk",
            "ruko",
            "ruk jao",
            "ek minute",
            "ek min",
            "nahin",
            "nahi",
            "no",
            "wrong",
            "galat",
            "suno",
            "sun",
        )
    )
    backchannel_phrases: tuple[str, ...] = Field(
        default=(
            "haan",
            "ha",
            "hmm",
            "hm",
            "okay",
            "ok",
            "ji",
            "achha",
            "acha",
            "theek hai",
            "thik hai",
            "yes",
            "yeah",
            "right",
        )
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
