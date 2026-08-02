import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.deps import get_current_user, get_postgrest_client, get_powabase_client
from app.api.routes.chatbots import router as chatbots_router

app = FastAPI()
app.include_router(chatbots_router)
client = TestClient(app)


class FakePostgrestClient:
    def __init__(self, chatbot_row=None, list_rows=None):
        self.chatbot_row = chatbot_row
        self.list_rows = list_rows or []
        self.insert_calls = []
        self.update_calls = []
        self.delete_calls = []

    async def select(self, table, columns, *, filters=None, order=None, access_token):
        return self.list_rows

    async def select_one(self, table, filters, columns, *, access_token):
        return self.chatbot_row

    async def insert(self, table, values, *, access_token):
        self.insert_calls.append((table, values, access_token))
        self.chatbot_row = {
            "id": "chatbot-new",
            "created_at": "2026-01-01T00:00:00Z",
            **values,
        }
        return self.chatbot_row

    async def update(self, table, filters, values, *, access_token):
        self.update_calls.append((table, filters, values, access_token))
        if self.chatbot_row is None:
            return []
        self.chatbot_row = {**self.chatbot_row, **values}
        return [self.chatbot_row]

    async def delete(self, table, filters, *, access_token):
        self.delete_calls.append((table, filters, access_token))
        if self.chatbot_row is None:
            return []
        return [self.chatbot_row]


class FakePowabaseClient:
    def __init__(self):
        self.create_agent_calls = []
        self.delete_agent_calls = []

    async def create_agent(self, name, system_prompt):
        self.create_agent_calls.append((name, system_prompt))
        return {"id": "agent-new"}

    async def delete_agent(self, agent_id):
        self.delete_agent_calls.append(agent_id)


@pytest.fixture(autouse=True)
def clear_overrides():
    yield
    app.dependency_overrides.clear()


def test_list_chatbots_returns_owned_rows():
    postgrest = FakePostgrestClient(
        list_rows=[{"id": "cb-1", "name": "Tax Docs Helper", "created_at": "2026-01-01T00:00:00Z"}]
    )
    app.dependency_overrides[get_current_user] = lambda: {"id": "user-1"}
    app.dependency_overrides[get_postgrest_client] = lambda: postgrest

    response = client.get("/chatbots", headers={"Authorization": "Bearer test-token"})

    assert response.status_code == 200
    assert response.json() == [
        {"id": "cb-1", "name": "Tax Docs Helper", "created_at": "2026-01-01T00:00:00Z"}
    ]


def test_list_chatbots_requires_auth():
    response = client.get("/chatbots")

    assert response.status_code == 401


def test_create_chatbot_returns_new_row():
    postgrest = FakePostgrestClient()
    powabase = FakePowabaseClient()
    app.dependency_overrides[get_current_user] = lambda: {"id": "user-1"}
    app.dependency_overrides[get_postgrest_client] = lambda: postgrest
    app.dependency_overrides[get_powabase_client] = lambda: powabase

    response = client.post(
        "/chatbots",
        json={"name": "Tax Docs Helper", "system_prompt": "You're a tax assistant."},
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 200
    assert response.json()["name"] == "Tax Docs Helper"
    assert powabase.create_agent_calls == [
        ("Tax Docs Helper", "You're a tax assistant.")
    ]
    assert postgrest.insert_calls[0][1]["owner_id"] == "user-1"


def test_rename_chatbot_updates_name():
    postgrest = FakePostgrestClient(
        chatbot_row={"id": "cb-1", "name": "old", "created_at": "2026-01-01T00:00:00Z"}
    )
    app.dependency_overrides[get_current_user] = lambda: {"id": "user-1"}
    app.dependency_overrides[get_postgrest_client] = lambda: postgrest

    response = client.patch(
        "/chatbots/cb-1",
        json={"name": "new name"},
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 200
    assert response.json()["name"] == "new name"


def test_rename_chatbot_returns_404_when_not_owned():
    postgrest = FakePostgrestClient(chatbot_row=None)
    app.dependency_overrides[get_current_user] = lambda: {"id": "user-1"}
    app.dependency_overrides[get_postgrest_client] = lambda: postgrest

    response = client.patch(
        "/chatbots/cb-missing",
        json={"name": "new name"},
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 404


def test_delete_chatbot_succeeds():
    postgrest = FakePostgrestClient(chatbot_row={"id": "cb-1", "powabase_agent_id": "agent-1"})
    powabase = FakePowabaseClient()
    app.dependency_overrides[get_current_user] = lambda: {"id": "user-1"}
    app.dependency_overrides[get_postgrest_client] = lambda: postgrest
    app.dependency_overrides[get_powabase_client] = lambda: powabase

    response = client.delete(
        "/chatbots/cb-1", headers={"Authorization": "Bearer test-token"}
    )

    assert response.status_code == 204
    assert powabase.delete_agent_calls == ["agent-1"]


def test_delete_chatbot_returns_404_when_not_owned():
    postgrest = FakePostgrestClient(chatbot_row=None)
    powabase = FakePowabaseClient()
    app.dependency_overrides[get_current_user] = lambda: {"id": "user-1"}
    app.dependency_overrides[get_postgrest_client] = lambda: postgrest
    app.dependency_overrides[get_powabase_client] = lambda: powabase

    response = client.delete(
        "/chatbots/cb-missing", headers={"Authorization": "Bearer test-token"}
    )

    assert response.status_code == 404
