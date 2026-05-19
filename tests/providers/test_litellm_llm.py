import asyncio
from typing import Any

from voice_agent.config import Settings
from voice_agent.contracts.ports import LLMPort
from voice_agent.providers.llm import LiteLLM


def test_litellm_adapter_satisfies_llm_port() -> None:
    async def fake_completion(**kwargs: Any) -> Any:
        return _stream(["hello"])

    llm = LiteLLM(completion_factory=fake_completion)

    assert isinstance(llm, LLMPort)


def test_litellm_stream_response_yields_delta_content() -> None:
    async def scenario() -> None:
        async def fake_completion(**kwargs: Any) -> Any:
            assert kwargs["stream"] is True
            assert kwargs["messages"][0]["role"] == "system"
            return _stream(["Hello", ", there."])

        llm = LiteLLM(completion_factory=fake_completion)
        tokens = [
            token
            async for token in llm.stream_response(
                "call-1",
                [{"role": "user", "content": "hi"}],
                "response-1",
            )
        ]

        assert tokens == ["Hello", ", there."]

    asyncio.run(scenario())


def test_litellm_cancel_stops_stream_response() -> None:
    async def scenario() -> None:
        async def fake_completion(**kwargs: Any) -> Any:
            return _slow_stream()

        llm = LiteLLM(completion_factory=fake_completion)
        stream = llm.stream_response("call-1", [{"role": "user", "content": "hi"}], "response-1")

        assert await anext(stream) == "first"
        await llm.cancel("response-1")

        try:
            await asyncio.wait_for(anext(stream), timeout=0.1)
        except StopAsyncIteration:
            pass
        else:
            raise AssertionError("cancelled LiteLLM stream should stop")

    asyncio.run(scenario())


def test_litellm_classify_returns_json_dict() -> None:
    async def scenario() -> None:
        async def fake_completion(**kwargs: Any) -> Any:
            assert kwargs["stream"] is False
            assert kwargs["response_format"] == {"type": "json_object"}
            return {"choices": [{"message": {"content": '{"label": "hangup", "confidence": 0.9}'}}]}

        llm = LiteLLM(completion_factory=fake_completion)

        result = await llm.classify("call-1", "Classify this", schema={"type": "object"})

        assert result == {"label": "hangup", "confidence": 0.9}

    asyncio.run(scenario())


def test_litellm_first_token_timeout_records_retryable_error() -> None:
    async def scenario() -> None:
        async def fake_completion(**kwargs: Any) -> Any:
            return _sleeping_stream()

        llm = LiteLLM(
            settings=Settings(llm_first_token_timeout_ms=1, llm_total_timeout_ms=100),
            completion_factory=fake_completion,
        )

        try:
            [
                token
                async for token in llm.stream_response(
                    "call-1",
                    [{"role": "user", "content": "hi"}],
                    "response-1",
                )
            ]
        except TimeoutError:
            pass
        else:
            raise AssertionError("first token timeout should raise")

        assert llm.errors[-1].error_type == "stream_failed"
        assert llm.errors[-1].retryable

    asyncio.run(scenario())


async def _stream(parts: list[str]):
    for part in parts:
        yield {"choices": [{"delta": {"content": part}}]}


async def _slow_stream():
    yield {"choices": [{"delta": {"content": "first"}}]}
    await asyncio.sleep(10)
    yield {"choices": [{"delta": {"content": "stale"}}]}


async def _sleeping_stream():
    await asyncio.sleep(10)
    yield {"choices": [{"delta": {"content": "late"}}]}
