import asyncio

from voice_agent.core.response.sentence_aggregator import (
    SentenceAggregator,
    aggregate_token_stream,
    sanitize_for_speech,
)


def test_sentence_aggregator_flushes_on_sentence_end() -> None:
    aggregator = SentenceAggregator()

    chunks = aggregator.add("Okay, I can help.")

    assert chunks == ["Okay, I can help."]


def test_sentence_aggregator_splits_long_text_at_word_boundary() -> None:
    aggregator = SentenceAggregator(min_chars=10, max_chars=24, timeout_ms=500)

    chunks = aggregator.add("Please share your policy number so I can check it")

    assert chunks == ["Please share your"]
    assert aggregator.flush() == "policy number so I can check it"


def test_sanitize_for_speech_removes_markdown_markers() -> None:
    assert sanitize_for_speech("## Title\n- **hello** `there`") == "Title hello there"


def test_aggregate_token_stream_flushes_on_timeout() -> None:
    async def scenario() -> None:
        async def tokens():
            yield "One partial thought"
            await asyncio.sleep(0.02)

        chunks = [
            chunk
            async for chunk in aggregate_token_stream(
                tokens(),
                min_chars=80,
                max_chars=160,
                timeout_ms=5,
            )
        ]

        assert chunks == ["One partial thought"]

    asyncio.run(scenario())
