"""HTTP routes for health, readiness, and Vobiz call control."""

from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import JSONResponse, Response

from voice_agent.api.deps import settings_dependency
from voice_agent.api.vobiz_urls import vobiz_answer_xml
from voice_agent.config import Settings

router = APIRouter()


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
    settings: Settings = Depends(settings_dependency),
) -> Response:
    """VoiceXML webhook: tells Vobiz which WebSocket receives call audio."""
    return Response(content=vobiz_answer_xml(settings, agent_id=agent_id), media_type="application/xml")
