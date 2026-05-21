import asyncio

from voice_agent.config import Settings
from voice_agent.core.provider_warmup import ProviderWarmupPool
from voice_agent.factory.provider_registry import ProviderRegistry
from voice_agent.providers.llm import MockLLM
from voice_agent.providers.stt import MockSTT
from voice_agent.providers.tts import MockTTS


class HealthSTT(MockSTT):
    def __init__(self) -> None:
        super().__init__()
        self.alive = True
        self.stop_called = False

    async def health_check(self) -> bool:
        return self.alive

    async def stop(self) -> None:
        self.stop_called = True
        await super().stop()


class HealthTTS(MockTTS):
    def __init__(self) -> None:
        super().__init__()
        self.alive = True

    async def health_check(self) -> bool:
        return self.alive


def test_provider_warmup_claim_discards_dead_speech_bundle() -> None:
    async def scenario() -> None:
        created_stt: list[HealthSTT] = []
        registry = ProviderRegistry()
        registry.register("stt", "mock", lambda: create_stt(created_stt))
        registry.register("tts", "mock", HealthTTS)
        registry.register("llm", "mock", MockLLM)
        registry.register("live_store", "memory", lambda: None)
        registry.register("final_store", "memory", lambda: None)
        settings = Settings(
            stt_provider="mock",
            tts_provider="mock",
            llm_provider="mock",
            live_store_provider="memory",
            final_store_provider="memory",
            agent_config_path="missing-agent-test-file.json",
            default_agent_id="fallback",
        )
        pool = ProviderWarmupPool(settings, registry)

        await pool.prewarm("prewarm-dead")
        created_stt[0].alive = False

        assert await pool.claim(prewarm_id="prewarm-dead", call_id="call-1") is None
        assert created_stt[0].stop_called

    asyncio.run(scenario())


def test_provider_warmup_health_monitor_discards_dropped_bundle() -> None:
    async def scenario() -> None:
        created_stt: list[HealthSTT] = []
        registry = ProviderRegistry()
        registry.register("stt", "mock", lambda: create_stt(created_stt))
        registry.register("tts", "mock", HealthTTS)
        registry.register("llm", "mock", MockLLM)
        registry.register("live_store", "memory", lambda: None)
        registry.register("final_store", "memory", lambda: None)
        settings = Settings(
            stt_provider="mock",
            tts_provider="mock",
            llm_provider="mock",
            live_store_provider="memory",
            final_store_provider="memory",
            provider_health_check_seconds=0.01,
            agent_config_path="missing-agent-test-file.json",
            default_agent_id="fallback",
        )
        pool = ProviderWarmupPool(settings, registry)

        await pool.prewarm("prewarm-watch")
        created_stt[0].alive = False
        await wait_until(lambda: "prewarm-watch" not in pool._entries)

        assert created_stt[0].stop_called

    asyncio.run(scenario())


def create_stt(created_stt: list[HealthSTT]) -> HealthSTT:
    stt = HealthSTT()
    created_stt.append(stt)
    return stt


async def wait_until(predicate, *, timeout_seconds: float = 0.5) -> None:
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout_seconds
    while loop.time() < deadline:
        if predicate():
            return
        await asyncio.sleep(0.005)
    raise AssertionError("condition was not met before timeout")
