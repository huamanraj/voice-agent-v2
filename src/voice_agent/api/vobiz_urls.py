"""Helpers for Vobiz VoiceXML answer URLs and media stream WebSockets."""

from __future__ import annotations

from urllib.parse import urlencode
from xml.sax.saxutils import escape

from voice_agent.config import Settings


def public_media_stream_url(settings: Settings) -> str:
    """WebSocket URL Vobiz should connect to for live call audio."""
    base = settings.public_ws_base_url.rstrip("/")
    path = settings.vobiz_stream_ws_path
    if not path.startswith("/"):
        path = f"/{path}"
    url = f"{base}{path}"
    if settings.vobiz_stream_auth_token:
        query = urlencode({"token": settings.vobiz_stream_auth_token})
        url = f"{url}?{query}"
    return url


def vobiz_answer_xml(settings: Settings) -> str:
    stream_url = public_media_stream_url(settings)
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
