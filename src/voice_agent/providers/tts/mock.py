"""In-memory TTS adapter for offline simulations."""

from collections.abc import AsyncIterator

from voice_agent.contracts.audio import AudioFrame
from voice_agent.contracts.capabilities import TTSCapabilities
from voice_agent.contracts.packets import now_ms


class MockTTS:
    provider_name = "mock"
    capabilities = TTSCapabilities(
        supports_streaming=True,
        supports_cancel=True,
        supports_word_timestamps=False,
        output_codecs=("mulaw_8k", "pcm16_8k"),
    )

    def __init__(self, chunk_words: int = 3) -> None:
        self.call_id: str | None = None
        self.voice: str | None = None
        self.language: str | None = None
        self.chunk_words = chunk_words
        self.cancelled_message_ids: set[str] = set()

    async def start(self, call_id: str, voice: str, language: str) -> None:
        self.call_id = call_id
        self.voice = voice
        self.language = language

    async def synthesize(
        self,
        text: str,
        message_id: str,
        sequence_id: int,
    ) -> AsyncIterator[AudioFrame]:
        if self.call_id is None:
            raise RuntimeError("MockTTS must be started before synthesize().")

        words = text.split() or [text]
        for index in range(0, len(words), self.chunk_words):
            if message_id in self.cancelled_message_ids:
                break
            chunk = " ".join(words[index : index + self.chunk_words])
            yield AudioFrame(
                call_id=self.call_id,
                data=chunk.encode("utf-8"),
                timestamp_ms=now_ms(),
                sample_rate=8000,
                codec="mulaw_8k",
                sequence_id=sequence_id,
                duration_ms=20,
                meta={
                    "message_id": message_id,
                    "text": chunk,
                    "chunk_index": index // self.chunk_words,
                },
            )

    async def cancel(self, message_id: str, reason: str) -> None:
        self.cancelled_message_ids.add(message_id)

    async def stop(self) -> None:
        return None
