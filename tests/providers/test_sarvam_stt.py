import asyncio
import base64
import json
from typing import Any
from urllib.parse import parse_qs, urlparse

import pytest

from voice_agent.audio.converter import silence_bytes
from voice_agent.config import Settings
from voice_agent.contracts.audio import AudioFrame
from voice_agent.contracts.ports import STTPort
from voice_agent.providers.stt import SarvamSTT


class FakeSarvamWebSocket:
    def __init__(self, *, fail_sends: int = 0) -> None:
        self.fail_sends = fail_sends
        self.closed = False
        self.sent: list[bytes | str] = []
        self.incoming: asyncio.Queue[str | bytes | Exception] = asyncio.Queue()

    async def send(self, data: bytes | str) -> None:
        if self.fail_sends > 0:
            self.fail_sends -= 1
            raise RuntimeError("sarvam send exploded")
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


def test_sarvam_stt_satisfies_port_and_builds_documented_url() -> None:
    async def scenario() -> None:
        websocket = FakeSarvamWebSocket()
        captured: dict[str, Any] = {}

        async def factory(url: str, headers: dict[str, str]) -> FakeSarvamWebSocket:
            captured["url"] = url
            captured["headers"] = headers
            return websocket

        stt = SarvamSTT(settings=sarvam_settings(), websocket_factory=factory)
        await stt.start("call-sarvam", language_hint="hi-IN")

        query = parse_qs(urlparse(captured["url"]).query)
        assert isinstance(stt, STTPort)
        assert captured["headers"] == {"Api-Subscription-Key": "sarvam-key"}
        assert captured["url"].startswith("wss://api.sarvam.ai/speech-to-text/ws?")
        assert query["language-code"] == ["hi-IN"]
        assert query["model"] == ["saaras:v3"]
        assert query["mode"] == ["transcribe"]
        assert query["sample_rate"] == ["8000"]
        assert query["input_audio_codec"] == ["pcm_s16le"]
        assert query["vad_signals"] == ["true"]
        assert query["flush_signal"] == ["true"]
        await stt.stop()

    asyncio.run(scenario())


def test_sarvam_send_audio_uses_low_latency_pcm_json_frames() -> None:
    async def scenario() -> None:
        websocket = FakeSarvamWebSocket()
        stt = SarvamSTT(
            settings=sarvam_settings(),
            websocket_factory=lambda url, headers: async_value(websocket),
        )
        frame = audio_frame()

        await stt.start("call-sarvam")
        await stt.send_audio(frame)

        payload = json.loads(websocket.sent[0])
        assert payload == {
            "audio": {
                "data": base64.b64encode(frame.data).decode("ascii"),
                "sample_rate": "8000",
                "encoding": "audio/wav",
            }
        }
        await stt.stop()

    asyncio.run(scenario())


def test_sarvam_transcription_and_vad_events() -> None:
    async def scenario() -> None:
        websocket = FakeSarvamWebSocket()
        stt = SarvamSTT(
            settings=sarvam_settings(),
            websocket_factory=lambda url, headers: async_value(websocket),
        )

        await stt.start("call-sarvam", language_hint="unknown")
        await websocket.feed_json({"type": "events", "data": {"signal_type": "START_SPEECH"}})
        await websocket.feed_json(
            {
                "type": "data",
                "data": {
                    "request_id": "request-1",
                    "transcript": "haan policy chahiye",
                    "language_code": "hi-IN",
                    "language_probability": 0.93,
                    "metrics": {"audio_duration": 1.2, "processing_latency": 0.15},
                },
            }
        )
        await websocket.feed_json({"type": "events", "data": {"signal_type": "END_SPEECH"}})

        start = await asyncio.wait_for(anext(stt.speech_events()), 0.2)
        transcript = await asyncio.wait_for(anext(stt.transcripts()), 0.2)
        stop = await asyncio.wait_for(anext(stt.speech_events()), 0.2)

        assert start.source == "stt"
        assert transcript.call_id == "call-sarvam"
        assert transcript.text == "haan policy chahiye"
        assert transcript.is_final
        assert transcript.confidence == 0.93
        assert transcript.language == "hi-IN"
        assert transcript.end_ms == 1200
        assert transcript.asr_turn_id == "request-1"
        assert stop.source == "stt"
        await stt.stop()

    asyncio.run(scenario())


def test_sarvam_requires_api_key_and_router_codec() -> None:
    async def scenario() -> None:
        with pytest.raises(ValueError, match="SARVAM_API_KEY"):
            await SarvamSTT(settings=Settings(sarvam_api_key=None)).start("call-sarvam")

        websocket = FakeSarvamWebSocket()
        stt = SarvamSTT(
            settings=sarvam_settings(),
            websocket_factory=lambda url, headers: async_value(websocket),
        )
        await stt.start("call-sarvam")
        with pytest.raises(ValueError, match="does not accept codec"):
            await stt.send_audio(
                AudioFrame(
                    call_id="call-sarvam",
                    data=silence_bytes("mulaw_8k", 20),
                    timestamp_ms=1000,
                    sample_rate=8000,
                    codec="mulaw_8k",
                    duration_ms=20,
                )
            )
        await stt.stop()

    asyncio.run(scenario())


def sarvam_settings(**overrides: Any) -> Settings:
    values = {
        "sarvam_api_key": "sarvam-key",
        "sarvam_stt_ws_url": "wss://api.sarvam.ai/speech-to-text/ws",
        "sarvam_stt_model": "saaras:v3",
        "sarvam_stt_mode": "transcribe",
        "sarvam_stt_language_code": "unknown",
        "sarvam_stt_sample_rate": 8000,
        "sarvam_stt_vad_signals": True,
    }
    values.update(overrides)
    return Settings(**values)


def audio_frame() -> AudioFrame:
    return AudioFrame(
        call_id="call-sarvam",
        data=silence_bytes("pcm16_8k", 20),
        timestamp_ms=1000,
        sample_rate=8000,
        codec="pcm16_8k",
        duration_ms=20,
    )


async def async_value(value: Any) -> Any:
    return value
