import asyncio
import base64
import json
from typing import Any

from voice_agent.config import Settings
from voice_agent.contracts.audio import AudioFrame
from voice_agent.contracts.capabilities import STTCapabilities
from voice_agent.contracts.events import SpeechStart, SpeechStop, TranscriptEvent
from voice_agent.contracts.packets import now_ms
from voice_agent.factory.provider_registry import ProviderRegistry
from voice_agent.providers.llm import MockLLM
from voice_agent.providers.storage import MemoryStore
from voice_agent.providers.telephony import VobizTelephony
from voice_agent.providers.tts import MockTTS
from voice_agent.api.ws import (
    _INVALID_STREAM_TOKEN,
    _stream_auth_token_for_session,
    run_vobiz_websocket_session,
)


class FakeVobizWebSocket:
    def __init__(self) -> None:
        self.closed = False
        self.sent_text: list[str] = []
        self.incoming: asyncio.Queue[str] = asyncio.Queue()

    async def receive_text(self) -> str:
        return await self.incoming.get()

    async def send_text(self, data: str) -> None:
        self.sent_text.append(data)

    async def close(self) -> None:
        self.closed = True

    async def feed_json(self, packet: dict[str, Any]) -> None:
        await self.incoming.put(json.dumps(packet))


class QueryWebSocket:
    def __init__(self, token: str | None) -> None:
        self.query_params = {} if token is None else {"token": token}


class TranscriptOnAudioSTT:
    provider_name = "mock"
    capabilities = STTCapabilities(
        supports_interim=True,
        supports_final=True,
        supports_vad_events=True,
        supports_language_detection=True,
        supports_code_switching=True,
        accepted_codecs=("mulaw_8k", "pcm16_8k", "pcm16_16k"),
    )

    def __init__(self, transcript: str) -> None:
        self.transcript = transcript
        self.call_id = "unknown"
        self.sent_transcript = False
        self.audio_frames: list[AudioFrame] = []
        self._transcripts: asyncio.Queue[TranscriptEvent | None] = asyncio.Queue()
        self._speech_events: asyncio.Queue[SpeechStart | SpeechStop | None] = asyncio.Queue()

    async def start(self, call_id: str, language_hint: str | None = None) -> None:
        self.call_id = call_id

    async def send_audio(self, frame: AudioFrame) -> None:
        self.audio_frames.append(frame)
        if self.sent_transcript:
            return
        self.sent_transcript = True
        ts_ms = now_ms()
        await self._speech_events.put(
            SpeechStart(call_id=self.call_id, ts_ms=ts_ms, source="stt", confidence=1.0)
        )
        await self._transcripts.put(
            TranscriptEvent(
                call_id=self.call_id,
                text=self.transcript,
                is_final=True,
                confidence=0.98,
                language="en-IN",
                start_ms=ts_ms,
                end_ms=ts_ms,
                provider=self.provider_name,
            )
        )
        await self._speech_events.put(
            SpeechStop(call_id=self.call_id, ts_ms=ts_ms, source="stt", confidence=1.0)
        )

    async def transcripts(self):
        while True:
            event = await self._transcripts.get()
            if event is None:
                break
            yield event

    async def speech_events(self):
        while True:
            event = await self._speech_events.get()
            if event is None:
                break
            yield event

    async def update_language_hint(self, language: str) -> None:
        return None

    async def stop(self) -> None:
        await self._transcripts.put(None)
        await self._speech_events.put(None)


def test_vobiz_websocket_session_runs_user_turn_to_play_audio() -> None:
    async def scenario() -> None:
        websocket = FakeVobizWebSocket()
        registry = build_registry()
        settings = Settings(
            telephony_provider="vobiz",
            stt_provider="mock",
            tts_provider="mock",
            llm_provider="mock",
            live_store_provider="memory",
            final_store_provider="memory",
            min_user_speech_ms=0,
            min_silence_for_turn_end_ms=0,
            smart_turn_enabled=False,
            llm_sentence_timeout_ms=1,
            vobiz_start_timeout_ms=500,
            vobiz_stream_auth_token=None,
        )

        session_task = asyncio.create_task(
            run_vobiz_websocket_session(websocket, settings=settings, registry=registry)
        )
        await websocket.feed_json(start_packet())
        await websocket.feed_json(media_packet())
        await wait_until(lambda: any(packet.get("event") == "playAudio" for packet in sent_packets(websocket)))
        await websocket.feed_json({"event": "stop"})

        stats = await asyncio.wait_for(session_task, timeout=2)

        assert stats.user_turns_finalized == 1
        assert stats.llm_responses_started == 1
        assert stats.tts_chunks_created >= 1
        assert stats.audio_chunks_sent >= 1
        assert any(packet["event"] == "playAudio" for packet in sent_packets(websocket))
        assert websocket.closed

    asyncio.run(scenario())


def test_vobiz_websocket_session_times_out_without_start_event() -> None:
    async def scenario() -> None:
        websocket = FakeVobizWebSocket()
        registry = build_registry()
        settings = Settings(vobiz_start_timeout_ms=1, vobiz_stream_auth_token=None)

        try:
            await run_vobiz_websocket_session(websocket, settings=settings, registry=registry)
        except TimeoutError:
            pass
        else:
            raise AssertionError("missing Vobiz start event should time out")

        assert websocket.closed

    asyncio.run(scenario())


def test_vobiz_query_token_satisfies_stream_auth() -> None:
    settings = Settings(vobiz_stream_auth_token="expected-token")

    assert _stream_auth_token_for_session(QueryWebSocket("expected-token"), settings) is None
    assert _stream_auth_token_for_session(QueryWebSocket(None), settings) == "expected-token"
    assert (
        _stream_auth_token_for_session(QueryWebSocket("wrong-token"), settings)
        is _INVALID_STREAM_TOKEN
    )


def build_registry() -> ProviderRegistry:
    registry = ProviderRegistry()
    registry.register("telephony", "vobiz", VobizTelephony)
    registry.register("stt", "mock", lambda: TranscriptOnAudioSTT("I need help with my policy"))
    registry.register("tts", "mock", lambda: MockTTS(chunk_words=3))
    registry.register("llm", "mock", lambda: MockLLM(responses=["Sure, I can help with that."]))
    registry.register("live_store", "memory", MemoryStore)
    registry.register("final_store", "memory", MemoryStore)
    return registry


def start_packet() -> dict[str, Any]:
    return {
        "event": "start",
        "start": {
            "callId": "call-123",
            "streamId": "stream-123",
            "mediaFormat": {"encoding": "audio/x-mulaw", "sampleRate": 8000},
        },
    }


def media_packet() -> dict[str, Any]:
    return {
        "event": "media",
        "media": {
            "track": "inbound",
            "timestamp": str(now_ms()),
            "chunk": "1",
            "payload": base64.b64encode(b"\xff" * 160).decode("ascii"),
        },
    }


def sent_packets(websocket: FakeVobizWebSocket) -> list[dict[str, Any]]:
    return [json.loads(message) for message in websocket.sent_text]


async def wait_until(predicate: Any, *, timeout_seconds: float = 1.0) -> None:
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout_seconds
    while loop.time() < deadline:
        if predicate():
            return
        await asyncio.sleep(0)
    raise AssertionError("condition was not met before timeout")
