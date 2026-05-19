"""CLI entrypoint for local development."""

from voice_agent.config import get_settings


def main() -> None:
    settings = get_settings()

    import uvicorn

    uvicorn.run(
        "voice_agent.api.app:create_app",
        factory=True,
        host=settings.api_host,
        port=settings.api_port,
        log_level=settings.log_level.lower(),
    )
