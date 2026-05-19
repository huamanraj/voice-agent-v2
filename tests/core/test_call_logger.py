import asyncio
import json

from voice_agent.core.observability.call_logger import AsyncCallLogger


def test_async_call_logger_writes_jsonl(tmp_path) -> None:
    async def scenario() -> None:
        logger = AsyncCallLogger(call_id="call-1", log_dir=tmp_path)
        logger.start()
        logger.emit("call_started", state="new")
        logger.emit("llm_first_token", turn_id=1, sequence_id=2, provider="litellm")
        await logger.stop(timeout_seconds=1)

        log_files = list(tmp_path.glob("*/*.jsonl"))
        assert len(log_files) == 1
        rows = [json.loads(line) for line in log_files[0].read_text(encoding="utf-8").splitlines()]
        assert [row["event_name"] for row in rows] == ["call_started", "llm_first_token"]
        assert rows[1]["turn_id"] == 1
        assert rows[1]["sequence_id"] == 2
        assert rows[1]["provider"] == "litellm"

    asyncio.run(scenario())
