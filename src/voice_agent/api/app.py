"""FastAPI application factory."""

from fastapi import FastAPI

from voice_agent.api.routes import router
from voice_agent.api.ws import register_websocket_routes
from voice_agent.config import Settings, get_settings
from voice_agent.factory.provider_registry import ProviderRegistry, create_default_registry


def create_app(
    settings: Settings | None = None,
    registry: ProviderRegistry | None = None,
) -> FastAPI:
    settings = settings or get_settings()
    app = FastAPI(
        title="Mercury Voice Agent",
        version="0.1.0",
        debug=settings.app_env == "development",
    )
    app.state.settings = settings
    app.state.provider_registry = registry or create_default_registry()
    app.include_router(router)
    register_websocket_routes(app, settings)
    return app
