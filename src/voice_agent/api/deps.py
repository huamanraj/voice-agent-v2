"""FastAPI dependencies."""

from fastapi import Request

from voice_agent.config import Settings, get_settings


def settings_dependency(request: Request) -> Settings:
    settings = getattr(getattr(request.app, "state", None), "settings", None)
    if isinstance(settings, Settings):
        return settings
    return get_settings()
