#!/usr/bin/env python3
"""Place a Vobiz outbound call that connects to this project's media WebSocket."""

from __future__ import annotations

import argparse
import asyncio
import sys

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
    return parser.parse_args()


async def _main() -> int:
    args = _parse_args()
    settings = get_settings()
    client = VobizOutboundClient(settings)
    try:
        result = await client.make_call(
            args.to_number,
            from_number=args.from_number,
            answer_url=args.answer_url,
        )
    except (ValueError, RuntimeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    print(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_main()))
