"""FastAPI application factory."""

from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI

from voice_agent.api.routes import router
from voice_agent.api.ws import register_websocket_routes
from voice_agent.config import Settings, get_settings
from voice_agent.core.turn_detection.local_models import preload_turn_detection_models
from voice_agent.factory.provider_registry import ProviderRegistry, create_default_registry


def _lifespan(settings: Settings) -> Callable[[FastAPI], AsyncIterator[None]]:
    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.turn_detection_models = None
        if settings.vad_enabled or settings.smart_turn_enabled:
            app.state.turn_detection_models = await preload_turn_detection_models(settings)
        yield

    return lifespan


def create_app(
    settings: Settings | None = None,
    registry: ProviderRegistry | None = None,
) -> FastAPI:
    settings = settings or get_settings()
    app = FastAPI(
        title="Mercury Voice Agent",
        version="0.1.0",
        debug=settings.app_env == "development",
        lifespan=_lifespan(settings),
    )
    app.state.settings = settings
    app.state.provider_registry = registry or create_default_registry()
    app.include_router(router)
    register_websocket_routes(app, settings)
    return app
