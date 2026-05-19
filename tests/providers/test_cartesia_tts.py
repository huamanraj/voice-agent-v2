import asyncio
import base64
import json
from typing import Any

import pytest

from voice_agent.config import Settings
from voice_agent.contracts.ports import TTSPort
from voice_agent.providers.tts import CartesiaTTS


class FakeCartesiaWebSocket:
    def __init__(self, *, fail_sends: int = 0) -> None:
        self.fail_sends = fail_sends
        self.closed = False
        self.sent: list[str | bytes] = []
        self.incoming: asyncio.Queue[str | bytes | Exception] = asyncio.Queue()

    async def send(self, data: str | bytes) -> None:
        if self.fail_sends > 0:
            self.fail_sends -= 1
            raise RuntimeError("cartesia send exploded")
        self.sent.append(data)

    async def recv(self) -> str | bytes:
        item = await self.incoming.get()
        if isinstance(item, Exception):
            raise item
        return item

    async def close(self) -> None:
        self.closed = True

    async def feed_json(self, payload: dict[str, Any]) -> None:
        await self.incoming.put(json.dumps(payload))


def test_cartesia_tts_satisfies_port_and_connects_with_headers() -> None:
    async def scenario() -> None:
        websocket = FakeCartesiaWebSocket()
        captured: dict[str, Any] = {}

        async def factory(url: str, headers: dict[str, str]) -> FakeCartesiaWebSocket:
            captured["url"] = url
            captured["headers"] = headers
            return websocket

        tts = CartesiaTTS(settings=cartesia_settings(), websocket_factory=factory)

        await tts.start("call-cartesia", voice="ignored-by-config", language="en-IN")

        assert isinstance(tts, TTSPort)
        assert captured["url"] == "wss://api.cartesia.ai/tts/websocket"
        assert captured["headers"] == {
            "X-API-Key": "cartesia-key",
            "Cartesia-Version": "2026-03-01",
        }
        await tts.stop()
        assert websocket.closed

    asyncio.run(scenario())


def test_cartesia_synthesize_sends_documented_payload_and_yields_mulaw() -> None:
    async def scenario() -> None:
        websocket = FakeCartesiaWebSocket()
        tts = CartesiaTTS(
            settings=cartesia_settings(),
            websocket_factory=lambda url, headers: async_value(websocket),
        )

        await tts.start("call-cartesia", voice="voice-from-start", language="en-IN")
        await websocket.feed_json(chunk_payload("msg-1", b"\xff" * 160, done=False, step_time=42))
        await websocket.feed_json({"type": "done", "done": True, "status_code": 206, "context_id": "msg-1"})
        frames = [frame async for frame in tts.synthesize("hello world", "msg-1", 7)]

        sent_payload = json.loads(websocket.sent[0])
        assert sent_payload == {
            "model_id": "sonic-3.5",
            "transcript": "hello world",
            "voice": {"mode": "id", "id": "voice-id"},
            "output_format": {"container": "raw", "encoding": "pcm_mulaw", "sample_rate": 8000},
            "language": "en",
            "context_id": "msg-1",
            "continue": False,
            "max_buffer_delay_ms": 100,
            "add_timestamps": True,
        }
        assert len(frames) == 1
        assert frames[0].call_id == "call-cartesia"
        assert frames[0].codec == "mulaw_8k"
        assert frames[0].sample_rate == 8000
        assert frames[0].duration_ms == 20
        assert frames[0].sequence_id == 7
        assert frames[0].meta["provider"] == "cartesia"
        assert frames[0].meta["message_id"] == "msg-1"
        assert frames[0].meta["context_id"] == "msg-1"
        assert frames[0].meta["chunk_index"] == 0
        assert frames[0].meta["step_time"] == 42
        await tts.stop()

    asyncio.run(scenario())


def test_cartesia_timestamps_are_stored_and_attached_to_later_chunks() -> None:
    async def scenario() -> None:
        websocket = FakeCartesiaWebSocket()
        tts = CartesiaTTS(
            settings=cartesia_settings(),
            websocket_factory=lambda url, headers: async_value(websocket),
        )
        timestamps = {"words": ["hello"], "start": [0.0], "end": [0.4]}

        await tts.start("call-cartesia", voice="voice-from-start", language="en-IN")
        await websocket.feed_json(
            {
                "type": "timestamps",
                "done": False,
                "status_code": 206,
                "context_id": "msg-1",
                "word_timestamps": timestamps,
            }
        )
        await websocket.feed_json(chunk_payload("msg-1", b"\xff" * 80, done=True))
        frames = [frame async for frame in tts.synthesize("hello", "msg-1", 7)]

        assert tts.word_timestamps_by_context["msg-1"] == timestamps
        assert frames[0].meta["word_timestamps"] == timestamps
        await tts.stop()

    asyncio.run(scenario())


