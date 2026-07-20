from app.api.deps import get_chat_service, get_ingest_service, get_powabase_client
from app.clients.powabase_client import PowabaseClient
from app.services.chat_service import ChatService
from app.services.ingest_service import IngestService


def test_get_powabase_client_uses_settings(monkeypatch):
    import app.core.config as config_module

    monkeypatch.setattr(config_module.settings, "powabase_base_url", "https://x.p.powabase.ai")
    monkeypatch.setattr(config_module.settings, "powabase_api_key", "key-123")

    client = get_powabase_client()

    assert isinstance(client, PowabaseClient)
    assert client.base_url == "https://x.p.powabase.ai"
    assert client.headers["apikey"] == "key-123"


def test_get_ingest_service_wires_kb_id(monkeypatch):
    import app.core.config as config_module

    monkeypatch.setattr(config_module.settings, "powabase_kb_id", "kb-123")
    client = PowabaseClient(base_url="https://x.p.powabase.ai", api_key="key")

    service = get_ingest_service(client=client)

    assert isinstance(service, IngestService)
    assert service.kb_id == "kb-123"


def test_get_chat_service_wires_agent_id(monkeypatch):
    import app.core.config as config_module

    monkeypatch.setattr(config_module.settings, "powabase_agent_id", "agent-123")
    client = PowabaseClient(base_url="https://x.p.powabase.ai", api_key="key")

    service = get_chat_service(client=client)

    assert isinstance(service, ChatService)
    assert service.agent_id == "agent-123"
