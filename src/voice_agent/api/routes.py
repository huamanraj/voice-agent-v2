"""HTTP routes for health, readiness, and Vobiz call control."""

from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel

from voice_agent.api.deps import settings_dependency
from voice_agent.api.vobiz_urls import vobiz_answer_xml, with_query_params
from voice_agent.config import Settings
from voice_agent.core.provider_warmup import ProviderWarmupPool
from voice_agent.providers.telephony import VobizOutboundClient

router = APIRouter()


class VobizCallRequest(BaseModel):
    to_number: str
    from_number: str | None = None
    answer_url: str | None = None
    answer_method: str | None = None
    agent_id: str | None = None
    machine_detection: str | bool | None = None


@router.get("/healthz")
async def healthz(settings: Settings = Depends(settings_dependency)) -> dict[str, str]:
    return {"status": "ok", "env": settings.app_env}


@router.get("/readyz")
async def readyz(
    request: Request,
    settings: Settings = Depends(settings_dependency),
) -> JSONResponse:
    models = getattr(getattr(request.app, "state", None), "turn_detection_models", None)
    if settings.vad_enabled or settings.smart_turn_enabled:
        vad_ready = bool(getattr(models, "vad", None))
        smart_turn_ready = bool(getattr(models, "smart_turn", None))
        ready = (not settings.vad_enabled or vad_ready) and (
            not settings.smart_turn_enabled or smart_turn_ready
        )
        return JSONResponse(
            status_code=status.HTTP_200_OK if ready else status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "status": "ready" if ready else "not_ready",
                "vad": "ready" if vad_ready else "not_ready",
                "smart_turn": "ready" if smart_turn_ready else "not_ready",
            },
        )
    return JSONResponse(content={"status": "ready", "vad": "disabled", "smart_turn": "disabled"})


@router.get("/vobiz/answer")
@router.post("/vobiz/answer")
async def vobiz_answer(
    agent_id: str | None = None,
    prewarm_id: str | None = None,
    settings: Settings = Depends(settings_dependency),
) -> Response:
    """VoiceXML webhook: tells Vobiz which WebSocket receives call audio."""
    return Response(
        content=vobiz_answer_xml(settings, agent_id=agent_id, prewarm_id=prewarm_id),
        media_type="application/xml",
    )


@router.post("/vobiz/call")
async def vobiz_call(
    payload: VobizCallRequest,
    request: Request,
    settings: Settings = Depends(settings_dependency),
) -> dict[str, Any]:
    """Prewarm speech providers in this process, then place a Vobiz outbound call."""
    pool = _provider_warmup_pool_from_request(request)
    prewarm_id = str(uuid4()) if settings.outbound_provider_prewarm_enabled and pool else None
    answer_url = payload.answer_url or settings.vobiz_answer_url
    if not answer_url:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="VOBIZ_ANSWER_URL or answer_url is required.",
        )

    if prewarm_id is not None:
        await pool.prewarm(prewarm_id, agent_id=payload.agent_id)

    call_answer_url = with_query_params(
        answer_url,
        {
            "agent_id": payload.agent_id,
            "prewarm_id": prewarm_id,
        },
    )
    client = _vobiz_outbound_client_from_request(request, settings)
    try:
        result = await client.make_call(
            payload.to_number,
            from_number=payload.from_number,
            answer_url=call_answer_url,
            answer_method=payload.answer_method,
            machine_detection=payload.machine_detection,
        )
    except Exception:
        if prewarm_id is not None:
            await pool.discard(prewarm_id, reason="make_call_failed")
        raise

    if prewarm_id is not None:
        for key in ("request_uuid", "RequestUUID", "call_uuid", "CallUUID"):
            await pool.add_alias(str(result.get(key)) if result.get(key) else None, prewarm_id)
        result["prewarm_id"] = prewarm_id
    return result


def _provider_warmup_pool_from_request(request: Request) -> ProviderWarmupPool | None:
    pool = getattr(getattr(request.app, "state", None), "provider_warmup_pool", None)
    return pool if isinstance(pool, ProviderWarmupPool) else None


def _vobiz_outbound_client_from_request(request: Request, settings: Settings) -> VobizOutboundClient:
    factory = getattr(getattr(request.app, "state", None), "vobiz_outbound_client_factory", None)
    if callable(factory):
        client = factory(settings)
        if isinstance(client, VobizOutboundClient):
            return client
        return client
    return VobizOutboundClient(settings)
