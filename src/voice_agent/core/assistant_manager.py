"""Higher-level assistant workflow manager for conversation and post-call tasks."""

import asyncio
from dataclasses import dataclass, field
from typing import Any

from voice_agent.config import Settings, get_settings
from voice_agent.contracts.ports import FinalStorePort, LLMPort
from voice_agent.core.session_orchestrator import SessionOrchestrator, SessionStats
from voice_agent.core.tasks.extraction_task import ExtractionTask
from voice_agent.core.tasks.summarization_task import SummarizationTask
from voice_agent.core.tasks.webhook_task import WebhookTask


@dataclass(slots=True)
class AssistantRunResult:
    call_id: str
    stats: SessionStats
    final_record: dict[str, Any]
    post_call: dict[str, Any] = field(default_factory=dict)


class AssistantManager:
    def __init__(
        self,
        *,
        call_id: str,
        orchestrator: SessionOrchestrator,
        llm: LLMPort,
        settings: Settings | None = None,
        final_store: FinalStorePort | None = None,
        webhook_url: str | None = None,
    ) -> None:
        self.call_id = call_id
        self.orchestrator = orchestrator
        self.llm = llm
        self.settings = settings or get_settings()
        self.final_store = final_store
        self.webhook_url = webhook_url if webhook_url is not None else self.settings.post_call_webhook_url

    async def run(self) -> AssistantRunResult:
        stats = await self.orchestrator.run()
        final_record = self.orchestrator.final_record or {}
        post_call = await self.run_post_call_tasks(final_record)
        if post_call:
            final_record = {**final_record, "post_call": post_call}
            target_store = self.final_store or self.orchestrator.providers.final_store
            if target_store is not None:
                await target_store.save_call(self.call_id, final_record)
        return AssistantRunResult(
            call_id=self.call_id,
            stats=stats,
            final_record=final_record,
            post_call=post_call,
        )

    async def run_post_call_tasks(self, final_record: dict[str, Any]) -> dict[str, Any]:
        if not self.settings.post_call_enabled:
            return {}

        async def _run_tasks() -> dict[str, Any]:
            summary_task = SummarizationTask(llm=self.llm)
            extraction_task = ExtractionTask(llm=self.llm)
            summary = await summary_task.run(self.call_id, final_record)
            extraction = await extraction_task.run(self.call_id, final_record)
            webhook_result: dict[str, Any] | None = None
            if self.webhook_url:
                webhook_result = await WebhookTask(self.webhook_url).run(
                    {
                        "call_id": self.call_id,
                        "summary": summary,
                        "extraction": extraction,
                        "metrics": final_record.get("metrics", {}),
                    }
                )
            return {
                "summary": summary,
                "extraction": extraction,
                "webhook": webhook_result,
            }

        try:
            return await asyncio.wait_for(_run_tasks(), timeout=self.settings.post_call_timeout_seconds)
        except Exception as exc:
            return {
                "error": {
                    "type": exc.__class__.__name__,
                    "message": str(exc),
                }
            }
