import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.deps import get_bearer_token, get_postgrest_client, get_powabase_client
from app.api.routes.ingest import router as ingest_router
from app.services.document_ingestion import DocumentIngestResult
from app.services.ingest_service import ExtractionNotUsableError, PollTimeoutError

app = FastAPI()
app.include_router(ingest_router)
client = TestClient(app)

AUTH_HEADER = {"Authorization": "Bearer user-jwt-token"}


class FakePostgrestClient:
    def __init__(self, chatbot_row=None):
        self._chatbot_row = chatbot_row

    async def select_one(self, table, filters, columns, *, access_token):
        return self._chatbot_row


class FakePowabaseClient:
    pass


def _post(chatbot_id="cb-1", headers=None, files=None):
    return client.post(
        "/ingest/file",
        data={"chatbot_id": chatbot_id},
        files=files or {"file": ("doc.pdf", b"%PDF-1.4 fake", "application/pdf")},
        headers=headers if headers is not None else AUTH_HEADER,
    )


def _override_chatbot_lookup(chatbot_row):
    app.dependency_overrides[get_postgrest_client] = lambda: FakePostgrestClient(chatbot_row)
    app.dependency_overrides[get_powabase_client] = lambda: FakePowabaseClient()


@pytest.fixture(autouse=True)
def clear_overrides():
    yield
    app.dependency_overrides.pop(get_postgrest_client, None)
    app.dependency_overrides.pop(get_powabase_client, None)
    app.dependency_overrides.pop(get_bearer_token, None)


def _patch_ingest(monkeypatch, result=None, error=None):
    async def fake_ingest_document_for_chatbot(**kwargs):
        if error:
            raise error
        return result

    import app.api.routes.ingest as ingest_route_module

    monkeypatch.setattr(
        ingest_route_module, "ingest_document_for_chatbot", fake_ingest_document_for_chatbot
    )


def test_ingest_file_missing_authorization_returns_401():
    response = _post(headers={})

    assert response.status_code == 401


def test_ingest_file_chatbot_not_found_returns_404():
    _override_chatbot_lookup(None)

    response = _post()

    assert response.status_code == 404


def test_ingest_file_success(monkeypatch):
    _override_chatbot_lookup({"id": "cb-1", "powabase_agent_id": "agent-1"})
    _patch_ingest(
        monkeypatch,
        result=DocumentIngestResult(
            document_id="doc-1",
            is_new=True,
            index_status="indexed",
            chatbot_document_id="cd-1",
        ),
    )

    response = _post()

    assert response.status_code == 200
    assert response.json() == {
        "document_id": "doc-1",
        "is_new": True,
        "index_status": "indexed",
        "chatbot_document_id": "cd-1",
    }


def test_ingest_file_extraction_not_usable_returns_422(monkeypatch):
    _override_chatbot_lookup({"id": "cb-1", "powabase_agent_id": "agent-1"})
    _patch_ingest(monkeypatch, error=ExtractionNotUsableError("src-1", "attention_required"))

    response = _post()

    assert response.status_code == 422


def test_ingest_file_poll_timeout_returns_504(monkeypatch):
    _override_chatbot_lookup({"id": "cb-1", "powabase_agent_id": "agent-1"})
    _patch_ingest(monkeypatch, error=PollTimeoutError("indexing", "idx-1"))

    response = _post()

    assert response.status_code == 504


def test_ingest_file_upstream_http_error_returns_502(monkeypatch):
    _override_chatbot_lookup({"id": "cb-1", "powabase_agent_id": "agent-1"})
    _patch_ingest(
        monkeypatch,
        error=httpx.HTTPStatusError(
            "boom",
            request=httpx.Request("POST", "https://x/api/sources/upload"),
            response=httpx.Response(500, request=httpx.Request("POST", "https://x")),
        ),
    )

    response = _post()

    assert response.status_code == 502


def test_ingest_file_powabase_insufficient_credits_returns_402(monkeypatch):
    _override_chatbot_lookup({"id": "cb-1", "powabase_agent_id": "agent-1"})
    _patch_ingest(
        monkeypatch,
        error=httpx.HTTPStatusError(
            "insufficient_credits",
            request=httpx.Request("POST", "https://x/api/sources/upload"),
            response=httpx.Response(402, request=httpx.Request("POST", "https://x")),
        ),
    )

    response = _post()

    assert response.status_code == 402


def test_ingest_file_connection_error_returns_502(monkeypatch):
    _override_chatbot_lookup({"id": "cb-1", "powabase_agent_id": "agent-1"})
    _patch_ingest(
        monkeypatch,
        error=httpx.ConnectError("connection failed", request=httpx.Request("POST", "https://x")),
    )

    response = _post()

    assert response.status_code == 502
