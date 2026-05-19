"""Queue sizing for the future async pipeline."""

from dataclasses import dataclass

from voice_agent.config import Settings


@dataclass(frozen=True, slots=True)
class QueueSizes:
    telephony_audio_in: int
    stt_audio: int
    vad_audio: int
    transcript_event: int
    speech_event: int
    turn_event: int
    interruption_event: int
    llm_output: int
    tts_audio: int
    telephony_audio_out: int
    playback_event: int
    metrics: int
    dtmf: int


def queue_sizes_from_settings(settings: Settings) -> QueueSizes:
    return QueueSizes(
        telephony_audio_in=settings.queue_audio_in_max,
        stt_audio=settings.queue_stt_audio_max,
        vad_audio=settings.queue_vad_audio_max,
        transcript_event=settings.queue_transcript_event_max,
        speech_event=settings.queue_speech_event_max,
        turn_event=settings.queue_turn_event_max,
        interruption_event=settings.queue_interruption_event_max,
        llm_output=settings.queue_llm_output_max,
        tts_audio=settings.queue_tts_audio_max,
        telephony_audio_out=settings.queue_telephony_audio_out_max,
        playback_event=settings.queue_playback_event_max,
        metrics=settings.queue_metrics_max,
        dtmf=settings.queue_dtmf_max,
    )
