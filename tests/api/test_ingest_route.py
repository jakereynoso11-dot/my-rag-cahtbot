import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.deps import get_current_user, get_postgrest_client, get_powabase_client
from app.api.routes.ingest import router as ingest_router

app = FastAPI()
app.include_router(ingest_router)
client = TestClient(app)

_DEFAULT_CHATBOT_ROW = object()


class FakePostgrestClient:
    def __init__(self, chatbot_row=_DEFAULT_CHATBOT_ROW):
        self.chatbot_row = (
            {"id": "chatbot-1", "powabase_agent_id": "agent-1"}
            if chatbot_row is _DEFAULT_CHATBOT_ROW
            else chatbot_row
        )
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
            "attach_document_to_chatbot": {"id": "cd-1"},
        }

    async def select_one(self, table, filters, columns, *, access_token):
        return self.chatbot_row

    async def rpc(self, function_name, payload, *, access_token):
        return self.rpc_results[function_name]

    async def update(self, table, filters, values, *, access_token):
        return [values]

    async def insert(self, table, values, *, access_token):
        return {**values, "id": "row-1"}


class FakePowabaseClient:
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


@pytest.fixture(autouse=True)
def clear_overrides():
    yield
    app.dependency_overrides.clear()


def test_ingest_file_success():
    app.dependency_overrides[get_current_user] = lambda: {"id": "user-1"}
    app.dependency_overrides[get_postgrest_client] = lambda: FakePostgrestClient()
    app.dependency_overrides[get_powabase_client] = lambda: FakePowabaseClient()

    response = client.post(
        "/ingest/file",
        data={"chatbot_id": "chatbot-1"},
        files={"file": ("doc.pdf", b"%PDF-1.4 fake", "application/pdf")},
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "document_id": "doc-1",
        "is_new": True,
        "index_status": "indexed",
        "chatbot_document_id": "cd-1",
    }


def test_ingest_file_requires_chatbot_id():
    app.dependency_overrides[get_current_user] = lambda: {"id": "user-1"}
    app.dependency_overrides[get_postgrest_client] = lambda: FakePostgrestClient()
    app.dependency_overrides[get_powabase_client] = lambda: FakePowabaseClient()

    response = client.post(
        "/ingest/file",
        files={"file": ("doc.pdf", b"%PDF-1.4 fake", "application/pdf")},
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 422


def test_ingest_file_returns_404_when_chatbot_not_owned():
    app.dependency_overrides[get_current_user] = lambda: {"id": "user-1"}
    app.dependency_overrides[get_postgrest_client] = lambda: FakePostgrestClient(chatbot_row=None)
    app.dependency_overrides[get_powabase_client] = lambda: FakePowabaseClient()

    response = client.post(
        "/ingest/file",
        data={"chatbot_id": "not-mine"},
        files={"file": ("doc.pdf", b"%PDF-1.4 fake", "application/pdf")},
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 404


def test_ingest_file_requires_auth():
    response = client.post(
        "/ingest/file",
        data={"chatbot_id": "chatbot-1"},
        files={"file": ("doc.pdf", b"%PDF-1.4 fake", "application/pdf")},
    )

    assert response.status_code == 401
