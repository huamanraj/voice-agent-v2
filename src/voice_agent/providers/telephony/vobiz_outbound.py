"""Vobiz outbound call API client."""

import asyncio
import json
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from voice_agent.config import Settings


@dataclass(frozen=True, slots=True)
class VobizOutboundCall:
    to_number: str
    from_number: str
    answer_url: str
    answer_method: str = "POST"
    machine_detection: str | bool | None = None

    def to_payload(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "from": self.from_number,
            "to": self.to_number,
            "answer_url": self.answer_url,
            "answer_method": self.answer_method,
        }
        if self.machine_detection is not None:
            payload["machine_detection"] = self.machine_detection
        return payload


class VobizOutboundClient:
    def __init__(
        self,
        settings: Settings,
        *,
        opener: Callable[[Request, float], Any] | None = None,
        timeout_seconds: float = 10.0,
    ) -> None:
        self.settings = settings
        self.opener = opener or _default_opener
        self.timeout_seconds = timeout_seconds

    async def make_call(
        self,
        to_number: str,
        *,
        from_number: str | None = None,
        answer_url: str | None = None,
        answer_method: str | None = None,
        machine_detection: str | bool | None = None,
    ) -> dict[str, Any]:
        self._validate_credentials()
        call = VobizOutboundCall(
            to_number=to_number,
            from_number=from_number or self._required(self.settings.vobiz_from_number, "VOBIZ_FROM_NUMBER"),
            answer_url=answer_url or self._required(self.settings.vobiz_answer_url, "VOBIZ_ANSWER_URL"),
            answer_method=answer_method or self.settings.vobiz_answer_method,
            machine_detection=machine_detection,
        )
        request = self._build_request(call)
        return await asyncio.to_thread(self._send_request, request)

    def _build_request(self, call: VobizOutboundCall) -> Request:
        assert self.settings.vobiz_auth_id is not None
        assert self.settings.vobiz_auth_token is not None
        body = json.dumps(call.to_payload()).encode("utf-8")
        return Request(
            url=self._call_url(),
            data=body,
            method="POST",
            headers={
                "Content-Type": "application/json",
                "X-Auth-ID": self.settings.vobiz_auth_id,
                "X-Auth-Token": self.settings.vobiz_auth_token,
            },
        )

    def _send_request(self, request: Request) -> dict[str, Any]:
        try:
            with self.opener(request, self.timeout_seconds) as response:
                data = response.read()
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace") if exc.fp else ""
            raise RuntimeError(f"Vobiz outbound call failed with HTTP {exc.code}: {detail}") from exc
        except URLError as exc:
            raise RuntimeError(f"Vobiz outbound call failed: {exc.reason}") from exc

        if not data:
            return {}
        return json.loads(data.decode("utf-8"))

    def _call_url(self) -> str:
        assert self.settings.vobiz_auth_id is not None
        base_url = self.settings.vobiz_api_base_url.rstrip("/")
        return f"{base_url}/api/v1/Account/{self.settings.vobiz_auth_id}/Call/"

    def _validate_credentials(self) -> None:
        self._required(self.settings.vobiz_auth_id, "VOBIZ_AUTH_ID")
        self._required(self.settings.vobiz_auth_token, "VOBIZ_AUTH_TOKEN")

    @staticmethod
    def _required(value: str | None, name: str) -> str:
        if not value:
            raise ValueError(f"{name} is required for Vobiz outbound calls.")
        return value


def _default_opener(request: Request, timeout: float) -> Any:
    return urlopen(request, timeout=timeout)
