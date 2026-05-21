"""LiteLLM adapter for streaming chat completions."""

import asyncio
import json
import os
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import suppress
from dataclasses import dataclass
from typing import Any

from voice_agent.config import Settings, get_settings
from voice_agent.contracts.capabilities import LLMCapabilities
from voice_agent.contracts.events import ProviderError

CompletionFactory = Callable[..., Awaitable[Any]]
_WARMUP_MESSAGES = [{"role": "user", "content": "warmup"}]


@dataclass(slots=True)
class _ResponseState:
    cancel_event: asyncio.Event
    next_chunk_task: asyncio.Task[Any] | None = None


class LiteLLM:
    provider_name = "litellm"
    capabilities = LLMCapabilities(
        supports_streaming=True,
        supports_json_mode=True,
        supports_tool_calling=False,
    )

    def __init__(
        self,
        *,
        settings: Settings | None = None,
        completion_factory: CompletionFactory | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.completion_factory = completion_factory or _load_litellm_acompletion()
        self.cancelled_response_ids: set[str] = set()
        self.errors: list[ProviderError] = []
        self._responses: dict[str, _ResponseState] = {}
        self._stopped = False

    async def stream_response(
        self,
        call_id: str,
        messages: list[dict[str, Any]],
        response_id: str,
    ) -> AsyncIterator[str]:
        if self._stopped:
            return

        state = _ResponseState(cancel_event=asyncio.Event())
        self._responses[response_id] = state
        request = self._talker_request(messages)
        timeout_seconds = self.settings.llm_total_timeout_ms / 1000

        try:
            stream = await asyncio.wait_for(
                self.completion_factory(**request),
                timeout=timeout_seconds,
            )
            first_content_received = False
            deadline = asyncio.get_running_loop().time() + timeout_seconds

            while not self._stopped and response_id not in self.cancelled_response_ids:
                remaining = max(0.001, deadline - asyncio.get_running_loop().time())
                next_timeout = (
                    self.settings.llm_first_token_timeout_ms / 1000
                    if not first_content_received
                    else remaining
                )
                try:
                    chunk = await self._next_chunk_or_cancel(
                        stream,
                        state,
                        timeout_seconds=min(next_timeout, remaining),
                    )
                except StopAsyncIteration:
                    break

                content = _chunk_content(chunk)
                if not content:
                    continue
                first_content_received = True
                yield content
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            self._record_error(
                call_id,
                "stream_failed",
                str(exc),
                retryable=_is_retryable_litellm_error(exc),
                error_code=exc.__class__.__name__,
            )
            raise
        finally:
            self._responses.pop(response_id, None)
            await _close_stream_if_possible(locals().get("stream"))

    async def classify(
        self,
        call_id: str,
        prompt: str,
        schema: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        request = self._listener_request(prompt, schema)
        try:
            response = await asyncio.wait_for(
                self.completion_factory(**request),
                timeout=self.settings.llm_total_timeout_ms / 1000,
            )
        except Exception as exc:
            self._record_error(
                call_id,
                "classify_failed",
                str(exc),
                retryable=_is_retryable_litellm_error(exc),
                error_code=exc.__class__.__name__,
            )
            raise

        content = _message_content(response)
        if not content:
            return {}
        try:
            parsed = json.loads(content)
        except json.JSONDecodeError:
            return {"raw": content}
        return parsed if isinstance(parsed, dict) else {"value": parsed}

    async def cancel(self, response_id: str) -> None:
        self.cancelled_response_ids.add(response_id)
        state = self._responses.get(response_id)
        if state is None:
            return
        state.cancel_event.set()
        if state.next_chunk_task is not None and not state.next_chunk_task.done():
            state.next_chunk_task.cancel()

    async def stop(self) -> None:
        self._stopped = True
        for response_id in tuple(self._responses):
            await self.cancel(response_id)

    async def _next_chunk_or_cancel(
        self,
        stream: Any,
        state: _ResponseState,
        *,
        timeout_seconds: float,
    ) -> Any:
        state.next_chunk_task = asyncio.create_task(anext(stream))
        cancel_task = asyncio.create_task(state.cancel_event.wait())
        try:
            done, _pending = await asyncio.wait(
                {state.next_chunk_task, cancel_task},
                timeout=timeout_seconds,
                return_when=asyncio.FIRST_COMPLETED,
            )
            if not done:
                state.next_chunk_task.cancel()
                raise TimeoutError("LiteLLM did not return a token in time.")
            if cancel_task in done:
                state.next_chunk_task.cancel()
                raise StopAsyncIteration
            return await state.next_chunk_task
        finally:
            cancel_task.cancel()
            with suppress(asyncio.CancelledError):
                await cancel_task
            state.next_chunk_task = None

    def _talker_request(self, messages: list[dict[str, Any]]) -> dict[str, Any]:
        request = self._base_request(
            model=self.settings.talker_model,
            messages=_with_voice_system_prompt(messages),
            max_tokens=self.settings.talker_max_tokens,
            temperature=self.settings.talker_temperature,
        )
        request["stream"] = True
        request["stop"] = ["User:"]
        return request

    def _listener_request(self, prompt: str, schema: dict[str, Any] | None) -> dict[str, Any]:
        content = prompt
        if schema is not None:
            content = f"{prompt}\n\nReturn JSON matching this schema:\n{json.dumps(schema, ensure_ascii=False)}"
        request = self._base_request(
            model=self.settings.listener_model,
            messages=[
                {
                    "role": "system",
                    "content": "Return a single compact JSON object. Do not include markdown.",
                },
                {"role": "user", "content": content},
            ],
            max_tokens=self.settings.listener_max_tokens,
            temperature=self.settings.listener_temperature,
        )
        request["stream"] = False
        request["response_format"] = {"type": "json_object"}
        return request

    def _base_request(
        self,
        *,
        model: str,
        messages: list[dict[str, Any]],
        max_tokens: int,
        temperature: float,
    ) -> dict[str, Any]:
        request: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "timeout": self.settings.llm_total_timeout_ms / 1000,
            "drop_params": True,
        }
        if self.settings.litellm_api_key:
            request["api_key"] = self.settings.litellm_api_key
        if self.settings.litellm_api_base:
            request["api_base"] = self.settings.litellm_api_base
        if self.settings.litellm_api_version:
            request["api_version"] = self.settings.litellm_api_version
        return request

    def _record_error(
        self,
        call_id: str,
        error_type: str,
        message: str,
        *,
        retryable: bool,
        error_code: str | None = None,
    ) -> None:
        self.errors.append(
            ProviderError(
                call_id=call_id,
                provider=self.provider_name,
                error_type=error_type,
                error_code=error_code,
                message=message,
                retryable=retryable,
            )
        )


def _load_litellm_acompletion() -> CompletionFactory:
    litellm = _load_litellm_module()

    return litellm.acompletion


def preload_litellm_runtime(settings: Settings) -> None:
    litellm = _load_litellm_module(settings)
    for model in {settings.talker_model, settings.listener_model}:
        if not model or model.startswith("mock"):
            continue
        with suppress(Exception):
            litellm.token_counter(model=model, messages=_WARMUP_MESSAGES)


def _load_litellm_module(settings: Settings | None = None) -> Any:
    settings = settings or get_settings()
    if settings.litellm_local_model_cost_map:
        os.environ.setdefault("LITELLM_LOCAL_MODEL_COST_MAP", "True")

    import litellm

    if settings.litellm_disable_hf_tokenizer_download:
        litellm.disable_hf_tokenizer_download = True
    return litellm


def _with_voice_system_prompt(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if messages and messages[0].get("role") == "system":
        return messages
    return [
        {
            "role": "system",
            "content": (
                "You are a real-time phone voice agent. Reply briefly, naturally, "
                "and with one question at a time. Match the user's language style. "
                "Do not use markdown, bullets, code formatting, or long paragraphs."
            ),
        },
        *messages,
    ]


def _chunk_content(chunk: Any) -> str:
    choice = _first_choice(chunk)
    delta = _value(choice, "delta")
    content = _value(delta, "content")
    return content if isinstance(content, str) else ""


def _message_content(response: Any) -> str:
    choice = _first_choice(response)
    message = _value(choice, "message")
    content = _value(message, "content")
    return content if isinstance(content, str) else ""


def _first_choice(payload: Any) -> Any:
    choices = _value(payload, "choices")
    if isinstance(choices, list) and choices:
        return choices[0]
    return {}


def _value(payload: Any, key: str) -> Any:
    if isinstance(payload, dict):
        return payload.get(key)
    return getattr(payload, key, None)


async def _close_stream_if_possible(stream: Any) -> None:
    if stream is None:
        return
    close = getattr(stream, "aclose", None)
    if close is not None:
        with suppress(Exception):
            await close()


def _is_retryable_litellm_error(exc: Exception) -> bool:
    status_code = getattr(exc, "status_code", None)
    if isinstance(status_code, int):
        return status_code in {408, 429} or status_code >= 500
    name = exc.__class__.__name__.lower()
    return "timeout" in name or "ratelimit" in name or "connection" in name
