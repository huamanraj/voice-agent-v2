"""Helpers for Vobiz VoiceXML answer URLs and media stream WebSockets."""

from __future__ import annotations

from urllib.parse import urlencode
from urllib.parse import parse_qsl, urlsplit, urlunsplit
from xml.sax.saxutils import escape

from voice_agent.config import Settings


def public_media_stream_url(
    settings: Settings,
    *,
    agent_id: str | None = None,
    prewarm_id: str | None = None,
) -> str:
    """WebSocket URL Vobiz should connect to for live call audio."""
    base = settings.public_ws_base_url.rstrip("/")
    path = settings.vobiz_stream_ws_path
    if not path.startswith("/"):
        path = f"/{path}"
    url = f"{base}{path}"
    query_params: dict[str, str] = {}
    if settings.vobiz_stream_auth_token:
        query_params["token"] = settings.vobiz_stream_auth_token
    if agent_id:
        query_params["agent_id"] = agent_id
    if prewarm_id:
        query_params["prewarm_id"] = prewarm_id
    if query_params:
        query = urlencode(query_params)
        url = f"{url}?{query}"
    return url


def vobiz_answer_xml(
    settings: Settings,
    *,
    agent_id: str | None = None,
    prewarm_id: str | None = None,
) -> str:
    stream_url = public_media_stream_url(settings, agent_id=agent_id, prewarm_id=prewarm_id)
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        "<Response>\n"
        '  <Stream bidirectional="true" audioTrack="inbound" '
        'streamTimeout="7200" keepCallAlive="true" '
        'contentType="audio/x-mulaw;rate=8000">'
        f"{escape(stream_url)}"
        "</Stream>\n"
        "</Response>\n"
    )


def with_query_params(url: str, params: dict[str, str | None]) -> str:
    split = urlsplit(url)
    query = dict(parse_qsl(split.query, keep_blank_values=True))
    for key, value in params.items():
        if value is not None:
            query[key] = value
    return urlunsplit(
        (
            split.scheme,
            split.netloc,
            split.path,
            urlencode(query),
            split.fragment,
        )
    )
