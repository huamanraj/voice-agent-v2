import asyncio

from voice_agent.contracts.audio import AudioFrame
from voice_agent.contracts.ports import (
    FinalStorePort,
    LLMPort,
    LiveStorePort,
    STTPort,
    TTSPort,
    TelephonyPort,
)
from voice_agent.contracts.packets import now_ms
from voice_agent.factory.provider_registry import create_default_registry
from voice_agent.providers.llm import MockLLM
from voice_agent.providers.storage import MemoryStore
from voice_agent.providers.stt import MockSTT
from voice_agent.providers.telephony import MockTelephony
from voice_agent.providers.tts import MockTTS


def test_mock_providers_satisfy_runtime_ports() -> None:
    assert isinstance(MockTelephony(call_id="call-1"), TelephonyPort)
    assert isinstance(MockSTT(), STTPort)
    assert isinstance(MockTTS(), TTSPort)
    assert isinstance(MockLLM(), LLMPort)

    memory_store = MemoryStore()
    assert isinstance(memory_store, LiveStorePort)
    assert isinstance(memory_store, FinalStorePort)


def test_default_registry_creates_mock_providers() -> None:
    registry = create_default_registry()

    assert registry.available("telephony") == ("mock", "vobiz")
    assert isinstance(registry.create("telephony", "mock", call_id="call-1"), MockTelephony)
    assert isinstance(registry.create("stt", "mock"), MockSTT)
    assert isinstance(registry.create("tts", "mock"), MockTTS)
    assert isinstance(registry.create("llm", "mock"), MockLLM)
    assert isinstance(registry.create("live_store", "memory"), MemoryStore)
    assert isinstance(registry.create("final_store", "memory"), MemoryStore)


def test_mock_stt_emits_transcript_from_audio_metadata() -> None:
    async def scenario() -> None:
        stt = MockSTT()
        await stt.start("call-1", language_hint="hi-IN")
        await stt.send_audio(
            AudioFrame(
                call_id="call-1",
                data=b"fake-audio",
                timestamp_ms=now_ms(),
                sample_rate=8000,
                codec="mulaw_8k",
                duration_ms=20,
                meta={"transcript": "haan mujhe policy chahiye", "confidence": 0.92},
            )
        )
        await stt.stop()

        transcripts = [event async for event in stt.transcripts()]

        assert transcripts[0].text == "haan mujhe policy chahiye"
        assert transcripts[0].language == "hi-IN"
        assert transcripts[0].is_final

    asyncio.run(scenario())


def test_memory_store_keeps_copies_isolated() -> None:
    async def scenario() -> None:
        store = MemoryStore()
        state = {"status": "listening", "nested": {"turn": 1}}
        await store.set_call_state("call-1", state)
        state["nested"]["turn"] = 99

        saved = await store.get_call_state("call-1")

        assert saved == {"status": "listening", "nested": {"turn": 1}}

    asyncio.run(scenario())
