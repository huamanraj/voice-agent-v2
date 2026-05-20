from voice_agent.core.interruption.sequence_manager import SYSTEM_SEQUENCE_ID, SequenceManager


def test_sequence_manager_creates_monotonic_valid_sequences() -> None:
    manager = SequenceManager()

    first = manager.create_sequence()
    second = manager.create_sequence()

    assert first == 1
    assert second == 2
    assert manager.is_valid(first)
    assert manager.is_valid(second)
    assert manager.is_valid(SYSTEM_SEQUENCE_ID)


def test_sequence_manager_invalidates_pending_sequences_but_keeps_system_sequence() -> None:
    manager = SequenceManager()
    first = manager.create_sequence()
    second = manager.create_sequence()

    invalidated = manager.invalidate_pending("interruption")

    assert invalidated == {first, second}
    assert not manager.is_valid(first)
    assert not manager.is_valid(second)
    assert manager.is_valid(SYSTEM_SEQUENCE_ID)
    assert manager.invalidated_sequences() == {first, second}


def test_sequence_manager_retires_completed_sequence() -> None:
    manager = SequenceManager()
    sequence_id = manager.create_sequence()

    assert manager.retire(sequence_id)
    assert not manager.is_valid(sequence_id)
    assert manager.is_valid(SYSTEM_SEQUENCE_ID)
    assert manager.invalidate_pending("interruption") == set()
