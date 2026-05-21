import asyncio
import json
from typing import Any

import pytest

from voice_agent.audio.converter import silence_bytes
from voice_agent.config import Settings
from voice_agent.contracts.audio import AudioFrame
from voice_agent.contracts.ports import STTPort
from voice_agent.providers.stt import DeepgramSTT


class FakeDeepgramWebSocket:
    def __init__(self, *, fail_sends: int = 0) -> None:
        self.fail_sends = fail_sends
        self.closed = False
        self.sent: list[bytes | str] = []
        self.incoming: asyncio.Queue[str | bytes | Exception] = asyncio.Queue()

    async def send(self, data: bytes | str) -> None:
        if self.fail_sends > 0:
            self.fail_sends -= 1
            raise RuntimeError("deepgram send exploded")
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


def test_deepgram_stt_satisfies_port_and_builds_documented_url() -> None:
    async def scenario() -> None:
        websocket = FakeDeepgramWebSocket()
        captured: dict[str, Any] = {}

        async def factory(url: str, headers: dict[str, str]) -> FakeDeepgramWebSocket:
            captured["url"] = url
            captured["headers"] = headers
            return websocket

        stt = DeepgramSTT(
            settings=deepgram_settings(),
            websocket_factory=factory,
            keepalive_seconds=99,
        )
        await stt.start("call-dg", language_hint="hi")

        assert isinstance(stt, STTPort)
        assert captured["headers"] == {"Authorization": "Token dg-key"}
        assert captured["url"].startswith("wss://api.deepgram.com/v1/listen?")
        assert "model=nova-3" in captured["url"]
        assert "encoding=mulaw" in captured["url"]
        assert "sample_rate=8000" in captured["url"]
        assert "interim_results=true" in captured["url"]
        assert "vad_events=true" in captured["url"]
        assert "endpointing=100" in captured["url"]
        assert "utterance_end_ms=1000" in captured["url"]
        assert "language=hi" in captured["url"]
        await stt.stop()

    asyncio.run(scenario())


def test_deepgram_send_audio_writes_binary_frames() -> None:
    async def scenario() -> None:
        websocket = FakeDeepgramWebSocket()
        stt = DeepgramSTT(
            settings=deepgram_settings(),
            websocket_factory=lambda url, headers: async_value(websocket),
            keepalive_seconds=99,
        )
        frame = audio_frame()

        await stt.start("call-dg")
        await stt.send_audio(frame)

        assert websocket.sent == [frame.data]
        await stt.stop()

    asyncio.run(scenario())


def test_deepgram_keepalive_is_text_json_not_audio() -> None:
    async def scenario() -> None:
        websocket = FakeDeepgramWebSocket()
        stt = DeepgramSTT(
            settings=deepgram_settings(),
            websocket_factory=lambda url, headers: async_value(websocket),
            keepalive_seconds=0.01,
        )

        await stt.start("call-dg")
        await wait_until(lambda: any(item == '{"type": "KeepAlive"}' for item in websocket.sent))
        await stt.stop()

    asyncio.run(scenario())


def test_deepgram_results_emit_transcript_events() -> None:
    async def scenario() -> None:
        websocket = FakeDeepgramWebSocket()
        stt = DeepgramSTT(
            settings=deepgram_settings(),
            websocket_factory=lambda url, headers: async_value(websocket),
            keepalive_seconds=99,
        )

        await stt.start("call-dg", language_hint="multi")
        await websocket.feed_json(
            {
                "type": "Results",
                "start": 1.25,
                "duration": 0.75,
                "is_final": True,
                "speech_final": True,
                "channel": {
                    "alternatives": [
                        {
                            "transcript": "haan policy chahiye",
                            "confidence": 0.91,
                            "languages": ["hi"],
                            "words": [],
                        }
                    ]
                },
                "metadata": {"request_id": "request-1"},
            }
        )
        transcript = await asyncio.wait_for(anext(stt.transcripts()), 0.2)

        assert transcript.call_id == "call-dg"
        assert transcript.text == "haan policy chahiye"
        assert transcript.is_final
        assert transcript.confidence == 0.91
        assert transcript.language == "hi"
        assert transcript.start_ms == 1250
        assert transcript.end_ms == 2000
        assert transcript.asr_turn_id == "request-1"
        await stt.stop()

    asyncio.run(scenario())


