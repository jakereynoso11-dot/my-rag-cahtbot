import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.deps import get_current_user, get_postgrest_client, get_powabase_client
from app.api.routes.chat import router as chat_router

app = FastAPI()
app.include_router(chat_router)
client = TestClient(app)


_DEFAULT_SESSION_ROW = object()


class FakePostgrestClient:
    def __init__(self, session_row=_DEFAULT_SESSION_ROW, list_rows=None):
        self.session_row = (
            {"id": "sess-1", "powabase_agent_id": None}
            if session_row is _DEFAULT_SESSION_ROW
            else session_row
        )
        self.list_rows = list_rows or []
        self.rpc_results = {
            "register_or_get_document": [
                {
                    "id": "doc-1",
                    "is_new": True,
                    "index_status": "pending",
                    "powabase_source_id": None,
                    "powabase_knowledge_base_id": None,
                }
            ],
        }
        self.update_calls = []

    async def select_one(self, table, filters, columns, *, access_token):
        if table == "chat_sessions":
            return self.session_row
        raise AssertionError(f"unexpected select_one on {table}")

    async def rpc(self, function_name, payload, *, access_token):
        return self.rpc_results[function_name]

    async def update(self, table, filters, values, *, access_token):
        self.update_calls.append((table, filters, values))
        return [values]

    async def insert(self, table, values, *, access_token):
        return {**values, "id": "session-doc-1"}

    async def select(self, table, columns, *, filters=None, order=None, access_token):
        if table == "chat_session_documents":
            return self.list_rows
        raise AssertionError(f"unexpected select on {table}")


class FakePowabaseClient:
    def __init__(self):
        self.create_agent_calls = []

    async def create_knowledge_base(self, name):
        return {"id": "kb-new"}

    async def upload_source(self, filename, content):
        return {"id": "src-1"}

    async def get_source(self, source_id):
        return {"id": source_id, "extraction_status": "extracted"}

    async def add_source_to_kb(self, kb_id, source_id):
        return {"id": "idx-1"}

    async def list_kb_sources(self, kb_id):
        return {"items": [{"id": "idx-1", "index_status": "indexed"}]}

    async def add_knowledge_base_to_agent(self, agent_id, kb_id):
        return {"id": "link-1"}

    async def create_agent(self, name, system_prompt):
        self.create_agent_calls.append((name, system_prompt))
        return {"id": "session-agent-new"}


@pytest.fixture(autouse=True)
def clear_overrides():
    yield
    app.dependency_overrides.clear()


def test_upload_session_document_creates_dedicated_agent():
    postgrest = FakePostgrestClient()
    powabase = FakePowabaseClient()
    app.dependency_overrides[get_current_user] = lambda: {"id": "user-1"}
    app.dependency_overrides[get_postgrest_client] = lambda: postgrest
    app.dependency_overrides[get_powabase_client] = lambda: powabase

    response = client.post(
        "/chat/sessions/sess-1/documents",
        files={"file": ("notes.pdf", b"%PDF-1.4 fake", "application/pdf")},
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "document_id": "doc-1",
        "is_new": True,
        "index_status": "indexed",
        "session_document_id": "session-doc-1",
    }
    assert powabase.create_agent_calls == [("session-sess-1", powabase.create_agent_calls[0][1])]
    assert (
        "chat_sessions",
        {"id": "sess-1"},
        {"powabase_agent_id": "session-agent-new"},
    ) in postgrest.update_calls


def test_upload_session_document_returns_404_when_session_missing():
    postgrest = FakePostgrestClient(session_row=None)
    powabase = FakePowabaseClient()
    app.dependency_overrides[get_current_user] = lambda: {"id": "user-1"}
    app.dependency_overrides[get_postgrest_client] = lambda: postgrest
    app.dependency_overrides[get_powabase_client] = lambda: powabase

    response = client.post(
        "/chat/sessions/sess-missing/documents",
        files={"file": ("notes.pdf", b"%PDF-1.4 fake", "application/pdf")},
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 404


def test_upload_session_document_requires_auth():
    response = client.post(
        "/chat/sessions/sess-1/documents",
        files={"file": ("notes.pdf", b"%PDF-1.4 fake", "application/pdf")},
    )

    assert response.status_code == 401


def test_list_session_documents_returns_rows():
    postgrest = FakePostgrestClient(
        list_rows=[
            {
                "id": "sd-1",
                "display_name": "notes.pdf",
                "created_at": "2026-01-01T00:00:00Z",
                "documents": {"index_status": "indexed", "original_filename": "notes.pdf"},
            }
        ]
    )
    app.dependency_overrides[get_current_user] = lambda: {"id": "user-1"}
    app.dependency_overrides[get_postgrest_client] = lambda: postgrest

    response = client.get(
        "/chat/sessions/sess-1/documents", headers={"Authorization": "Bearer test-token"}
    )

    assert response.status_code == 200
    assert response.json()[0]["display_name"] == "notes.pdf"
