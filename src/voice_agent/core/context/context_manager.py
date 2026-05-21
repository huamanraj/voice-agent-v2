"""Conversation context records used to build LLM history."""

from dataclasses import dataclass

from voice_agent.contracts.events import UserTurnFinal
from voice_agent.contracts.packets import now_ms
from voice_agent.core.context.prompt_builder import (
    ConversationLine,
    DynamicPromptInput,
    LatestContext,
    build_dynamic_system_prompt,
)
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
        max_recent_turns: int = 60,
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

    def replace_user_turn(self, turn: UserTurnFinal) -> None:
        for record in reversed(self.user_turns):
            if record.turn_id == turn.turn_id:
                record.text = turn.text
                record.timestamp_ms = turn.end_ms or now_ms()
                record.confidence = turn.confidence
                record.language = turn.language
                return
        self.append_user_turn(turn)

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
        return [{"role": "system", "content": self.build_system_prompt(current_user_turn)}]

    def build_system_prompt(self, current_user_turn: UserTurnFinal | None = None) -> str:
        return build_dynamic_system_prompt(
            DynamicPromptInput(
                system_instructions=self.system_prompt,
                conversation=self._conversation_lines(current_user_turn),
                latest=self._latest_context(current_user_turn),
                older_summary=self.summary_text,
                known_details=self.slots.to_prompt_text(),
            )
        )

    def _conversation_lines(self, current_user_turn: UserTurnFinal | None) -> list[ConversationLine]:
        records: list[tuple[int, int, ConversationLine]] = []
        for index, user in enumerate(self.user_turns):
            records.append((user.timestamp_ms, index, ConversationLine("user", user.text)))
        for index, assistant in enumerate(self.assistant_turns):
            content = assistant_context_text(assistant)
            records.append(
                (
                    assistant.created_ms,
                    index,
                    ConversationLine("assistant", content, interrupted=assistant.interrupted),
                )
            )
        if current_user_turn is not None and not self._has_user_turn(current_user_turn.turn_id):
            records.append(
                (
                    current_user_turn.end_ms or now_ms(),
                    len(records),
                    ConversationLine("user", current_user_turn.text),
                )
            )
        records.sort(key=lambda item: (item[0], item[1]))
        return [line for _, _, line in records[-self.max_recent_turns :] if line.content.strip()]

    def _latest_context(self, current_user_turn: UserTurnFinal | None) -> LatestContext:
        latest_user = current_user_turn.text if current_user_turn is not None else None
        if latest_user is None and self.user_turns:
            latest_user = self.user_turns[-1].text

        latest_agent = self._latest_assistant_with_heard_text()
        latest_agent_text = assistant_context_text(latest_agent) if latest_agent is not None else None
        interrupted_text = latest_agent_text if latest_agent is not None and latest_agent.interrupted else None

        return LatestContext(
            last_agent_message=latest_agent_text,
            last_user_message=latest_user,
            interrupted_agent_message=interrupted_text,
            interruption_user_message=latest_user if interrupted_text else None,
        )

    def _latest_assistant_with_heard_text(self) -> AssistantTurnRecord | None:
        for assistant in reversed(self.assistant_turns):
            if assistant_context_text(assistant):
                return assistant
        return None

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