def test_deepgram_final_empty_results_emit_empty_transcript_event() -> None:
    async def scenario() -> None:
        websocket = FakeDeepgramWebSocket()
        stt = DeepgramSTT(
            settings=deepgram_settings(),
            websocket_factory=lambda url, headers: async_value(websocket),
            keepalive_seconds=99,
        )

        await stt.start("call-dg", language_hint="multi")
        await websocket.feed_json(
            {
                "type": "Results",
                "start": 1.25,
                "duration": 0.75,
                "is_final": True,
                "speech_final": True,
                "channel": {"alternatives": [{"transcript": "", "confidence": 0.0}]},
            }
        )
        transcript = await asyncio.wait_for(anext(stt.transcripts()), 0.2)

        assert transcript.call_id == "call-dg"
        assert transcript.text == ""
        assert transcript.is_final
        assert transcript.start_ms == 1250
        assert transcript.end_ms == 2000
        await stt.stop()

    asyncio.run(scenario())


def test_deepgram_speech_started_and_utterance_end_emit_speech_events() -> None:
    async def scenario() -> None:
        websocket = FakeDeepgramWebSocket()
        stt = DeepgramSTT(
            settings=deepgram_settings(),
            websocket_factory=lambda url, headers: async_value(websocket),
            keepalive_seconds=99,
        )

        await stt.start("call-dg")
        await websocket.feed_json({"type": "SpeechStarted", "timestamp": 0.3, "channel": [0]})
        await websocket.feed_json({"type": "UtteranceEnd", "last_word_end": 1.2, "channel": [0]})
        events = [
            await asyncio.wait_for(anext(stt.speech_events()), 0.2),
            await asyncio.wait_for(anext(stt.speech_events()), 0.2),
        ]

        assert events[0].source == "stt"
        assert events[0].call_id == "call-dg"
        assert events[1].source == "stt"
        assert events[1].call_id == "call-dg"
        await stt.stop()

    asyncio.run(scenario())


def test_deepgram_reconnect_buffers_audio_and_flushes_to_next_socket() -> None:
    async def scenario() -> None:
        first = FakeDeepgramWebSocket(fail_sends=1)
        second = FakeDeepgramWebSocket()
        sockets = [first, second]

        async def factory(url: str, headers: dict[str, str]) -> FakeDeepgramWebSocket:
            return sockets.pop(0)

        stt = DeepgramSTT(
            settings=deepgram_settings(),
            websocket_factory=factory,
            keepalive_seconds=99,
            reconnect_backoffs_seconds=(0,),
        )
        frame = audio_frame()

        await stt.start("call-dg")
        await stt.send_audio(frame)

        assert first.closed
        assert second.sent == [frame.data]
        assert any(error.error_type == "audio_send_failed" for error in stt.errors)
        await stt.stop()

    asyncio.run(scenario())


def test_deepgram_requires_api_key() -> None:
    async def scenario() -> None:
        stt = DeepgramSTT(settings=Settings(deepgram_api_key=None))

        with pytest.raises(ValueError, match="DEEPGRAM_API_KEY"):
            await stt.start("call-dg")

    asyncio.run(scenario())


def test_deepgram_rejects_wrong_router_codec() -> None:
    async def scenario() -> None:
        websocket = FakeDeepgramWebSocket()
        stt = DeepgramSTT(
            settings=deepgram_settings(),
            websocket_factory=lambda url, headers: async_value(websocket),
            keepalive_seconds=99,
        )
        await stt.start("call-dg")

        with pytest.raises(ValueError, match="AudioRouter should convert"):
            await stt.send_audio(
                AudioFrame(
                    call_id="call-dg",
                    data=silence_bytes("pcm16_16k", 20),
                    timestamp_ms=1000,
                    sample_rate=16000,
                    codec="pcm16_16k",
                    duration_ms=20,
                )
            )
        await stt.stop()

    asyncio.run(scenario())


def deepgram_settings() -> Settings:
    return Settings(
        deepgram_api_key="dg-key",
        deepgram_ws_url="wss://api.deepgram.com/v1/listen",
        deepgram_model="nova-3",
        deepgram_language="multi",
        deepgram_endpointing_ms=100,
        deepgram_utterance_end_ms=1000,
        deepgram_keepalive_seconds=3,
    )


def audio_frame() -> AudioFrame:
    return AudioFrame(
        call_id="call-dg",
        data=silence_bytes("mulaw_8k", 20),
        timestamp_ms=1000,
        sample_rate=8000,
        codec="mulaw_8k",
        duration_ms=20,
    )


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
