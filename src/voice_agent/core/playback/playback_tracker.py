"""Track assistant playback and estimate what the caller actually heard."""

from dataclasses import dataclass, field
from typing import Any

from voice_agent.contracts.audio import AudioFrame
from voice_agent.contracts.events import InterruptionStarted, PlaybackEvent
from voice_agent.contracts.packets import now_ms


@dataclass(slots=True)
class MessagePlayback:
    call_id: str
    message_id: str
    sequence_id: int
    full_text: str = ""
    text_sent_to_tts: str = ""
    audio_chunks_sent: int = 0
    audio_ms_sent: int = 0
    checkpoints_sent: list[str] = field(default_factory=list)
    checkpoints_played: list[str] = field(default_factory=list)
    cleared: bool = False
    interrupted: bool = False
    started_ms: int | None = None
    fully_played_ms: int | None = None
    interrupted_ms: int | None = None
    word_timestamps: dict[str, Any] | None = None

    @property
    def total_audio_ms(self) -> int:
        return max(0, self.audio_ms_sent)

    @property
    def source_text(self) -> str:
        return self.full_text or self.text_sent_to_tts


class PlaybackTracker:
    def __init__(self, call_id: str) -> None:
        self.call_id = call_id
        self.messages: dict[str, MessagePlayback] = {}
        self.sequence_to_message_id: dict[int, str] = {}
        self.checkpoint_to_message_id: dict[str, str] = {}

    def start_message(
        self,
        *,
        message_id: str,
        sequence_id: int,
        started_ms: int | None = None,
    ) -> MessagePlayback:
        playback = self.messages.get(message_id)
        if playback is None:
            playback = MessagePlayback(
                call_id=self.call_id,
                message_id=message_id,
                sequence_id=sequence_id,
                started_ms=started_ms,
            )
            self.messages[message_id] = playback
        self.sequence_to_message_id[sequence_id] = message_id
        return playback

    def append_generated_text(self, message_id: str, text: str) -> None:
        playback = self.messages.get(message_id)
        if playback is None or not text:
            return
        playback.full_text = _append_text(playback.full_text, text)

    def mark_text_sent_to_tts(self, message_id: str, text: str) -> None:
        playback = self.messages.get(message_id)
        if playback is None or not text:
            return
        playback.text_sent_to_tts = _append_text(playback.text_sent_to_tts, text)

    def mark_audio_sent(self, frame: AudioFrame, timestamp_ms: int | None = None) -> MessagePlayback | None:
        message_id = _optional_str(frame.meta.get("message_id"))
        if message_id is None and frame.sequence_id is not None:
            message_id = self.sequence_to_message_id.get(frame.sequence_id)
        if message_id is None:
            return None

        sequence_id = frame.sequence_id or 0
        playback = self.start_message(
            message_id=message_id,
            sequence_id=sequence_id,
            started_ms=timestamp_ms or frame.timestamp_ms or now_ms(),
        )
        if playback.started_ms is None:
            playback.started_ms = timestamp_ms or frame.timestamp_ms or now_ms()
        playback.audio_chunks_sent += 1
        playback.audio_ms_sent += frame.duration_ms or 0
        text = _optional_str(frame.meta.get("text"))
        if text:
            playback.text_sent_to_tts = _append_text(playback.text_sent_to_tts, text)
        word_timestamps = frame.meta.get("word_timestamps")
        if isinstance(word_timestamps, dict):
            playback.word_timestamps = word_timestamps
        return playback

    def mark_checkpoint_sent(self, message_id: str, checkpoint_id: str) -> None:
        playback = self.messages.get(message_id)
        if playback is None:
            return
        playback.checkpoints_sent.append(checkpoint_id)
        self.checkpoint_to_message_id[checkpoint_id] = message_id

    def handle_playback_event(self, event: PlaybackEvent) -> MessagePlayback | None:
        if event.event_type == "checkpoint_played":
            message_id = self._message_id_for_playback_event(event)
            if message_id is None:
                return None
            playback = self.messages.get(message_id)
            if playback is None:
                return None
            checkpoint_id = event.checkpoint_id or event.message_id
            if checkpoint_id:
                playback.checkpoints_played.append(checkpoint_id)
            playback.fully_played_ms = event.ts_ms
            playback.interrupted = False
            return playback

        if event.event_type == "cleared":
            marked: MessagePlayback | None = None
            for playback in self.messages.values():
                if playback.fully_played_ms is None and not playback.interrupted:
                    playback.cleared = True
                    playback.interrupted = True
                    playback.interrupted_ms = event.ts_ms
                    marked = playback
            return marked
        return None

    def mark_interrupted(self, event: InterruptionStarted) -> MessagePlayback | None:
        message_id = self.sequence_to_message_id.get(event.sequence_id)
        if message_id is None:
            return None
        playback = self.messages.get(message_id)
        if playback is None:
            return None
        playback.interrupted = True
        playback.cleared = True
        playback.interrupted_ms = event.ts_ms
        return playback

    def heard_text(self, message_id: str) -> str:
        playback = self.messages.get(message_id)
        if playback is None:
            return ""
        return estimate_heard_text(playback)

    def _message_id_for_playback_event(self, event: PlaybackEvent) -> str | None:
        for candidate in (event.checkpoint_id, event.message_id):
            if candidate and candidate in self.checkpoint_to_message_id:
                return self.checkpoint_to_message_id[candidate]
            if candidate and candidate in self.messages:
                return candidate
        if event.sequence_id in self.sequence_to_message_id:
            return self.sequence_to_message_id[event.sequence_id]
        return None


