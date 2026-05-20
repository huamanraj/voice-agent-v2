from fastapi.testclient import TestClient

from voice_agent.api.app import create_app
from voice_agent.config import Settings


def test_vobiz_answer_returns_stream_xml() -> None:
    settings = Settings(
        public_ws_base_url="wss://example.ngrok.app",
        vobiz_stream_ws_path="/ws/vobiz",
        vobiz_stream_auth_token=None,
    )
    client = TestClient(create_app(settings=settings))

    response = client.get("/vobiz/answer")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/xml")
    assert 'bidirectional="true"' in response.text
    assert 'audioTrack="inbound"' in response.text
    assert 'keepCallAlive="true"' in response.text
    assert 'contentType="audio/x-mulaw;rate=8000"' in response.text
    assert ">wss://example.ngrok.app/ws/vobiz</Stream>" in response.text


def test_vobiz_answer_can_attach_agent_id_to_stream_url() -> None:
    settings = Settings(
        public_ws_base_url="wss://example.ngrok.app",
        vobiz_stream_ws_path="/ws/vobiz",
        vobiz_stream_auth_token="stream-token",
    )
    client = TestClient(create_app(settings=settings))

    response = client.get("/vobiz/answer?agent_id=sales")

    assert response.status_code == 200
    assert ">wss://example.ngrok.app/ws/vobiz?token=stream-token&amp;agent_id=sales</Stream>" in response.text
