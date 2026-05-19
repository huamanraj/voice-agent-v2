"""FastAPI dependencies."""

from voice_agent.config import Settings, get_settings


def settings_dependency() -> Settings:
    return get_settings()
