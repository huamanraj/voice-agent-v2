import asyncio
import base64
import json
from typing import Any

import pytest

from voice_agent.audio.converter import silence_bytes
from voice_agent.contracts.audio import AudioFrame
from voice_agent.contracts.ports import TelephonyPort
from voice_agent.factory.provider_registry import create_default_registry
from voice_agent.providers.telephony import VobizTelephony


class FakeWebSocketDisconnect(Exception):
    pass


class FakeVobizWebSocket:
    def __init__(self, *, fail_send: bool = False) -> None:
        self.fail_send = fail_send
        self.closed = False
        self.sent_text: list[str] = []
        self.incoming: asyncio.Queue[str | Exception] = asyncio.Queue()

    async def receive_text(self) -> str:
        item = await self.incoming.get()
        if isinstance(item, Exception):
            raise item
        return item

    async def send_text(self, data: str) -> None:
        if self.fail_send:
            raise RuntimeError("send exploded")
        self.sent_text.append(data)

    async def close(self) -> None:
        self.closed = True

    async def feed_json(self, packet: dict[str, Any]) -> None:
        await self.incoming.put(json.dumps(packet))

    async def disconnect(self) -> None:
        await self.incoming.put(FakeWebSocketDisconnect("websocket closed"))


def test_vobiz_satisfies_telephony_port_and_registry() -> None:
    websocket = FakeVobizWebSocket()
    adapter = VobizTelephony(websocket)
    registry = create_default_registry()

    assert isinstance(adapter, TelephonyPort)
    assert registry.available("telephony") == ("mock", "vobiz")
    assert isinstance(registry.create("telephony", "vobiz", websocket=websocket), VobizTelephony)


def test_vobiz_start_and_media_decode_to_audio_frame() -> None:
    async def scenario() -> None:
        websocket = FakeVobizWebSocket()
        adapter = VobizTelephony(websocket)
        payload = silence_bytes("mulaw_8k", 20)

        await websocket.feed_json({"event": "connected", "protocol": "Call"})
        await websocket.feed_json(start_packet())
        await websocket.feed_json({"event": "dtmf", "dtmf": {"digit": "1"}})
        await websocket.feed_json(
            {
                "sequenceNumber": 2,
                "event": "media",
                "media": {
                    "track": "inbound",
                    "timestamp": "1234",
                    "chunk": "7",
                    "payload": base64.b64encode(payload).decode("ascii"),
                },
            }
        )
        await websocket.feed_json({"event": "stop"})
        await adapter.start()

        frames = [frame async for frame in adapter.receive_audio()]

        assert len(frames) == 1
        assert adapter.errors == []
        assert frames[0].call_id == "call-123"
        assert frames[0].meta["stream_id"] == "stream-123"
        assert frames[0].codec == "mulaw_8k"
        assert frames[0].sample_rate == 8000
        assert frames[0].sequence_id == 7
        assert frames[0].duration_ms == 20
        assert frames[0].data == payload
        assert adapter.stopped

    asyncio.run(scenario())


def test_vobiz_start_accepts_sid_style_fields_from_docs() -> None:
    async def scenario() -> None:
        websocket = FakeVobizWebSocket()
        adapter = VobizTelephony(websocket)

        await websocket.feed_json(
            {
                "event": "start",
                "start": {
                    "CallSid": "call-sid-123",
                    "StreamSid": "stream-sid-123",
                    "media_format": {"encoding": "audio/x-mulaw", "sampleRate": 8000},
                },
            }
        )
        await adapter.start()
        await wait_until(lambda: adapter.stream_id == "stream-sid-123")

        assert adapter.call_id == "call-sid-123"
        assert adapter.errors == []
        await adapter.stop("test_done")

    asyncio.run(scenario())


