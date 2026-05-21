import asyncio
import base64
import json
from typing import Any
from urllib.parse import parse_qs, urlparse

import pytest

from voice_agent.config import Settings
from voice_agent.contracts.ports import TTSPort
from voice_agent.providers.tts import SarvamTTS


class FakeSarvamTTSWebSocket:
    def __init__(self, *, fail_sends: int = 0) -> None:
        self.fail_sends = fail_sends
        self.closed = False
        self.sent: list[str | bytes] = []
        self.incoming: asyncio.Queue[str | bytes | Exception] = asyncio.Queue()

    async def send(self, data: str | bytes) -> None:
        if self.fail_sends > 0:
            self.fail_sends -= 1
            raise RuntimeError("sarvam tts send exploded")
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


def test_sarvam_tts_satisfies_port_and_configures_documented_socket() -> None:
    async def scenario() -> None:
        websocket = FakeSarvamTTSWebSocket()
        captured: dict[str, Any] = {}

        async def factory(url: str, headers: dict[str, str]) -> FakeSarvamTTSWebSocket:
            captured["url"] = url
            captured["headers"] = headers
            return websocket

        tts = SarvamTTS(settings=sarvam_tts_settings(), websocket_factory=factory)
        await tts.start("call-sarvam-tts", voice="Simran", language="en-IN")

        query = parse_qs(urlparse(captured["url"]).query)
        assert isinstance(tts, TTSPort)
        assert captured["headers"] == {"Api-Subscription-Key": "sarvam-key"}
        assert query["model"] == ["bulbul:v3"]
        assert query["send_completion_event"] == ["true"]

        config_payload = json.loads(websocket.sent[0])
        assert config_payload == {
            "type": "config",
            "data": {
                "model": "bulbul:v3",
                "target_language_code": "en-IN",
                "speaker": "simran",
                "pace": 1.0,
                "temperature": 0.6,
                "speech_sample_rate": "8000",
                "enable_preprocessing": True,
                "output_audio_codec": "linear16",
                "output_audio_bitrate": "128k",
                "min_buffer_size": 50,
                "max_chunk_length": 120,
            },
        }
        await tts.stop()

    asyncio.run(scenario())


def test_sarvam_tts_synthesize_streams_mulaw_audio_after_text_and_flush() -> None:
    async def scenario() -> None:
        websocket = FakeSarvamTTSWebSocket()
        tts = SarvamTTS(
            settings=sarvam_tts_settings(sarvam_tts_output_audio_codec="mulaw"),
            websocket_factory=lambda url, headers: async_value(websocket),
        )

        await tts.start("call-sarvam-tts", voice="simran", language="en-IN")
        await websocket.feed_json(audio_payload(b"\xff" * 160, request_id="req-1", content_type="audio/basic"))
        await websocket.feed_json(event_payload())
        frames = [frame async for frame in tts.synthesize("hello world", "msg-1", 7)]

        assert json.loads(websocket.sent[1]) == {"type": "text", "data": {"text": "hello world"}}
        assert json.loads(websocket.sent[2]) == {"type": "flush"}
        assert len(frames) == 1
        assert frames[0].call_id == "call-sarvam-tts"
        assert frames[0].codec == "mulaw_8k"
        assert frames[0].sample_rate == 8000
        assert frames[0].duration_ms == 20
        assert frames[0].sequence_id == 7
        assert frames[0].meta["provider"] == "sarvam"
        assert frames[0].meta["message_id"] == "msg-1"
        assert frames[0].meta["request_id"] == "req-1"
        assert frames[0].meta["content_type"] == "audio/basic"
        assert frames[0].meta["chunk_index"] == 0
        await tts.stop()

    asyncio.run(scenario())


def test_sarvam_tts_cancel_flushes_and_drops_late_chunks() -> None:
    async def scenario() -> None:
        websocket = FakeSarvamTTSWebSocket()
        tts = SarvamTTS(
            settings=sarvam_tts_settings(),
            websocket_factory=lambda url, headers: async_value(websocket),
            first_audio_timeout_seconds=0.5,
        )

        await tts.start("call-sarvam-tts", voice="simran", language="en-IN")

        async def collect_frames() -> list[Any]:
            return [frame async for frame in tts.synthesize("please wait", "msg-1", 3)]

        task = asyncio.create_task(collect_frames())
        await wait_until(lambda: len(websocket.sent) >= 3)
        await tts.cancel("msg-1", reason="barge-in")
        await websocket.feed_json(audio_payload(b"\xff" * 80))
        await websocket.feed_json(event_payload())

        assert await asyncio.wait_for(task, timeout=0.2) == []
        assert json.loads(websocket.sent[3]) == {"type": "flush"}
        await tts.stop()

    asyncio.run(scenario())


