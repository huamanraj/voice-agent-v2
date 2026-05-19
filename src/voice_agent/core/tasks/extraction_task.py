"""Post-call structured extraction task."""

from typing import Any

from voice_agent.contracts.ports import LLMPort
from voice_agent.core.tasks.transcript import transcript_text


DEFAULT_EXTRACTION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "customer_name": {"type": ["string", "null"]},
        "issue": {"type": ["string", "null"]},
        "interest_level": {"type": ["string", "null"]},
        "callback_time": {"type": ["string", "null"]},
        "order_number": {"type": ["string", "null"]},
        "sentiment": {"type": ["string", "null"]},
        "escalation_needed": {"type": "boolean"},
    },
    "required": ["escalation_needed"],
}


class ExtractionTask:
    def __init__(self, *, llm: LLMPort, schema: dict[str, Any] | None = None) -> None:
        self.llm = llm
        self.schema = schema or DEFAULT_EXTRACTION_SCHEMA

    async def run(self, call_id: str, final_record: dict[str, Any]) -> dict[str, Any]:
        transcript = transcript_text(final_record)
        if not transcript:
            return {"escalation_needed": False}
        prompt = (
            "Extract post-call fields from this phone transcript. "
            "Use only facts explicitly present. Return JSON only.\n\n"
            f"Transcript:\n{transcript}"
        )
        result = await self.llm.classify(call_id=call_id, prompt=prompt, schema=self.schema)
        return _normalize_extraction(result)


def _normalize_extraction(result: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(result)
    normalized.setdefault("customer_name", None)
    normalized.setdefault("issue", None)
    normalized.setdefault("interest_level", None)
    normalized.setdefault("callback_time", None)
    normalized.setdefault("order_number", None)
    normalized.setdefault("sentiment", None)
    normalized["escalation_needed"] = bool(normalized.get("escalation_needed", False))
    return normalized
