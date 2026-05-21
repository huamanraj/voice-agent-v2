import asyncio
import json
from contextlib import AbstractContextManager
from typing import Any
from urllib.request import Request

import pytest

from voice_agent.config import Settings
from voice_agent.providers.telephony import VobizOutboundClient


class FakeResponse(AbstractContextManager["FakeResponse"]):
    def __init__(self, payload: dict[str, Any] | None) -> None:
        self.payload = payload

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def read(self) -> bytes:
        if self.payload is None:
            return b""
        return json.dumps(self.payload).encode("utf-8")


def test_vobiz_outbound_client_builds_make_call_request_from_env_settings() -> None:
    async def scenario() -> None:
        captured: dict[str, Any] = {}

        def opener(request: Request, timeout: float) -> FakeResponse:
            captured["url"] = request.full_url
            captured["method"] = request.get_method()
            captured["headers"] = dict(request.header_items())
            captured["body"] = json.loads(request.data.decode("utf-8"))
            captured["timeout"] = timeout
            return FakeResponse({"message": "Call fired", "request_uuid": "req-1"})

        client = VobizOutboundClient(
            Settings(
                vobiz_api_base_url="https://api.vobiz.ai",
                vobiz_auth_id="auth-123",
                vobiz_auth_token="token-123",
                vobiz_from_number="14155551234",
                vobiz_answer_url="https://example.com/answer",
            ),
            opener=opener,
            timeout_seconds=3.0,
        )

        response = await client.make_call("+919876543210")

        assert response == {"message": "Call fired", "request_uuid": "req-1"}
        assert captured["url"] == "https://api.vobiz.ai/api/v1/Account/auth-123/Call/"
        assert captured["method"] == "POST"
        assert captured["headers"]["X-auth-id"] == "auth-123"
        assert captured["headers"]["X-auth-token"] == "token-123"
        assert captured["body"] == {
            "from": "14155551234",
            "to": "+919876543210",
            "answer_url": "https://example.com/answer",
            "answer_method": "POST",
        }
        assert captured["timeout"] == 3.0

    asyncio.run(scenario())


def test_vobiz_outbound_client_requires_credentials_and_numbers() -> None:
    async def scenario() -> None:
        client = VobizOutboundClient(
            Settings(vobiz_auth_id=None, vobiz_auth_token="token-123")
        )

        with pytest.raises(ValueError, match="VOBIZ_AUTH_ID"):
            await client.make_call("+919876543210")

        client = VobizOutboundClient(
            Settings(
                vobiz_auth_id="auth-123",
                vobiz_auth_token="token-123",
                vobiz_from_number="",
                vobiz_answer_url="",
            )
        )
        with pytest.raises(ValueError, match="VOBIZ_FROM_NUMBER"):
            await client.make_call("+919876543210")

    asyncio.run(scenario())


def test_vobiz_outbound_client_hangup_uses_delete_call_endpoint() -> None:
    async def scenario() -> None:
        captured: dict[str, Any] = {}

        def opener(request: Request, timeout: float) -> FakeResponse:
            captured["url"] = request.full_url
            captured["method"] = request.get_method()
            captured["headers"] = dict(request.header_items())
            captured["body"] = request.data
            captured["timeout"] = timeout
            return FakeResponse(None)

        client = VobizOutboundClient(
            Settings(
                vobiz_api_base_url="https://api.vobiz.ai",
                vobiz_auth_id="auth-123",
                vobiz_auth_token="token-123",
            ),
            opener=opener,
            timeout_seconds=2.0,
        )

        response = await client.hangup_call("call-uuid-123")

        assert response == {}
        assert captured["url"] == "https://api.vobiz.ai/api/v1/Account/auth-123/Call/call-uuid-123/"
        assert captured["method"] == "DELETE"
        assert captured["headers"]["X-auth-id"] == "auth-123"
        assert captured["headers"]["X-auth-token"] == "token-123"
        assert captured["body"] is None
        assert captured["timeout"] == 2.0

    asyncio.run(scenario())
