"""Provider registry without importing concrete adapters into core."""

from collections.abc import Callable
from typing import Any


class ProviderRegistry:
    def __init__(self) -> None:
        self._providers: dict[str, dict[str, Callable[..., Any]]] = {}

    def register(self, category: str, name: str, factory: Callable[..., Any]) -> None:
        self._providers.setdefault(category, {})[name] = factory

    def create(self, category: str, name: str, **kwargs: Any) -> Any:
        try:
            factory = self._providers[category][name]
        except KeyError as exc:
            available = sorted(self._providers.get(category, {}))
            raise LookupError(
                f"Provider '{name}' is not registered for '{category}'. "
                f"Available: {available}"
            ) from exc
        return factory(**kwargs)

    def available(self, category: str) -> tuple[str, ...]:
        return tuple(sorted(self._providers.get(category, {})))


def create_default_registry() -> ProviderRegistry:
    from voice_agent.providers.llm.litellm import LiteLLM
    from voice_agent.providers.llm.mock import MockLLM
    from voice_agent.providers.storage.memory_store import MemoryStore
    from voice_agent.providers.storage.postgres_final_store import PostgresFinalStore
    from voice_agent.providers.storage.redis_live_store import RedisLiveStore
    from voice_agent.providers.stt.deepgram import DeepgramSTT
    from voice_agent.providers.stt.mock import MockSTT
    from voice_agent.providers.stt.sarvam import SarvamSTT
    from voice_agent.providers.telephony.mock import MockTelephony
    from voice_agent.providers.telephony.vobiz import VobizTelephony
    from voice_agent.providers.tts.cartesia import CartesiaTTS
    from voice_agent.providers.tts.mock import MockTTS
    from voice_agent.providers.tts.sarvam import SarvamTTS

    registry = ProviderRegistry()
    registry.register("telephony", "mock", MockTelephony)
    registry.register("telephony", "vobiz", VobizTelephony)
    registry.register("stt", "deepgram", DeepgramSTT)
    registry.register("stt", "mock", MockSTT)
    registry.register("stt", "sarvam", SarvamSTT)
    registry.register("tts", "cartesia", CartesiaTTS)
    registry.register("tts", "mock", MockTTS)
    registry.register("tts", "sarvam", SarvamTTS)
    registry.register("llm", "litellm", LiteLLM)
    registry.register("llm", "mock", MockLLM)
    registry.register("live_store", "memory", MemoryStore)
    registry.register("live_store", "redis", RedisLiveStore)
    registry.register("final_store", "memory", MemoryStore)
    registry.register("final_store", "postgres", PostgresFinalStore)
    registry.register("memory", "memory", MemoryStore)
    return registry
