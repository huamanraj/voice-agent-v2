"""Redis-backed live call state store."""

import json
from typing import Any


class RedisLiveStore:
    provider_name = "redis"

    def __init__(
        self,
        *,
        redis_url: str,
        ttl_seconds: int = 21600,
        client: Any | None = None,
    ) -> None:
        self.redis_url = redis_url
        self.ttl_seconds = ttl_seconds
        self._client = client

    async def _redis(self) -> Any:
        if self._client is not None:
            return self._client
        try:
            from redis import asyncio as redis_asyncio
        except ImportError as exc:
            raise RuntimeError(
                "RedisLiveStore requires the 'redis' package. Install project dependencies before using Redis."
            ) from exc
        self._client = redis_asyncio.from_url(self.redis_url, decode_responses=True)
        return self._client

    async def get_call_state(self, call_id: str) -> dict[str, Any] | None:
        client = await self._redis()
        raw = await client.get(_key(call_id, "state"))
        if raw is None:
            return None
        return json.loads(raw)

    async def set_call_state(self, call_id: str, state: dict[str, Any]) -> None:
        client = await self._redis()
        state_json = json.dumps(state, ensure_ascii=False, separators=(",", ":"))
        pipe = client.pipeline()
        pipe.set(_key(call_id, "state"), state_json, ex=self.ttl_seconds)
        pipe.set(_key(call_id, "meta"), json.dumps(_meta_from_state(state), separators=(",", ":")), ex=self.ttl_seconds)
        pipe.set(
            _key(call_id, "active_response"),
            json.dumps(state.get("active_response", {}), separators=(",", ":")),
            ex=self.ttl_seconds,
        )
        pipe.set(_key(call_id, "turns"), json.dumps(state.get("turns", []), ensure_ascii=False), ex=self.ttl_seconds)
        pipe.set(_key(call_id, "metrics"), json.dumps(state.get("metrics", {}), separators=(",", ":")), ex=self.ttl_seconds)
        pipe.set(_key(call_id, "errors"), json.dumps(state.get("errors", []), ensure_ascii=False), ex=self.ttl_seconds)
        await pipe.execute()

    async def delete_call_state(self, call_id: str) -> None:
        client = await self._redis()
        await client.delete(
            _key(call_id, "meta"),
            _key(call_id, "state"),
            _key(call_id, "active_response"),
            _key(call_id, "turns"),
            _key(call_id, "metrics"),
            _key(call_id, "errors"),
        )

    async def close(self) -> None:
        if self._client is not None:
            close = getattr(self._client, "aclose", None) or getattr(self._client, "close", None)
            if close is not None:
                result = close()
                if hasattr(result, "__await__"):
                    await result


def _key(call_id: str, suffix: str) -> str:
    return f"call:{call_id}:{suffix}"


def _meta_from_state(state: dict[str, Any]) -> dict[str, Any]:
    return {
        "state": state.get("state"),
        "call_id": state.get("call_id"),
        "updated_ms": state.get("updated_ms"),
        "current_sequence_id": state.get("current_sequence_id"),
    }
