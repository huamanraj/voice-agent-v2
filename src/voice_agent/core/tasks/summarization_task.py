"""Post-call summarization task."""

from typing import Any

from voice_agent.contracts.ports import LLMPort
from voice_agent.core.tasks.transcript import transcript_text


class SummarizationTask:
    def __init__(self, *, llm: LLMPort) -> None:
        self.llm = llm

    async def run(self, call_id: str, final_record: dict[str, Any]) -> dict[str, Any]:
        transcript = transcript_text(final_record)
        if not transcript:
            return {
                "short_summary": "",
                "key_points": [],
                "next_action": None,
                "call_outcome": "no_transcript",
            }
        schema = {
            "type": "object",
            "properties": {
                "short_summary": {"type": "string"},
                "key_points": {"type": "array", "items": {"type": "string"}},
                "next_action": {"type": ["string", "null"]},
                "call_outcome": {"type": "string"},
            },
            "required": ["short_summary", "key_points", "call_outcome"],
        }
        prompt = (
            "Create a neutral post-call summary from this phone transcript. "
            "Do not invent facts. Return JSON with short_summary, key_points, next_action, call_outcome.\n\n"
            f"Transcript:\n{transcript}"
        )
        result = await self.llm.classify(call_id=call_id, prompt=prompt, schema=schema)
        return _normalize_summary(result)


def _normalize_summary(result: dict[str, Any]) -> dict[str, Any]:
    key_points = result.get("key_points", [])
    if not isinstance(key_points, list):
        key_points = [str(key_points)]
    return {
        "short_summary": str(result.get("short_summary") or result.get("summary") or ""),
        "key_points": [str(point) for point in key_points],
        "next_action": result.get("next_action"),
        "call_outcome": str(result.get("call_outcome") or "unknown"),
    }
