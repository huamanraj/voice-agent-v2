"""FastAPI application factory."""

import asyncio
import logging
import os
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI

from voice_agent.agents import apply_agent_profile, resolve_agent_profile
from voice_agent.api.routes import router
from voice_agent.api.ws import register_websocket_routes
from voice_agent.config import Settings, get_settings
from voice_agent.core.provider_warmup import ProviderWarmupPool
from voice_agent.core.turn_detection.local_models import preload_turn_detection_models
from voice_agent.factory.provider_registry import ProviderRegistry, create_default_registry

logger = logging.getLogger(__name__)


def _lifespan(settings: Settings) -> Callable[[FastAPI], AsyncIterator[None]]:
    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        _configure_runtime_environment(settings)
        runtime_settings = _default_runtime_settings(settings)
        await _preload_litellm_runtime(runtime_settings)
        registry = getattr(app.state, "provider_registry", None)
        if isinstance(registry, ProviderRegistry):
            app.state.provider_warmup_pool = ProviderWarmupPool(settings, registry)
        app.state.turn_detection_models = None
        if runtime_settings.vad_enabled or runtime_settings.smart_turn_enabled:
            app.state.turn_detection_models = await preload_turn_detection_models(runtime_settings)
        try:
            yield
        finally:
            pool = getattr(app.state, "provider_warmup_pool", None)
            if isinstance(pool, ProviderWarmupPool):
                await pool.close()

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


def _configure_runtime_environment(settings: Settings) -> None:
    if settings.hf_token:
        os.environ.setdefault("HF_TOKEN", settings.hf_token)
    if settings.hf_hub_offline:
        os.environ.setdefault("HF_HUB_OFFLINE", "1")
    if settings.litellm_local_model_cost_map:
        os.environ.setdefault("LITELLM_LOCAL_MODEL_COST_MAP", "True")


def _default_runtime_settings(settings: Settings) -> Settings:
    try:
        return apply_agent_profile(settings, resolve_agent_profile(settings))
    except Exception as exc:
        logger.warning(
            "default_agent_profile_preload_skipped error_code=%s message=%s",
            exc.__class__.__name__,
            str(exc),
        )
        return settings


async def _preload_litellm_runtime(settings: Settings) -> None:
    if settings.llm_provider != "litellm":
        return
    try:
        from voice_agent.providers.llm.litellm import preload_litellm_runtime

        await asyncio.to_thread(preload_litellm_runtime, settings)
    except Exception as exc:
        logger.warning(
            "litellm_runtime_preload_failed error_code=%s message=%s",
            exc.__class__.__name__,
            str(exc),
        )