def estimate_heard_text(playback: MessagePlayback) -> str:
    text = playback.source_text.strip()
    if not text:
        return ""
    if playback.fully_played_ms is not None and not playback.interrupted:
        return text

    played_audio_ms = _played_audio_ms(playback)
    if played_audio_ms <= 0:
        return ""

    timestamp_text = _heard_text_from_word_timestamps(text, playback.word_timestamps, played_audio_ms)
    if timestamp_text:
        return timestamp_text

    total_audio_ms = playback.total_audio_ms
    if total_audio_ms <= 0:
        return ""
    heard_chars = max(0, min(len(text), int(len(text) * played_audio_ms / total_audio_ms)))
    return text[:heard_chars].rstrip()


def _played_audio_ms(playback: MessagePlayback) -> int:
    if playback.fully_played_ms is not None:
        return playback.total_audio_ms
    if playback.interrupted_ms is not None and playback.started_ms is not None:
        return max(0, min(playback.total_audio_ms, playback.interrupted_ms - playback.started_ms))
    return playback.total_audio_ms if playback.cleared else 0


def _heard_text_from_word_timestamps(
    text: str,
    word_timestamps: dict[str, Any] | None,
    played_audio_ms: int,
) -> str:
    if not word_timestamps:
        return ""
    words = word_timestamps.get("words")
    ends = word_timestamps.get("end")
    if not isinstance(words, list) or not isinstance(ends, list):
        return ""

    heard_words: list[str] = []
    for word, end in zip(words, ends, strict=False):
        try:
            end_ms = int(float(end) * 1000)
        except (TypeError, ValueError):
            continue
        if end_ms <= played_audio_ms:
            heard_words.append(str(word))
    if not heard_words:
        return ""
    heard = " ".join(heard_words).strip()
    if heard and heard in text:
        return text[: text.index(heard) + len(heard)].rstrip()
    return heard


def _append_text(existing: str, text: str) -> str:
    if not existing:
        return text.strip()
    if not text.strip():
        return existing
    return f"{existing.rstrip()} {text.strip()}".strip()


def _optional_str(value: Any) -> str | None:
    return str(value) if value else None
