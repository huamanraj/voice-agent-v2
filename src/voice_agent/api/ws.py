"""WebSocket routes will be wired once telephony adapters exist."""

from fastapi import APIRouter, WebSocket, status

router = APIRouter()


@router.websocket("/ws/{call_id}")
async def call_websocket(websocket: WebSocket, call_id: str) -> None:
    await websocket.accept()
    await websocket.close(
        code=status.WS_1013_TRY_AGAIN_LATER,
        reason=f"Call {call_id} is not enabled before provider adapters are built.",
    )
