"""Conversation context records used to build LLM history."""

from dataclasses import dataclass

from voice_agent.contracts.events import UserTurnFinal
from voice_agent.contracts.packets import now_ms
from voice_agent.core.context.slots import SlotTracker
from voice_agent.core.context.summarizer import ConversationSummarizer, SummaryTurn
from voice_agent.core.playback.playback_tracker import MessagePlayback, estimate_heard_text


@dataclass(slots=True)
class UserTurnRecord:
    turn_id: int
    text: str
    timestamp_ms: int
    confidence: float
    language: str | None


@dataclass(slots=True)
class AssistantTurnRecord:
    message_id: str
    sequence_id: int
    full_text: str = ""
    heard_text: str = ""
    interrupted: bool = False
    created_ms: int = 0
    fully_played_ms: int | None = None


class ContextManager:
    def __init__(
        self,
        *,
        system_prompt: str,
        max_recent_turns: int = 12,
        summary_max_chars: int = 1200,
    ) -> None:
        self.system_prompt = system_prompt
        self.max_recent_turns = max_recent_turns
        self.summary_text = ""
        self.summarizer = ConversationSummarizer(summary_max_chars)
        self.slots = SlotTracker()
        self.user_turns: list[UserTurnRecord] = []
        self.assistant_turns: list[AssistantTurnRecord] = []
        self._assistant_by_message_id: dict[str, AssistantTurnRecord] = {}

    def append_user_turn(self, turn: UserTurnFinal) -> None:
        if self.user_turns and self.user_turns[-1].turn_id == turn.turn_id:
            return
        self.user_turns.append(
            UserTurnRecord(
                turn_id=turn.turn_id,
                text=turn.text,
                timestamp_ms=turn.end_ms or now_ms(),
                confidence=turn.confidence,
                language=turn.language,
            )
        )
        self._trim()

    def start_assistant_turn(self, *, message_id: str, sequence_id: int) -> AssistantTurnRecord:
        existing = self._assistant_by_message_id.get(message_id)
        if existing is not None:
            return existing
        record = AssistantTurnRecord(
            message_id=message_id,
            sequence_id=sequence_id,
            created_ms=now_ms(),
        )
        self.assistant_turns.append(record)
        self._assistant_by_message_id[message_id] = record
        self._trim()
        return record

    def append_assistant_text(self, message_id: str, text: str) -> None:
        record = self._assistant_by_message_id.get(message_id)
        if record is None or not text.strip():
            return
        record.full_text = _append_text(record.full_text, text)

    def update_assistant_from_playback(self, playback: MessagePlayback) -> AssistantTurnRecord:
        record = self.start_assistant_turn(
            message_id=playback.message_id,
            sequence_id=playback.sequence_id,
        )
        record.full_text = playback.full_text or playback.text_sent_to_tts or record.full_text
        record.heard_text = estimate_heard_text(playback)
        record.interrupted = playback.interrupted
        record.fully_played_ms = playback.fully_played_ms
        return record

    def build_llm_messages(self, current_user_turn: UserTurnFinal | None = None) -> list[dict[str, str]]:
        messages: list[dict[str, str]] = [{"role": "system", "content": self.system_prompt}]
        if self.summary_text:
            messages.append({"role": "system", "content": f"Earlier call context:\n{self.summary_text}"})
        slot_text = self.slots.to_prompt_text()
        if slot_text:
            messages.append({"role": "system", "content": f"Known call details:\n{slot_text}"})
        records = self._recent_records(current_user_turn)
        for role, content in records:
            if content:
                messages.append({"role": role, "content": content})
        return messages

    def _recent_records(self, current_user_turn: UserTurnFinal | None) -> list[tuple[str, str]]:
        records: list[tuple[int, int, str, str]] = []
        for index, user in enumerate(self.user_turns):
            records.append((user.timestamp_ms, index, "user", user.text))
        for index, assistant in enumerate(self.assistant_turns):
            content = assistant_context_text(assistant)
            records.append((assistant.created_ms, index, "assistant", content))
        if current_user_turn is not None and not self._has_user_turn(current_user_turn.turn_id):
            records.append(
                (
                    current_user_turn.end_ms or now_ms(),
                    len(records),
                    "user",
                    current_user_turn.text,
                )
            )
        records.sort(key=lambda item: (item[0], item[1]))
        return [(role, content) for _, _, role, content in records[-self.max_recent_turns :]]

    def _has_user_turn(self, turn_id: int) -> bool:
        return any(turn.turn_id == turn_id for turn in self.user_turns)

    def _trim(self) -> None:
        removed_summary_turns: list[tuple[int, int, SummaryTurn]] = []
        if len(self.user_turns) > self.max_recent_turns:
            removed = self.user_turns[: -self.max_recent_turns]
            self.user_turns = self.user_turns[-self.max_recent_turns :]
            for index, record in enumerate(removed):
                removed_summary_turns.append(
                    (
                        record.timestamp_ms,
                        index,
                        SummaryTurn(role="user", content=record.text),
                    )
                )
        if len(self.assistant_turns) > self.max_recent_turns:
            removed = self.assistant_turns[: -self.max_recent_turns]
            self.assistant_turns = self.assistant_turns[-self.max_recent_turns :]
            for index, record in enumerate(removed):
                self._assistant_by_message_id.pop(record.message_id, None)
                removed_summary_turns.append(
                    (
                        record.created_ms,
                        len(removed_summary_turns) + index,
                        SummaryTurn(role="assistant", content=assistant_context_text(record)),
                    )
                )
        if removed_summary_turns:
            removed_summary_turns.sort(key=lambda item: (item[0], item[1]))
            self.summary_text = self.summarizer.update(
                self.summary_text,
                (turn for _, _, turn in removed_summary_turns),
            )


def assistant_context_text(record: AssistantTurnRecord) -> str:
    text = (record.heard_text or "").strip()
    if record.interrupted:
        return f"{text} [interrupted]" if text else "[interrupted]"
    return text


def _append_text(existing: str, text: str) -> str:
    if not existing:
        return text.strip()
    return f"{existing.rstrip()} {text.strip()}".strip()