def test_cartesia_cancel_sends_context_cancel_and_drops_late_chunks() -> None:
    async def scenario() -> None:
        websocket = FakeCartesiaWebSocket()
        tts = CartesiaTTS(
            settings=cartesia_settings(),
            websocket_factory=lambda url, headers: async_value(websocket),
            first_audio_timeout_seconds=0.5,
        )

        await tts.start("call-cartesia", voice="voice-from-start", language="en")

        async def collect_frames() -> list[Any]:
            return [frame async for frame in tts.synthesize("please wait", "msg-1", 3)]

        task = asyncio.create_task(collect_frames())
        await wait_until(lambda: len(websocket.sent) == 1)
        await tts.cancel("msg-1", reason="barge-in")
        await websocket.feed_json(chunk_payload("msg-1", b"\xff" * 80, done=False))
        await websocket.feed_json({"type": "done", "done": True, "status_code": 206, "context_id": "msg-1"})

        assert await asyncio.wait_for(task, timeout=0.2) == []
        assert json.loads(websocket.sent[1]) == {"context_id": "msg-1", "cancel": True}
        await tts.stop()

    asyncio.run(scenario())


def test_cartesia_error_response_raises_and_records_error() -> None:
    async def scenario() -> None:
        websocket = FakeCartesiaWebSocket()
        tts = CartesiaTTS(
            settings=cartesia_settings(),
            websocket_factory=lambda url, headers: async_value(websocket),
        )

        await tts.start("call-cartesia", voice="voice-from-start", language="en")
        await websocket.feed_json(
            {
                "type": "error",
                "done": True,
                "error_code": "model_not_found",
                "title": "Invalid model",
                "message": "The model is not valid.",
                "context_id": "msg-1",
            }
        )

        with pytest.raises(RuntimeError, match="The model is not valid"):
            _ = [frame async for frame in tts.synthesize("hello", "msg-1", 1)]
        assert tts.errors[-1].error_type == "cartesia_error"
        assert tts.errors[-1].error_code == "model_not_found"
        await tts.stop()

    asyncio.run(scenario())


def test_cartesia_requires_api_key_and_voice() -> None:
    async def scenario() -> None:
        with pytest.raises(ValueError, match="CARTESIA_API_KEY"):
            await CartesiaTTS(settings=Settings(cartesia_api_key=None)).start("call-1", "voice-id", "en")

        with pytest.raises(ValueError, match="CARTESIA_VOICE_ID"):
            await CartesiaTTS(
                settings=Settings(cartesia_api_key="cartesia-key", cartesia_voice_id=None),
                websocket_factory=lambda url, headers: async_value(FakeCartesiaWebSocket()),
            ).start("call-1", "mock-voice", "en")

    asyncio.run(scenario())


def test_cartesia_converts_pcm16_8k_output_to_mulaw() -> None:
    async def scenario() -> None:
        websocket = FakeCartesiaWebSocket()
        tts = CartesiaTTS(
            settings=cartesia_settings(cartesia_output_encoding="pcm_s16le", cartesia_sample_rate=8000),
            websocket_factory=lambda url, headers: async_value(websocket),
        )

        await tts.start("call-cartesia", voice="voice-from-start", language="en")
        await websocket.feed_json(chunk_payload("msg-1", b"\x00\x00" * 80, done=True))
        frames = [frame async for frame in tts.synthesize("hello", "msg-1", 1)]

        assert frames[0].codec == "mulaw_8k"
        assert frames[0].sample_rate == 8000
        assert frames[0].meta["source_codec"] == "pcm16_8k"
        await tts.stop()

    asyncio.run(scenario())


def cartesia_settings(**overrides: Any) -> Settings:
    values = {
        "cartesia_api_key": "cartesia-key",
        "cartesia_ws_url": "wss://api.cartesia.ai/tts/websocket",
        "cartesia_version": "2026-03-01",
        "cartesia_voice_id": "voice-id",
        "cartesia_language": "en",
        "cartesia_model": "sonic-3.5",
        "cartesia_output_encoding": "pcm_mulaw",
        "cartesia_sample_rate": 8000,
        "cartesia_max_buffer_delay_ms": 100,
        "cartesia_add_timestamps": True,
        "tts_first_audio_timeout_ms": 3000,
    }
    values.update(overrides)
    return Settings(**values)


def chunk_payload(context_id: str, data: bytes, *, done: bool, step_time: int = 1) -> dict[str, Any]:
    return {
        "type": "chunk",
        "data": base64.b64encode(data).decode("ascii"),
        "done": done,
        "status_code": 206,
        "step_time": step_time,
        "context_id": context_id,
    }


async def async_value(value: Any) -> Any:
    return value


async def wait_until(predicate: Any, *, timeout_seconds: float = 0.2) -> None:
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout_seconds
    while loop.time() < deadline:
        if predicate():
            return
        await asyncio.sleep(0)
    raise AssertionError("condition was not met before timeout")
