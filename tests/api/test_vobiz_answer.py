from urllib.parse import parse_qs, urlsplit

from fastapi.testclient import TestClient

from voice_agent.api.app import create_app
from voice_agent.config import Settings
from voice_agent.factory.provider_registry import ProviderRegistry
from voice_agent.providers.llm import MockLLM
from voice_agent.providers.storage import MemoryStore
from voice_agent.providers.stt import MockSTT
from voice_agent.providers.tts import MockTTS


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


def test_vobiz_answer_can_attach_prewarm_id_to_stream_url() -> None:
    settings = Settings(
        public_ws_base_url="wss://example.ngrok.app",
        vobiz_stream_ws_path="/ws/vobiz",
        vobiz_stream_auth_token=None,
    )
    client = TestClient(create_app(settings=settings))

    response = client.get("/vobiz/answer?prewarm_id=prewarm-123")

    assert response.status_code == 200
    assert ">wss://example.ngrok.app/ws/vobiz?prewarm_id=prewarm-123</Stream>" in response.text


def test_vobiz_call_prewarms_providers_before_outbound_request() -> None:
    settings = Settings(
        stt_provider="mock",
        tts_provider="mock",
        llm_provider="mock",
        live_store_provider="memory",
        final_store_provider="memory",
        agent_config_path="missing-agent-test-file.json",
        default_agent_id="fallback",
        vad_enabled=False,
        smart_turn_enabled=False,
        vobiz_auth_id="auth-123",
        vobiz_auth_token="token-123",
        vobiz_from_number="+14155550000",
        vobiz_answer_url="https://voice.example.com/vobiz/answer",
    )
    registry = ProviderRegistry()
    registry.register("stt", "mock", MockSTT)
    registry.register("tts", "mock", MockTTS)
    registry.register("llm", "mock", MockLLM)
    registry.register("live_store", "memory", MemoryStore)
    registry.register("final_store", "memory", MemoryStore)

    class FakeOutboundClient:
        def __init__(self) -> None:
            self.calls = []

        async def make_call(self, to_number, **kwargs):
            self.calls.append({"to_number": to_number, **kwargs})
            return {"request_uuid": "req-1"}

    fake_client = FakeOutboundClient()
    app = create_app(settings=settings, registry=registry)
    app.state.vobiz_outbound_client_factory = lambda _settings: fake_client

    with TestClient(app) as client:
        response = client.post(
            "/vobiz/call",
            json={"to_number": "+919876543210", "agent_id": "fallback"},
        )

        assert response.status_code == 200
        payload = response.json()
        prewarm_id = payload["prewarm_id"]
        assert payload["request_uuid"] == "req-1"
        assert fake_client.calls[0]["to_number"] == "+919876543210"
        answer_url = fake_client.calls[0]["answer_url"]
        query = parse_qs(urlsplit(answer_url).query)
        assert query["agent_id"] == ["fallback"]
        assert query["prewarm_id"] == [prewarm_id]

        pool = app.state.provider_warmup_pool
        entry = pool._entries[prewarm_id]
        assert entry.bundle.stt.call_id == prewarm_id
        assert entry.bundle.tts.call_id == prewarm_id
