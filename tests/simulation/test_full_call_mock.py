import asyncio

from voice_agent.contracts.audio import AudioFrame
from voice_agent.contracts.packets import now_ms
from voice_agent.factory.provider_registry import create_default_registry
from voice_agent.providers.llm import MockLLM
from voice_agent.providers.stt import MockSTT
from voice_agent.providers.telephony import MockTelephony
from voice_agent.providers.tts import MockTTS


def test_full_fake_call_can_run_without_external_apis() -> None:
    async def scenario() -> None:
        registry = create_default_registry()
        telephony = registry.create("telephony", "mock", call_id="call-1")
        stt = registry.create("stt", "mock")
        llm = registry.create("llm", "mock", responses=["Sure, I can help with that."])
        tts = registry.create("tts", "mock")

        assert isinstance(telephony, MockTelephony)
        assert isinstance(stt, MockSTT)
        assert isinstance(llm, MockLLM)
        assert isinstance(tts, MockTTS)

        await telephony.start()
        await stt.start("call-1", language_hint="en-IN")
        await tts.start("call-1", voice="mock-voice", language="en-IN")

        await telephony.enqueue_audio(
            AudioFrame(
                call_id="call-1",
                data=b"caller-audio",
                timestamp_ms=now_ms(),
                sample_rate=8000,
                codec="mulaw_8k",
                duration_ms=20,
                meta={"transcript": "I need help with my policy", "language": "en-IN"},
            )
        )
        await telephony.finish_input()

        async for inbound_frame in telephony.receive_audio():
            await stt.send_audio(inbound_frame)
        await stt.stop()

        transcripts = [event async for event in stt.transcripts()]
        user_text = transcripts[-1].text

        tokens = [
            token
            async for token in llm.stream_response(
                call_id="call-1",
                messages=[{"role": "user", "content": user_text}],
                response_id="response-1",
            )
        ]
        assistant_text = "".join(tokens).strip()

        audio_chunks = [
            frame
            async for frame in tts.synthesize(
                text=assistant_text,
                message_id="message-1",
                sequence_id=1,
            )
        ]
        for chunk in audio_chunks:
            await telephony.send_audio(chunk)

        await telephony.send_checkpoint("checkpoint-1")
        await telephony.stop("test-complete")

        playback_events = [event async for event in telephony.playback_events()]

        assert user_text == "I need help with my policy"
        assert assistant_text == "Sure, I can help with that."
        assert len(telephony.sent_audio) >= 1
        assert all(frame.sequence_id == 1 for frame in telephony.sent_audio)
        assert {event.event_type for event in playback_events} >= {
            "started",
            "checkpoint_played",
        }

    asyncio.run(scenario())
