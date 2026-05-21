import asyncio
from typing import Any

from voice_agent.config import Settings
from voice_agent.contracts.audio import AudioFrame
from voice_agent.contracts.capabilities import LLMCapabilities
from voice_agent.contracts.packets import now_ms
from voice_agent.core.assistant_manager import AssistantManager
from voice_agent.core.session_orchestrator import SessionOrchestrator, SessionProviders
from voice_agent.providers.storage import MemoryStore
from voice_agent.providers.stt import MockSTT
from voice_agent.providers.telephony import MockTelephony
from voice_agent.providers.tts import MockTTS


class PostCallLLM:
    provider_name = "post-call"
    capabilities = LLMCapabilities(
        supports_streaming=True,
        supports_json_mode=True,
        supports_tool_calling=False,
    )

    def __init__(self) -> None:
        self.classify_calls: list[dict[str, Any]] = []

    async def stream_response(self, call_id, messages, response_id):
        yield "Sure, I can help."

    async def classify(self, call_id, prompt, schema=None):
        self.classify_calls.append({"call_id": call_id, "prompt": prompt, "schema": schema})
        if "short_summary" in prompt:
            return {
                "short_summary": "The user asked for help.",
                "key_points": ["Asked for help"],
                "next_action": "Follow up",
                "call_outcome": "completed",
            }
        return {
            "issue": "help request",
            "sentiment": "neutral",
            "escalation_needed": False,
        }

    async def cancel(self, response_id):
        return None

    async def stop(self):
        return None


def test_assistant_manager_runs_post_call_tasks_after_conversation() -> None:
    async def scenario() -> None:
        live_store = MemoryStore()
        final_store = MemoryStore()
        telephony = MockTelephony(call_id="call-1")
        llm = PostCallLLM()
        orchestrator = SessionOrchestrator(
            call_id="call-1",
            providers=SessionProviders(
                telephony=telephony,
                stt=MockSTT(),
                tts=MockTTS(),
                llm=llm,
                live_store=live_store,
                final_store=final_store,
            ),
            settings=Settings(
                post_call_enabled=True,
                min_user_speech_ms=0,
                min_silence_for_turn_end_ms=0,
                smart_turn_enabled=False,
                llm_sentence_timeout_ms=1,
                end_call_listener_enabled=False,
            ),
        )
        await telephony.enqueue_audio(
            AudioFrame(
                call_id="call-1",
                data=b"audio",
                timestamp_ms=now_ms(),
                sample_rate=8000,
                codec="mulaw_8k",
                duration_ms=20,
                meta={"transcript": "I need help", "language": "en-IN"},
            )
        )
        await telephony.finish_input()

        result = await AssistantManager(
            call_id="call-1",
            orchestrator=orchestrator,
            llm=llm,
            final_store=final_store,
            settings=orchestrator.settings,
        ).run()

        assert result.stats.user_turns_finalized == 1
        assert result.post_call["summary"]["call_outcome"] == "completed"
        assert result.post_call["extraction"]["issue"] == "help request"
        assert len(llm.classify_calls) == 2
        assert final_store.call_records["call-1"]["post_call"]["summary"]["short_summary"]

    asyncio.run(scenario())
