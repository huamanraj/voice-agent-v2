"""Two-stage interruption manager."""

from dataclasses import dataclass, field
from enum import StrEnum

from voice_agent.config import Settings
from voice_agent.contracts.events import (
    InterruptionRejected,
    InterruptionStarted,
    SpeechStart,
    TranscriptEvent,
)
from voice_agent.contracts.ports import LLMPort, TTSPort, TelephonyPort
from voice_agent.core.interruption.output_gate import OutputGate
from voice_agent.core.interruption.phrase_classifier import PhraseClassifier, PhraseDecision
from voice_agent.core.interruption.sequence_manager import SequenceManager


class InterruptionOutcome(StrEnum):
    IGNORED = "ignored"
    CANDIDATE = "candidate"
    CONFIRMED = "confirmed"
    REJECTED = "rejected"
    PENDING = "pending"


@dataclass(frozen=True, slots=True)
class InterruptionDecision:
    outcome: InterruptionOutcome
    reason: str
    phrase: PhraseDecision | None = None
    event: InterruptionStarted | InterruptionRejected | None = None


@dataclass(slots=True)
class ActiveResponse:
    sequence_id: int
    response_id: str
    message_id: str


@dataclass(slots=True)
class InterruptionState:
    agent_is_speaking: bool = False
    user_interrupt_start_ms: int | None = None
    candidate_sequence_id: int | None = None
    user_may_be_interrupting: bool = False
    confirmed_count: int = 0
    rejected_count: int = 0
    events: list[InterruptionStarted | InterruptionRejected] = field(default_factory=list)


class InterruptionManager:
    def __init__(
        self,
        call_id: str,
        settings: Settings,
        output_gate: OutputGate,
        sequence_manager: SequenceManager,
        telephony: TelephonyPort,
        tts: TTSPort,
        llm: LLMPort,
        phrase_classifier: PhraseClassifier | None = None,
    ) -> None:
        self.call_id = call_id
        self.settings = settings
        self.output_gate = output_gate
        self.sequence_manager = sequence_manager
        self.telephony = telephony
        self.tts = tts
        self.llm = llm
        self.phrase_classifier = phrase_classifier or PhraseClassifier(
            settings.force_interrupt_phrases,
            settings.backchannel_phrases,
        )
        self.state = InterruptionState()
        self.active_response: ActiveResponse | None = None

    def track_response(self, sequence_id: int, response_id: str, message_id: str) -> None:
        self.active_response = ActiveResponse(
            sequence_id=sequence_id,
            response_id=response_id,
            message_id=message_id,
        )

    def mark_agent_audio_sent(self, sequence_id: int | None) -> None:
        if self.active_response is None or sequence_id == self.active_response.sequence_id:
            self.state.agent_is_speaking = True

    def mark_agent_response_finished(self, sequence_id: int | None = None) -> None:
        if sequence_id is None or self.active_response is None or sequence_id == self.active_response.sequence_id:
            self.state.agent_is_speaking = False
            self.active_response = None
            self._reset_candidate()

    async def handle_speech_start(self, event: SpeechStart) -> InterruptionDecision:
        if not self.settings.interruption_enabled:
            return InterruptionDecision(InterruptionOutcome.IGNORED, "interruption_disabled")
        if not self._can_consider_interruption():
            return InterruptionDecision(InterruptionOutcome.IGNORED, "agent_not_speaking")

        self.state.user_interrupt_start_ms = event.ts_ms
        self.state.candidate_sequence_id = self.active_response.sequence_id if self.active_response else None
        self.state.user_may_be_interrupting = True
        if self.settings.wait_gate_on_speech_start:
            await self.output_gate.set_wait()
        if self.settings.preemptive_clear_audio:
            await self.telephony.clear_playback("preemptive_interruption_candidate")
        return InterruptionDecision(InterruptionOutcome.CANDIDATE, "speech_start")

    async def handle_transcript(self, event: TranscriptEvent) -> InterruptionDecision:
        if not self.settings.interruption_enabled:
            return InterruptionDecision(InterruptionOutcome.IGNORED, "interruption_disabled")
        if not self._can_consider_interruption():
            return InterruptionDecision(InterruptionOutcome.IGNORED, "agent_not_speaking")
        if self.state.user_interrupt_start_ms is None:
            await self.handle_speech_start(
                SpeechStart(
                    call_id=event.call_id,
                    ts_ms=event.start_ms or event.end_ms or 0,
                    source="stt",
                    confidence=event.confidence,
                )
            )

        phrase = self.phrase_classifier.decide(event.text)
        audio_ms = self._interruption_audio_ms(event)
        if phrase.is_backchannel:
            return await self.reject("backchannel_phrase", phrase, event)
        if phrase.is_force_interrupt:
            return await self.confirm("force_interrupt_phrase", phrase, event)
        if phrase.word_count >= self.settings.min_interrupt_words:
            return await self.confirm("word_count_threshold", phrase, event)
        if audio_ms >= self.settings.hard_interrupt_after_audio_ms and phrase.word_count > 0:
            return await self.confirm("long_user_speech", phrase, event)
        return InterruptionDecision(InterruptionOutcome.PENDING, "not_enough_words", phrase)

    async def reject(
        self,
        reason: str,
        phrase: PhraseDecision,
        event: TranscriptEvent,
    ) -> InterruptionDecision:
        await self.output_gate.set_send()
        self.state.rejected_count += 1
        rejected = InterruptionRejected(
            call_id=self.call_id,
            turn_id=None,
            sequence_id=self.active_response.sequence_id if self.active_response else 0,
            reason=reason,
            transcript=event.text,
            ts_ms=event.end_ms or event.start_ms or 0,
        )
        self.state.events.append(rejected)
        self._reset_candidate()
        return InterruptionDecision(InterruptionOutcome.REJECTED, reason, phrase, rejected)

    async def confirm(
        self,
        reason: str,
        phrase: PhraseDecision,
        event: TranscriptEvent,
    ) -> InterruptionDecision:
        active_response = self.active_response
        sequence_id = active_response.sequence_id if active_response else 0
        await self.output_gate.set_block()
        invalidated = self.sequence_manager.invalidate_pending(reason)
        await self.output_gate.block_sequences(invalidated)

        if active_response is not None:
            await self.tts.cancel(active_response.message_id, reason)
            await self.llm.cancel(active_response.response_id)
        if self.settings.clear_audio_on_confirmed_interrupt:
            await self.telephony.clear_playback(reason)

        self.state.confirmed_count += 1
        self.state.agent_is_speaking = False
        started = InterruptionStarted(
            call_id=self.call_id,
            turn_id=None,
            sequence_id=sequence_id,
            reason=reason,
            transcript=event.text,
            ts_ms=event.end_ms or event.start_ms or 0,
        )
        self.state.events.append(started)
        self.active_response = None
        self._reset_candidate()
        return InterruptionDecision(InterruptionOutcome.CONFIRMED, reason, phrase, started)

    def _can_consider_interruption(self) -> bool:
        return self.active_response is not None and self.state.agent_is_speaking

    def _interruption_audio_ms(self, event: TranscriptEvent) -> int:
        if self.state.user_interrupt_start_ms is None:
            return 0
        event_end_ms = event.end_ms or event.start_ms or self.state.user_interrupt_start_ms
        return max(0, event_end_ms - self.state.user_interrupt_start_ms)

    def _reset_candidate(self) -> None:
        self.state.user_interrupt_start_ms = None
        self.state.candidate_sequence_id = None
        self.state.user_may_be_interrupting = False
