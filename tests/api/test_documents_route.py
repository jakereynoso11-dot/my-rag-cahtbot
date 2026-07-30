import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.deps import get_current_user, get_postgrest_client, get_powabase_client
from app.api.routes.documents import router as documents_router

app = FastAPI()
app.include_router(documents_router)
client = TestClient(app)


class FakePostgrestClient:
    def __init__(self, rows):
        self.chatbot_row = {"id": "chatbot-1", "powabase_agent_id": "agent-1"}
        self._rows = rows
        self.select_calls = []

    async def select_one(self, table, filters, columns, *, access_token):
        return self.chatbot_row

    async def select(self, table, columns, *, filters=None, order=None, access_token):
        self.select_calls.append((table, columns, filters, order, access_token))
        return self._rows


class FakePowabaseClient:
    pass


@pytest.fixture(autouse=True)
def clear_overrides():
    yield
    app.dependency_overrides.clear()


def test_list_documents_returns_rows_for_own_chatbot():
    rows = [
        {
            "id": "cd-1",
            "display_name": "a.pdf",
            "created_at": "2026-01-01T00:00:00Z",
            "documents": {"index_status": "indexed", "original_filename": "a.pdf"},
        }
    ]
    postgrest = FakePostgrestClient(rows)
    app.dependency_overrides[get_current_user] = lambda: {"id": "user-1"}
    app.dependency_overrides[get_postgrest_client] = lambda: postgrest
    app.dependency_overrides[get_powabase_client] = lambda: FakePowabaseClient()

    response = client.get("/documents", headers={"Authorization": "Bearer test-token"})

    assert response.status_code == 200
    assert response.json() == rows
    assert postgrest.select_calls[0][2] == {"chatbot_id": "chatbot-1"}


def test_list_documents_requires_auth():
    response = client.get("/documents")

    assert response.status_code == 401
