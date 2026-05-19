import asyncio

from voice_agent.core.interruption.output_gate import OutputDecision, OutputGate, OutputGateState


def test_output_gate_sends_by_default_and_drops_blocked_sequences() -> None:
    gate = OutputGate()

    assert gate.decision_for(1) == OutputDecision.SEND

    async def scenario() -> None:
        await gate.block_sequence(1)

    asyncio.run(scenario())

    assert gate.decision_for(1) == OutputDecision.DROP
    assert gate.decision_for(2) == OutputDecision.SEND


def test_output_gate_wait_releases_when_send_is_restored() -> None:
    async def scenario() -> None:
        gate = OutputGate()
        await gate.set_wait()

        waiter = asyncio.create_task(gate.wait_until_released(timeout_seconds=1))
        await asyncio.sleep(0)
        await gate.set_send()

        assert await waiter == OutputDecision.SEND
        assert gate.state == OutputGateState.SEND

    asyncio.run(scenario())


def test_output_gate_wait_can_timeout() -> None:
    async def scenario() -> None:
        gate = OutputGate()
        await gate.set_wait()

        assert await gate.wait_until_released(timeout_seconds=0.001) == OutputDecision.WAIT

    asyncio.run(scenario())
