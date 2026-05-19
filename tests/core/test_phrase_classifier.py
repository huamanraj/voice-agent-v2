from voice_agent.config import get_settings
from voice_agent.core.interruption.phrase_classifier import PhraseClassifier


def classifier() -> PhraseClassifier:
    settings = get_settings()
    return PhraseClassifier(settings.force_interrupt_phrases, settings.backchannel_phrases)


def test_phrase_classifier_detects_force_interrupt_prefix() -> None:
    decision = classifier().decide("ruk jao please")

    assert decision.is_force_interrupt
    assert not decision.is_backchannel
    assert decision.matched_phrase == "ruk jao"


def test_phrase_classifier_detects_backchannel_only_when_not_force_interrupt() -> None:
    decision = classifier().decide("haan")

    assert decision.is_backchannel
    assert not decision.is_force_interrupt
    assert decision.word_count == 1


def test_phrase_classifier_counts_regular_speech_words() -> None:
    decision = classifier().decide("I have one more question")

    assert not decision.is_backchannel
    assert not decision.is_force_interrupt
    assert decision.word_count == 5
