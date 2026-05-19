"""FastAPI application factory."""

from fastapi import FastAPI

from voice_agent.api.routes import router
from voice_agent.config import get_settings


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="Mercury Voice Agent",
        version="0.1.0",
        debug=settings.app_env == "development",
    )
    app.include_router(router)
    return app
