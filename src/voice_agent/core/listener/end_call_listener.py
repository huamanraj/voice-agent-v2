"""Silent listener that decides when an assistant turn should end the call."""

import asyncio
from dataclasses import dataclass
from typing import Any

from voice_agent.config import Settings
from voice_agent.contracts.ports import LLMPort
from voice_agent.core.playback.playback_tracker import MessagePlayback, estimate_heard_text


END_CALL_LISTENER_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "should_hangup": {"type": "boolean"},
        "confidence": {"type": "number"},
        "reason": {"type": "string"},
    },
    "required": ["should_hangup", "confidence", "reason"],
}


@dataclass(frozen=True, slots=True)
class EndCallDecision:
    should_hangup: bool
    confidence: float
    reason: str
    source: str
    text: str


class EndCallListenerAgent:
    """Decides hangup from the caller's latest explicit end-call intent."""

    def __init__(self, *, call_id: str, settings: Settings, llm: LLMPort) -> None:
        self.call_id = call_id
        self.settings = settings
        self.llm = llm

    async def evaluate(
        self,
        playback: MessagePlayback,
        *,
        latest_user_text: str = "",
    ) -> EndCallDecision | None:
        if not self.settings.end_call_listener_enabled:
            return None

        assistant_text = estimate_heard_text(playback).strip() or playback.source_text.strip()
        user_text = latest_user_text.strip()
        if not assistant_text and not user_text:
            return None

        phrase_decision = self._phrase_decision(user_text, assistant_text)
        if phrase_decision.should_hangup:
            return phrase_decision
        if not _looks_like_user_end_intent(user_text):
            return phrase_decision

        payload = await asyncio.wait_for(
            self.llm.classify(
                self.call_id,
                self._prompt(assistant_text, user_text),
                schema=END_CALL_LISTENER_SCHEMA,
            ),
            timeout=self.settings.end_call_listener_timeout_ms / 1000,
        )
        should_hangup, confidence, reason = _decision_from_payload(payload)
        if should_hangup and not _looks_like_user_end_intent(user_text):
            should_hangup = False
            confidence = 0.0
            reason = f"rejected_without_user_end_intent:{reason}"
        return EndCallDecision(
            should_hangup=should_hangup,
            confidence=confidence,
            reason=reason,
            source="llm",
            text=assistant_text,
        )

    def _phrase_decision(self, user_text: str, assistant_text: str) -> EndCallDecision:
        normalized = _normalize_listener_text(user_text)
        for phrase in self.settings.end_call_phrases:
            normalized_phrase = _normalize_listener_text(phrase)
            if normalized_phrase and _contains_phrase(normalized, normalized_phrase):
                return EndCallDecision(
                    should_hangup=True,
                    confidence=1.0,
                    reason=f"matched_phrase:{phrase}",
                    source="phrase",
                    text=assistant_text,
                )
        return EndCallDecision(
            should_hangup=False,
            confidence=0.0,
            reason="no_user_end_phrase_match",
            source="phrase",
            text=assistant_text,
        )

    @staticmethod
    def _prompt(assistant_text: str, latest_user_text: str) -> str:
        return (
            "You are a silent call-end listener for a live phone agent. "
            "Decide whether the caller's latest user turn clearly asks to end or cut the call. "
            "Return JSON only.\n\n"
            f"Latest user turn: {latest_user_text}\n"
            f"Latest assistant message heard by caller: {assistant_text}\n\n"
            "Set should_hangup true only when the latest user turn clearly contains an end-call "
            "intent such as cut call, hang up, bye, byy, goodbye, alvida, à¤…à¤²à¤µà¤¿à¤¦à¤¾, "
            "à¤¬à¤¾à¤¯, or a mixed phrase like à¤ à¥€à¤• à¤¹à¥ˆ bye. Keep it false for thank you, ok, "
            "haan, theek hai, acknowledgments, or when only the assistant used goodbye words."
        )


def _decision_from_payload(payload: dict[str, Any]) -> tuple[bool, float, str]:
    label = str(payload.get("label") or "").strip().casefold()
    should_hangup = (
        _truthy(payload.get("should_hangup"))
        or _truthy(payload.get("hangup"))
        or _truthy(payload.get("end_call"))
        or label in {"hangup", "end_call", "close_call", "call_end", "goodbye"}
    )
    confidence = _float_value(payload.get("confidence"), 0.0)
    if should_hangup and confidence <= 0:
        confidence = 0.8
    reason = str(payload.get("reason") or label or "listener_decision")
    return should_hangup, confidence, reason


def _truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().casefold() in {"1", "true", "yes", "y", "hangup", "end_call"}
    return bool(value)


def _float_value(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _normalize_listener_text(text: str) -> str:
    normalized_chars = [char.casefold() if char.isalnum() else " " for char in text]
    return " ".join("".join(normalized_chars).split())


def _contains_phrase(normalized_text: str, normalized_phrase: str) -> bool:
    text_tokens = normalized_text.split()
    phrase_tokens = normalized_phrase.split()
    if not text_tokens or not phrase_tokens:
        return False
    phrase_len = len(phrase_tokens)
    return any(
        text_tokens[index : index + phrase_len] == phrase_tokens
        for index in range(0, len(text_tokens) - phrase_len + 1)
    )


def _looks_like_user_end_intent(text: str) -> bool:
    normalized = _normalize_listener_text(text)
    if not normalized:
        return False
    end_phrases = (
        "bye",
        "byy",
        "goodbye",
        "alvida",
        "baay",
        "à¤…à¤²à¤µà¤¿à¤¦à¤¾",
        "à¤¬à¤¾à¤¯",
        "cut call",
        "call cut",
        "end call",
        "call kaat",
        "kaat do",
        "hang up",
        "disconnect",
        "à¤•à¥‰à¤² à¤•à¤¾à¤Ÿ",
        "à¤•à¤¾à¤Ÿ à¤¦à¥‹",
    )
    return any(_contains_phrase(normalized, _normalize_listener_text(phrase)) for phrase in end_phrases)
