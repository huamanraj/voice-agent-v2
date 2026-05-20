"""WebSocket routes for live telephony media streams."""

import logging
from contextlib import suppress
from typing import Any

from fastapi import APIRouter, FastAPI, WebSocket, status

from voice_agent.config import Settings, get_settings
from voice_agent.core.session_orchestrator import SessionStats
from voice_agent.core.turn_detection.local_models import TurnDetectionModels
from voice_agent.factory.provider_registry import ProviderRegistry, create_default_registry
from voice_agent.factory.session_factory import create_session_orchestrator_with_telephony
from voice_agent.providers.telephony.vobiz import VobizTelephony

router = APIRouter()
logger = logging.getLogger(__name__)
_INVALID_STREAM_TOKEN = object()
_USE_SETTINGS_STREAM_TOKEN = object()


async def vobiz_websocket(websocket: WebSocket) -> None:
    await websocket.accept()
    logger.info("vobiz_websocket_accepted path=%s", websocket.url.path)
    settings = _settings_from_app(websocket)
    registry = _registry_from_app(websocket)
    turn_detection_models = _turn_detection_models_from_app(websocket)
    stream_auth_token = _stream_auth_token_for_session(websocket, settings)
    if stream_auth_token is _INVALID_STREAM_TOKEN:
        logger.warning("vobiz_websocket_rejected reason=invalid_stream_token")
        await _close_websocket(
            websocket,
            code=status.WS_1008_POLICY_VIOLATION,
            reason="Invalid Vobiz stream token.",
        )
        return
    try:
        await run_vobiz_websocket_session(
            websocket,
            settings=settings,
            registry=registry,
            turn_detection_models=turn_detection_models,
            stream_auth_token=stream_auth_token,
        )
    except TimeoutError:
        logger.warning("vobiz_websocket_closed reason=start_timeout")
        await _close_websocket(
            websocket,
            code=status.WS_1008_POLICY_VIOLATION,
            reason="Vobiz start event was not received in time.",
        )
    except Exception:
        logger.exception("vobiz_websocket_closed reason=session_failed")
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
    turn_detection_models: TurnDetectionModels | None = None,
    stream_auth_token: str | None | object = _USE_SETTINGS_STREAM_TOKEN,
) -> SessionStats:
    runtime_settings = settings or get_settings()
    provider_registry = registry or create_default_registry()
    auth_token = (
        runtime_settings.vobiz_stream_auth_token
        if stream_auth_token is _USE_SETTINGS_STREAM_TOKEN
        else stream_auth_token
    )
    telephony = provider_registry.create(
        "telephony",
        "vobiz",
        websocket=websocket,
        auth_token=auth_token,
    )
    if not isinstance(telephony, VobizTelephony):
        raise TypeError("The 'vobiz' telephony provider must create VobizTelephony.")

    await telephony.start()
    start_seen = await telephony.wait_started(runtime_settings.vobiz_start_timeout_ms / 1000)
    if not start_seen:
        logger.warning("vobiz_start_timeout provider_errors=%s", [error.error_type for error in telephony.errors])
        await telephony.stop("vobiz_start_timeout")
        raise TimeoutError("Vobiz start event was not received in time.")

    orchestrator = create_session_orchestrator_with_telephony(
        call_id=telephony.call_id,
        settings=runtime_settings,
        telephony=telephony,
        registry=provider_registry,
        turn_detection_models=turn_detection_models,
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


def _turn_detection_models_from_app(websocket: WebSocket) -> TurnDetectionModels | None:
    app = websocket.scope.get("app")
    models = getattr(getattr(app, "state", None), "turn_detection_models", None)
    return models if isinstance(models, TurnDetectionModels) else None


def _stream_auth_token_for_session(websocket: WebSocket, settings: Settings) -> str | None | object:
    expected = settings.vobiz_stream_auth_token
    if not expected:
        return None
    supplied = websocket.query_params.get("token")
    if supplied is None:
        return expected
    if supplied != expected:
        return _INVALID_STREAM_TOKEN
    return None


async def _close_websocket(websocket: WebSocket, *, code: int, reason: str) -> None:
    with suppress(Exception):
        await websocket.close(code=code, reason=reason)
