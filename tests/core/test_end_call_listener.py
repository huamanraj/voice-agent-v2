import asyncio

from voice_agent.config import Settings
from voice_agent.core.listener import EndCallListenerAgent
from voice_agent.core.playback.playback_tracker import MessagePlayback
from voice_agent.providers.llm import MockLLM


def test_end_call_listener_matches_user_close_phrase() -> None:
    async def scenario() -> None:
        llm = MockLLM()
        listener = EndCallListenerAgent(
            call_id="call-listener",
            settings=Settings(),
            llm=llm,
        )
        playback = MessagePlayback(
            call_id="call-listener",
            message_id="message-1",
            sequence_id=1,
            full_text="All the best, keep pushing! Byy!",
            fully_played_ms=1000,
        )

        decision = await listener.evaluate(playback, latest_user_text="theek hai bye")

        assert decision is not None
        assert decision.should_hangup
        assert decision.source == "phrase"
        assert decision.confidence == 1.0
        assert llm.requests == []

    asyncio.run(scenario())


def test_end_call_listener_does_not_trust_assistant_goodbye_without_user_intent() -> None:
    async def scenario() -> None:
        llm = EndCallLLM()
        listener = EndCallListenerAgent(
            call_id="call-listener",
            settings=Settings(),
            llm=llm,
        )
        playback = MessagePlayback(
            call_id="call-listener",
            message_id="message-1",
            sequence_id=1,
            full_text="Thank you for your time, bye.",
            fully_played_ms=1000,
        )

        decision = await listener.evaluate(playback, latest_user_text="ok")

        assert decision is not None
        assert not decision.should_hangup
        assert decision.source == "phrase"
        assert decision.reason == "no_user_end_phrase_match"
        assert llm.requests == []

    asyncio.run(scenario())


def test_end_call_listener_does_not_hangup_on_thank_you() -> None:
    async def scenario() -> None:
        llm = EndCallLLM()
        listener = EndCallListenerAgent(
            call_id="call-listener",
            settings=Settings(),
            llm=llm,
        )
        playback = MessagePlayback(
            call_id="call-listener",
            message_id="message-1",
            sequence_id=1,
            full_text="I will send the details after this call. Bye.",
            fully_played_ms=1000,
        )

        decision = await listener.evaluate(playback, latest_user_text="thank you")

        assert decision is not None
        assert not decision.should_hangup
        assert decision.source == "phrase"
        assert llm.requests == []

    asyncio.run(scenario())


def test_end_call_listener_allows_hindi_mixed_bye() -> None:
    async def scenario() -> None:
        listener = EndCallListenerAgent(
            call_id="call-listener",
            settings=Settings(),
            llm=MockLLM(),
        )
        playback = MessagePlayback(
            call_id="call-listener",
            message_id="message-1",
            sequence_id=1,
            full_text="Theek hai, bye.",
            fully_played_ms=1000,
        )

        decision = await listener.evaluate(playback, latest_user_text="theek hai bye")

        assert decision is not None
        assert decision.should_hangup
        assert decision.source == "phrase"

    asyncio.run(scenario())


def test_end_call_listener_returns_none_when_disabled() -> None:
    async def scenario() -> None:
        listener = EndCallListenerAgent(
            call_id="call-listener",
            settings=Settings(end_call_listener_enabled=False),
            llm=MockLLM(),
        )
        playback = MessagePlayback(
            call_id="call-listener",
            message_id="message-1",
            sequence_id=1,
            full_text="Bye.",
            fully_played_ms=1000,
        )

        assert await listener.evaluate(playback) is None

    asyncio.run(scenario())


class EndCallLLM(MockLLM):
    async def classify(self, call_id: str, prompt: str, schema=None):
        self.requests.append({"call_id": call_id, "prompt": prompt, "schema": schema})
        return {"should_hangup": True, "confidence": 0.91, "reason": "wrapped_up"}
