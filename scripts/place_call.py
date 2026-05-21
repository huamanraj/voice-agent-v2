#!/usr/bin/env python3
"""Place a Vobiz outbound call that connects to this project's media WebSocket."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from voice_agent.config import get_settings
from voice_agent.providers.telephony import VobizOutboundClient


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Place a Vobiz outbound test call.")
    parser.add_argument("to_number", help="Destination number in E.164 format, e.g. +919876543210")
    parser.add_argument(
        "--from-number",
        default=None,
        help="Caller ID (defaults to VOBIZ_FROM_NUMBER from .env)",
    )
    parser.add_argument(
        "--answer-url",
        default=None,
        help="Answer webhook (defaults to VOBIZ_ANSWER_URL from .env)",
    )
    parser.add_argument(
        "--agent-id",
        default=None,
        help="Agent profile id to pass through the server call endpoint.",
    )
    parser.add_argument(
        "--api-url",
        default=None,
        help="Mercury API base URL. Defaults to http://127.0.0.1:{API_PORT}.",
    )
    parser.add_argument(
        "--direct-vobiz",
        action="store_true",
        help="Call Vobiz directly and skip server-side provider prewarm.",
    )
    return parser.parse_args()


async def _main() -> int:
    args = _parse_args()
    settings = get_settings()
    try:
        if args.direct_vobiz:
            client = VobizOutboundClient(settings)
            result = await client.make_call(
                args.to_number,
                from_number=args.from_number,
                answer_url=args.answer_url,
            )
        else:
            result = await _make_call_through_server(
                args.to_number,
                from_number=args.from_number,
                answer_url=args.answer_url,
                agent_id=args.agent_id,
                api_url=args.api_url or f"http://127.0.0.1:{settings.api_port}",
            )
    except (ValueError, RuntimeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    print(result)
    return 0


async def _make_call_through_server(
    to_number: str,
    *,
    from_number: str | None,
    answer_url: str | None,
    agent_id: str | None,
    api_url: str,
) -> dict[str, Any]:
    payload = {
        "to_number": to_number,
        "from_number": from_number,
        "answer_url": answer_url,
        "agent_id": agent_id,
    }
    body = json.dumps({key: value for key, value in payload.items() if value is not None}).encode("utf-8")
    request = Request(
        f"{api_url.rstrip('/')}/vobiz/call",
        data=body,
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    return await asyncio.to_thread(_send_json_request, request)


def _send_json_request(request: Request) -> dict[str, Any]:
    try:
        with urlopen(request, timeout=30) as response:
            data = response.read()
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace") if exc.fp else ""
        raise RuntimeError(f"Mercury /vobiz/call failed with HTTP {exc.code}: {detail}") from exc
    except URLError as exc:
        raise RuntimeError(f"Mercury /vobiz/call failed: {exc.reason}") from exc
    return json.loads(data.decode("utf-8"))


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_main()))