def test_vobiz_send_audio_chunks_20ms_play_audio_messages() -> None:
    async def scenario() -> None:
        websocket = FakeVobizWebSocket()
        adapter = VobizTelephony(websocket)
        frame = AudioFrame(
            call_id="call-123",
            data=silence_bytes("mulaw_8k", 60),
            timestamp_ms=1000,
            sample_rate=8000,
            codec="mulaw_8k",
            duration_ms=60,
        )

        await adapter.send_audio(frame)

        sent = sent_packets(websocket)
        assert [packet["event"] for packet in sent] == ["playAudio", "playAudio", "playAudio"]
        assert all(packet["media"]["contentType"] == "audio/x-mulaw" for packet in sent)
        assert all(packet["media"]["sampleRate"] == 8000 for packet in sent)
        assert [len(base64.b64decode(packet["media"]["payload"])) for packet in sent] == [
            160,
            160,
            160,
        ]

    asyncio.run(scenario())


def test_vobiz_checkpoint_receives_played_stream_event() -> None:
    async def scenario() -> None:
        websocket = FakeVobizWebSocket()
        adapter = VobizTelephony(websocket)

        await websocket.feed_json(start_packet())
        await adapter.start()
        await wait_until(lambda: adapter.stream_id == "stream-123")

        await adapter.send_checkpoint("response-3")
        await websocket.feed_json({"sequenceNumber": 9, "event": "playedStream", "name": "response-3"})
        playback_event = await asyncio.wait_for(anext(adapter.playback_events()), 0.2)

        assert sent_packets(websocket)[0] == {
            "event": "checkpoint",
            "streamId": "stream-123",
            "name": "response-3",
        }
        assert playback_event.event_type == "checkpoint_played"
        assert playback_event.checkpoint_id == "response-3"
        assert playback_event.sequence_id == 9
        await adapter.stop("test_done")

    asyncio.run(scenario())


def test_vobiz_clear_audio_waits_for_ack_without_blocking_forever() -> None:
    async def scenario() -> None:
        websocket = FakeVobizWebSocket()
        adapter = VobizTelephony(websocket, clear_timeout_seconds=0.2)

        await websocket.feed_json(start_packet())
        await adapter.start()
        await wait_until(lambda: adapter.stream_id == "stream-123")

        clear_task = asyncio.create_task(adapter.clear_playback("barge-in"))
        await wait_until(lambda: sent_packets(websocket) != [])
        await websocket.feed_json({"sequenceNumber": 10, "event": "clearedAudio", "streamId": "stream-123"})
        await asyncio.wait_for(clear_task, 0.2)
        playback_event = await asyncio.wait_for(anext(adapter.playback_events()), 0.2)

        assert sent_packets(websocket)[0] == {"event": "clearAudio", "streamId": "stream-123"}
        assert playback_event.event_type == "cleared"
        assert playback_event.call_id == "call-123"
        await adapter.stop("test_done")

    asyncio.run(scenario())


def test_vobiz_clear_audio_timeout_returns_safely() -> None:
    async def scenario() -> None:
        websocket = FakeVobizWebSocket()
        adapter = VobizTelephony(websocket, clear_timeout_seconds=0.001)
        adapter.stream_id = "stream-timeout"

        await asyncio.wait_for(adapter.clear_playback("timeout-check"), 0.1)

        assert sent_packets(websocket) == [{"event": "clearAudio", "streamId": "stream-timeout"}]

    asyncio.run(scenario())


def test_vobiz_control_messages_before_start_record_errors() -> None:
    async def scenario() -> None:
        websocket = FakeVobizWebSocket()
        adapter = VobizTelephony(websocket)

        await adapter.clear_playback("early-clear")
        await adapter.send_checkpoint("early-checkpoint")

        assert websocket.sent_text == []
        assert [error.error_type for error in adapter.errors] == [
            "missing_stream_id",
            "missing_stream_id",
        ]

    asyncio.run(scenario())


def test_vobiz_unsupported_start_media_format_ends_stream_safely() -> None:
    async def scenario() -> None:
        websocket = FakeVobizWebSocket()
        adapter = VobizTelephony(websocket)

        await websocket.feed_json(
            start_packet(media_format={"encoding": "audio/opus", "sampleRate": 48000})
        )
        await adapter.start()

        frames = [frame async for frame in adapter.receive_audio()]

        assert frames == []
        assert adapter.stopped
        assert any(error.error_type == "invalid_start_media_format" for error in adapter.errors)

    asyncio.run(scenario())


