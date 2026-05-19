"""Post-call webhook task."""

from typing import Any

import httpx


class WebhookTask:
    def __init__(self, url: str, *, timeout_seconds: float = 5.0) -> None:
        self.url = url
        self.timeout_seconds = timeout_seconds

    async def run(self, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                response = await client.post(self.url, json=payload)
            return {
                "ok": 200 <= response.status_code < 300,
                "status_code": response.status_code,
                "body": response.text[:1000],
            }
        except Exception as exc:
            return {
                "ok": False,
                "error_type": exc.__class__.__name__,
                "message": str(exc),
            }
