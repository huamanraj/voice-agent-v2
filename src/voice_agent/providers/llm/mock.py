"""In-memory LLM adapter for offline simulations."""

from collections.abc import AsyncIterator
from typing import Any

from voice_agent.contracts.capabilities import LLMCapabilities


class MockLLM:
    provider_name = "mock"
    capabilities = LLMCapabilities(
        supports_streaming=True,
        supports_json_mode=True,
        supports_tool_calling=False,
    )

    def __init__(self, responses: list[str] | None = None) -> None:
        self.responses = responses or ["Hello, this is a mock response."]
        self.requests: list[dict[str, Any]] = []
        self.cancelled_response_ids: set[str] = set()
        self._response_index = 0

    async def stream_response(
        self,
        call_id: str,
        messages: list[dict[str, Any]],
        response_id: str,
    ) -> AsyncIterator[str]:
        self.requests.append(
            {"call_id": call_id, "messages": messages, "response_id": response_id}
        )
        response = self.responses[self._response_index % len(self.responses)]
        self._response_index += 1

        for token in response.split(" "):
            if response_id in self.cancelled_response_ids:
                break
            yield token + " "

    async def classify(
        self,
        call_id: str,
        prompt: str,
        schema: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        self.requests.append({"call_id": call_id, "prompt": prompt, "schema": schema})
        return {"label": "mock", "confidence": 1.0}

    async def cancel(self, response_id: str) -> None:
        self.cancelled_response_ids.add(response_id)

    async def stop(self) -> None:
        return None
