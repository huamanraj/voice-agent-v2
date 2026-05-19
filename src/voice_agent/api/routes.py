"""HTTP routes for health and readiness checks."""

from fastapi import APIRouter, Depends

from voice_agent.api.deps import settings_dependency
from voice_agent.config import Settings

router = APIRouter()


@router.get("/healthz")
async def healthz(settings: Settings = Depends(settings_dependency)) -> dict[str, str]:
    return {"status": "ok", "env": settings.app_env}


@router.get("/readyz")
async def readyz() -> dict[str, str]:
    return {"status": "ready"}
