"""WebSocket routes for live telephony media streams."""

from contextlib import suppress
from typing import Any

from fastapi import APIRouter, FastAPI, WebSocket, status

from voice_agent.config import Settings, get_settings
from voice_agent.core.session_orchestrator import SessionStats
from voice_agent.factory.provider_registry import ProviderRegistry, create_default_registry
from voice_agent.factory.session_factory import create_session_orchestrator_with_telephony
from voice_agent.providers.telephony.vobiz import VobizTelephony

router = APIRouter()


async def vobiz_websocket(websocket: WebSocket) -> None:
    await websocket.accept()
    settings = _settings_from_app(websocket)
    registry = _registry_from_app(websocket)
    try:
        await run_vobiz_websocket_session(
            websocket,
            settings=settings,
            registry=registry,
        )
    except TimeoutError:
        await _close_websocket(
            websocket,
            code=status.WS_1008_POLICY_VIOLATION,
            reason="Vobiz start event was not received in time.",
        )
    except Exception:
        await _close_websocket(
            websocket,
            code=status.WS_1011_INTERNAL_ERROR,
            reason="Voice session failed.",
        )


@router.websocket("/ws/{call_id}")
async def call_websocket(websocket: WebSocket, call_id: str) -> None:
    await websocket.accept()
    await _close_websocket(
        websocket,
        code=status.WS_1008_POLICY_VIOLATION,
        reason=f"Call {call_id} must connect through the configured provider route.",
    )


def register_websocket_routes(app: FastAPI, settings: Settings) -> None:
    app.add_api_websocket_route(settings.vobiz_stream_ws_path, vobiz_websocket)
    app.include_router(router)


async def run_vobiz_websocket_session(
    websocket: Any,
    *,
    settings: Settings | None = None,
    registry: ProviderRegistry | None = None,
) -> SessionStats:
    runtime_settings = settings or get_settings()
    provider_registry = registry or create_default_registry()
    telephony = provider_registry.create(
        "telephony",
        "vobiz",
        websocket=websocket,
        auth_token=runtime_settings.vobiz_stream_auth_token,
    )
    if not isinstance(telephony, VobizTelephony):
        raise TypeError("The 'vobiz' telephony provider must create VobizTelephony.")

    await telephony.start()
    start_seen = await telephony.wait_started(runtime_settings.vobiz_start_timeout_ms / 1000)
    if not start_seen:
        await telephony.stop("vobiz_start_timeout")
        raise TimeoutError("Vobiz start event was not received in time.")

    orchestrator = create_session_orchestrator_with_telephony(
        call_id=telephony.call_id,
        settings=runtime_settings,
        telephony=telephony,
        registry=provider_registry,
    )
    return await orchestrator.run()


def _settings_from_app(websocket: WebSocket) -> Settings:
    app = websocket.scope.get("app")
    settings = getattr(getattr(app, "state", None), "settings", None)
    return settings if isinstance(settings, Settings) else get_settings()


def _registry_from_app(websocket: WebSocket) -> ProviderRegistry:
    app = websocket.scope.get("app")
    registry = getattr(getattr(app, "state", None), "provider_registry", None)
    return registry if isinstance(registry, ProviderRegistry) else create_default_registry()


async def _close_websocket(websocket: WebSocket, *, code: int, reason: str) -> None:
    with suppress(Exception):
        await websocket.close(code=code, reason=reason)