def test_vobiz_malformed_media_is_recorded_and_does_not_kill_stream() -> None:
    async def scenario() -> None:
        websocket = FakeVobizWebSocket()
        adapter = VobizTelephony(websocket)

        await websocket.feed_json(start_packet())
        await websocket.feed_json(
            {
                "event": "media",
                "media": {
                    "track": "inbound",
                    "timestamp": "1000",
                    "chunk": 1,
                    "payload": "@@not-base64@@",
                },
            }
        )
        await websocket.feed_json({"event": "stop"})
        await adapter.start()

        frames = [frame async for frame in adapter.receive_audio()]

        assert frames == []
        assert any(error.error_type == "invalid_media_payload" for error in adapter.errors)
        assert adapter.stopped

    asyncio.run(scenario())


def test_vobiz_send_failure_is_recorded_and_raised() -> None:
    async def scenario() -> None:
        websocket = FakeVobizWebSocket(fail_send=True)
        adapter = VobizTelephony(websocket)
        frame = AudioFrame(
            call_id="call-123",
            data=silence_bytes("mulaw_8k", 20),
            timestamp_ms=1000,
            sample_rate=8000,
            codec="mulaw_8k",
            duration_ms=20,
        )

        with pytest.raises(RuntimeError, match="send exploded"):
            await adapter.send_audio(frame)

        assert any(error.error_type == "send_failed" for error in adapter.errors)

    asyncio.run(scenario())


def test_vobiz_websocket_close_ends_receive_stream_safely() -> None:
    async def scenario() -> None:
        websocket = FakeVobizWebSocket()
        adapter = VobizTelephony(websocket)

        await websocket.feed_json(start_packet())
        await websocket.disconnect()
        await adapter.start()

        frames = [frame async for frame in adapter.receive_audio()]

        assert frames == []
        assert adapter.stopped
        assert adapter.stop_reason == "websocket_closed"

    asyncio.run(scenario())


def test_vobiz_l16_media_is_byte_swapped_to_internal_pcm16() -> None:
    async def scenario() -> None:
        websocket = FakeVobizWebSocket()
        adapter = VobizTelephony(websocket)
        wire_payload = b"\x12\x34\xab\xcd" * 160

        await websocket.feed_json(
            start_packet(media_format={"encoding": "audio/x-l16", "sampleRate": 16000})
        )
        await websocket.feed_json(
            {
                "event": "media",
                "media": {
                    "track": "inbound",
                    "timestamp": "1000",
                    "chunk": 1,
                    "payload": base64.b64encode(wire_payload).decode("ascii"),
                },
            }
        )
        await websocket.feed_json({"event": "stop"})
        await adapter.start()

        frames = [frame async for frame in adapter.receive_audio()]

        assert frames[0].codec == "pcm16_16k"
        assert frames[0].sample_rate == 16000
        assert frames[0].data[:4] == b"\x34\x12\xcd\xab"
        assert frames[0].duration_ms == 20

    asyncio.run(scenario())


def start_packet(media_format: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "sequenceNumber": 0,
        "event": "start",
        "start": {
            "callId": "call-123",
            "streamId": "stream-123",
            "tracks": ["inbound"],
            "mediaFormat": media_format or {"encoding": "audio/x-mulaw", "sampleRate": 8000},
        },
    }


def sent_packets(websocket: FakeVobizWebSocket) -> list[dict[str, Any]]:
    return [json.loads(message) for message in websocket.sent_text]


async def wait_until(predicate: Any, *, timeout_seconds: float = 0.2) -> None:
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout_seconds
    while loop.time() < deadline:
        if predicate():
            return
        await asyncio.sleep(0)
    raise AssertionError("condition was not met before timeout")
