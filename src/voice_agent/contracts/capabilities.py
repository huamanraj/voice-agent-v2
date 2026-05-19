"""Provider capability contracts."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class TelephonyCapabilities:
    supports_clear_playback: bool
    supports_playback_checkpoint: bool
    supports_bidirectional_audio: bool
    inbound_codec: str
    outbound_codec: str


@dataclass(frozen=True, slots=True)
class STTCapabilities:
    supports_interim: bool
    supports_final: bool
    supports_vad_events: bool
    supports_language_detection: bool
    supports_code_switching: bool
    accepted_codecs: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class TTSCapabilities:
    supports_streaming: bool
    supports_cancel: bool
    supports_word_timestamps: bool
    output_codecs: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class LLMCapabilities:
    supports_streaming: bool
    supports_json_mode: bool
    supports_tool_calling: bool
