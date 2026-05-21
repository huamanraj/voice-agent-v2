"""Small health helpers shared by realtime provider adapters."""

from collections.abc import Awaitable
from typing import Any


async def websocket_ping(websocket: Any, *, timeout_seconds: float) -> bool:
    ping = getattr(websocket, "ping", None)
    if ping is None:
        return websocket_is_open(websocket)

    try:
        import asyncio

        pong_waiter = ping()
        if isinstance(pong_waiter, Awaitable):
            pong_waiter = await pong_waiter
        if isinstance(pong_waiter, Awaitable):
            await asyncio.wait_for(pong_waiter, timeout=timeout_seconds)
        return websocket_is_open(websocket)
    except Exception:
        return False


def websocket_is_open(websocket: Any) -> bool:
    if websocket is None:
        return False
    if bool(getattr(websocket, "closed", False)):
        return False
    close_code = getattr(websocket, "close_code", None)
    if close_code is not None:
        return False
    state = getattr(websocket, "state", None)
    if state is not None and str(state).upper().endswith("CLOSED"):
        return False
    return True