def test_sarvam_tts_converts_linear16_output_to_mulaw() -> None:
    async def scenario() -> None:
        websocket = FakeSarvamTTSWebSocket()
        tts = SarvamTTS(
            settings=sarvam_tts_settings(
                sarvam_tts_output_audio_codec="linear16",
                sarvam_tts_speech_sample_rate=8000,
            ),
            websocket_factory=lambda url, headers: async_value(websocket),
        )

        await tts.start("call-sarvam-tts", voice="simran", language="en-IN")
        await websocket.feed_json(audio_payload(b"\x00\x00" * 80, content_type="audio/l16"))
        await websocket.feed_json(event_payload())
        frames = [frame async for frame in tts.synthesize("hello", "msg-1", 1)]

        assert frames[0].codec == "mulaw_8k"
        assert frames[0].sample_rate == 8000
        assert frames[0].meta["source_codec"] == "pcm16_8k"
        await tts.stop()

    asyncio.run(scenario())


def test_sarvam_tts_retries_with_linear16_when_mulaw_is_rejected() -> None:
    async def scenario() -> None:
        first_socket = FakeSarvamTTSWebSocket()
        second_socket = FakeSarvamTTSWebSocket()
        sockets = [first_socket, second_socket]
        connected_urls: list[str] = []

        async def factory(url: str, headers: dict[str, str]) -> FakeSarvamTTSWebSocket:
            connected_urls.append(url)
            return sockets.pop(0)

        tts = SarvamTTS(
            settings=sarvam_tts_settings(sarvam_tts_output_audio_codec="mulaw"),
            websocket_factory=factory,
        )

        await tts.start("call-sarvam-tts", voice="simran", language="en-IN")
        await first_socket.feed_json(
            {
                "type": "error",
                "data": {
                    "message": "Input parameters has to be a valid dictionary",
                    "code": 422,
                },
            }
        )
        await second_socket.feed_json(audio_payload(b"\x00\x00" * 80, content_type="audio/l16"))
        await second_socket.feed_json(event_payload())

        frames = [frame async for frame in tts.synthesize("hello", "msg-1", 9)]

        assert len(connected_urls) == 2
        assert json.loads(first_socket.sent[0])["data"]["output_audio_codec"] == "mulaw"
        assert json.loads(second_socket.sent[0])["data"]["output_audio_codec"] == "linear16"
        assert frames[0].codec == "mulaw_8k"
        assert frames[0].meta["source_codec"] == "pcm16_8k"
        await tts.stop()

    asyncio.run(scenario())


def test_sarvam_tts_clamps_invalid_min_buffer_size() -> None:
    async def scenario() -> None:
        websocket = FakeSarvamTTSWebSocket()
        tts = SarvamTTS(
            settings=sarvam_tts_settings(sarvam_tts_min_buffer_size=1),
            websocket_factory=lambda url, headers: async_value(websocket),
        )

        await tts.start("call-sarvam-tts", voice="simran", language="en-IN")

        config_payload = json.loads(websocket.sent[0])
        assert config_payload["data"]["min_buffer_size"] == 50
        await tts.stop()

    asyncio.run(scenario())


def test_sarvam_tts_requires_api_key_and_speaker() -> None:
    async def scenario() -> None:
        with pytest.raises(ValueError, match="SARVAM_API_KEY"):
            await SarvamTTS(settings=Settings(sarvam_api_key=None)).start("call-1", "simran", "en-IN")

        with pytest.raises(ValueError, match="speaker"):
            await SarvamTTS(
                settings=Settings(
                    sarvam_api_key="sarvam-key",
                    sarvam_tts_speaker="",
                ),
                websocket_factory=lambda url, headers: async_value(FakeSarvamTTSWebSocket()),
            ).start("call-1", "mock-voice", "en-IN")

    asyncio.run(scenario())


def sarvam_tts_settings(**overrides: Any) -> Settings:
    values = {
        "sarvam_api_key": "sarvam-key",
        "sarvam_tts_ws_url": "wss://api.sarvam.ai/text-to-speech/ws",
        "sarvam_tts_model": "bulbul:v3",
        "sarvam_tts_speaker": "simran",
        "sarvam_tts_target_language_code": "en-IN",
        "sarvam_tts_speech_sample_rate": 8000,
        "sarvam_tts_output_audio_codec": "linear16",
        "sarvam_tts_output_audio_bitrate": "128k",
        "sarvam_tts_pace": 1.0,
        "sarvam_tts_temperature": 0.6,
        "sarvam_tts_enable_preprocessing": True,
        "sarvam_tts_min_buffer_size": 50,
        "sarvam_tts_max_chunk_length": 120,
        "sarvam_tts_send_completion_event": True,
        "sarvam_tts_keepalive_seconds": 20,
        "tts_first_audio_timeout_ms": 3000,
    }
    values.update(overrides)
    return Settings(**values)


def audio_payload(data: bytes, *, request_id: str = "req-1", content_type: str = "audio/basic") -> dict[str, Any]:
    return {
        "type": "audio",
        "data": {
            "audio": base64.b64encode(data).decode("ascii"),
            "request_id": request_id,
            "content_type": content_type,
        },
    }


def event_payload() -> dict[str, Any]:
    return {
        "type": "event",
        "data": {
            "event_type": "final",
            "message": "done",
            "timestamp": "2026-05-21T00:00:00Z",
        },
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
