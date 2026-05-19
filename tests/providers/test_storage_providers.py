import asyncio
import json

from voice_agent.providers.storage.postgres_final_store import PostgresFinalStore
from voice_agent.providers.storage.redis_live_store import RedisLiveStore


class FakeRedisPipeline:
    def __init__(self, client) -> None:
        self.client = client
        self.commands = []

    def set(self, key, value, ex=None) -> None:
        self.commands.append(("set", key, value, ex))

    async def execute(self) -> None:
        for _, key, value, ex in self.commands:
            self.client.values[key] = value
            self.client.ttls[key] = ex


class FakeRedis:
    def __init__(self) -> None:
        self.values = {}
        self.ttls = {}
        self.deleted = []

    def pipeline(self):
        return FakeRedisPipeline(self)

    async def get(self, key):
        return self.values.get(key)

    async def delete(self, *keys):
        self.deleted.extend(keys)
        for key in keys:
            self.values.pop(key, None)


def test_redis_live_store_writes_state_with_ttl() -> None:
    async def scenario() -> None:
        client = FakeRedis()
        store = RedisLiveStore(redis_url="redis://test", ttl_seconds=60, client=client)
        await store.set_call_state(
            "call-1",
            {
                "call_id": "call-1",
                "state": "listening",
                "updated_ms": 123,
                "turns": [{"speaker": "user", "text": "hello"}],
                "metrics": {"avg_llm_first_token_ms": 100},
                "errors": [],
            },
        )

        state = await store.get_call_state("call-1")
        assert state["state"] == "listening"
        assert client.ttls["call:call-1:state"] == 60
        assert json.loads(client.values["call:call-1:turns"])[0]["text"] == "hello"

        await store.delete_call_state("call-1")
        assert "call:call-1:state" in client.deleted

    asyncio.run(scenario())


class FakeTransaction:
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False


class FakeConnection:
    def __init__(self) -> None:
        self.executed = []

    def transaction(self):
        return FakeTransaction()

    async def execute(self, sql, *args):
        self.executed.append((sql, args))


class FakeAcquire:
    def __init__(self, conn) -> None:
        self.conn = conn

    async def __aenter__(self):
        return self.conn

    async def __aexit__(self, exc_type, exc, tb):
        return False


class FakePool:
    def __init__(self, conn) -> None:
        self.conn = conn

    def acquire(self):
        return FakeAcquire(self.conn)


def test_postgres_final_store_persists_call_turns_metrics_and_errors(tmp_path) -> None:
    async def scenario() -> None:
        conn = FakeConnection()
        store = PostgresFinalStore(dsn="postgresql://test", retry_dir=str(tmp_path), pool=FakePool(conn))
        await store.save_call(
            "call-1",
            {
                "call_id": "call-1",
                "started_ms": 1000,
                "ended_ms": 2000,
                "reason": "closed",
                "transcript_summary": "User asked for help.",
                "turns": [{"speaker": "user", "text": "help", "timestamp_ms": 1200}],
                "metrics": {"avg_llm_first_token_ms": 500, "interruption_count": 0},
                "provider_errors": [
                    {
                        "provider": "tts",
                        "error_type": "timeout",
                        "error_code": "TimeoutError",
                        "message": "slow",
                        "retryable": True,
                        "details": {"x": 1},
                    }
                ],
                "errors": ["slow"],
            },
        )

        sql_text = "\n".join(sql for sql, _ in conn.executed)
        assert "INSERT INTO calls" in sql_text
        assert "INSERT INTO turns" in sql_text
        assert "INSERT INTO call_metrics" in sql_text
        assert "INSERT INTO provider_errors" in sql_text
        assert list(tmp_path.glob("*.json")) == []

    asyncio.run(scenario())


def test_postgres_final_store_writes_retry_file_on_failure(tmp_path) -> None:
    class BrokenStore(PostgresFinalStore):
        async def _save_call(self, call_id, record):
            raise RuntimeError("database down")

    async def scenario() -> None:
        store = BrokenStore(dsn="postgresql://test", retry_dir=str(tmp_path))
        await store.save_call("call-2", {"call_id": "call-2"})

        retry_files = list(tmp_path.glob("*.json"))
        assert len(retry_files) == 1
        payload = json.loads(retry_files[0].read_text(encoding="utf-8"))
        assert payload["call_id"] == "call-2"
        assert "database down" in payload["error"]

    asyncio.run(scenario())
