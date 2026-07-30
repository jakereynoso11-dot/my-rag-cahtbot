import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.deps import get_current_user, get_postgrest_client, get_powabase_client
from app.api.routes.chat import router as chat_router

app = FastAPI()
app.include_router(chat_router)
client = TestClient(app)


class FakePostgrestClient:
    def __init__(self, chatbot_row=None, existing_session=None):
        self.chatbot_row = chatbot_row or {"id": "chatbot-1", "powabase_agent_id": "agent-1"}
        self.existing_session = existing_session
        self.inserted_rows = []
        self.update_calls = []
        self._next_session_id = "sess-new"

    async def select_one(self, table, filters, columns, *, access_token):
        if table == "chatbots":
            return self.chatbot_row
        if table == "chat_sessions":
            return self.existing_session
        raise AssertionError(f"unexpected select_one on {table}")

    async def insert(self, table, values, *, access_token):
        self.inserted_rows.append((table, values))
        if table == "chat_sessions":
            return {"id": self._next_session_id, "chatbot_id": values["chatbot_id"]}
        return {**values, "id": "row-1"}

    async def update(self, table, filters, values, *, access_token):
        self.update_calls.append((table, filters, values))
        return [values]

    async def select(self, table, columns, *, filters=None, order=None, access_token):
        if table == "chat_sessions":
            return [{"id": "sess-1", "title": None, "created_at": "2026-01-01T00:00:00Z"}]
        if table == "messages":
            return [
                {"id": "m1", "role": "user", "content": "hi", "created_at": "2026-01-01T00:00:00Z"}
            ]
        raise AssertionError(f"unexpected select on {table}")


class FakePowabaseClient:
    def __init__(self, lines=None):
        self._lines = lines or []

    async def create_agent(self, name, system_prompt):
        return {"id": "agent-new"}

    async def stream_agent_run(self, agent_id, message, session_id=None, temperature=None):
        for line in self._lines:
            yield line


@pytest.fixture(autouse=True)
def clear_overrides():
    yield
    app.dependency_overrides.clear()


def test_chat_starts_new_session_and_persists_messages():
    postgrest = FakePostgrestClient()
    powabase = FakePowabaseClient(
        lines=[
            'data: {"event": "start", "session_id": "powabase-sess-1"}',
            'data: {"event": "complete", "status": "completed", "content": "hi there"}',
        ]
    )
    app.dependency_overrides[get_current_user] = lambda: {"id": "user-1"}
    app.dependency_overrides[get_postgrest_client] = lambda: postgrest
    app.dependency_overrides[get_powabase_client] = lambda: powabase

    response = client.post(
        "/chat", json={"message": "hello"}, headers={"Authorization": "Bearer test-token"}
    )

    assert response.status_code == 200
    assert response.json() == {"answer": "hi there", "sources": [], "session_id": "sess-new"}

    message_inserts = [row for table, row in postgrest.inserted_rows if table == "messages"]
    assert message_inserts == [
        {"session_id": "sess-new", "role": "user", "content": "hello"},
        {"session_id": "sess-new", "role": "assistant", "content": "hi there"},
    ]
    assert postgrest.update_calls == [
        (
            "chat_sessions",
            {"id": "sess-new"},
            {"powabase_session_id": "powabase-sess-1"},
        )
    ]

    session_inserts = [row for table, row in postgrest.inserted_rows if table == "chat_sessions"]
    assert session_inserts == [{"chatbot_id": "chatbot-1"}]


def test_chat_continues_existing_session_without_updating_powabase_session_id():
    postgrest = FakePostgrestClient(
        existing_session={"id": "sess-1", "powabase_session_id": "powabase-sess-1"}
    )
    powabase = FakePowabaseClient(
        lines=[
            'data: {"event": "start", "session_id": "powabase-sess-1"}',
            'data: {"event": "complete", "status": "completed", "content": "second answer"}',
        ]
    )
    app.dependency_overrides[get_current_user] = lambda: {"id": "user-1"}
    app.dependency_overrides[get_postgrest_client] = lambda: postgrest
    app.dependency_overrides[get_powabase_client] = lambda: powabase

    response = client.post(
        "/chat",
        json={"message": "follow up", "session_id": "sess-1"},
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 200
    assert response.json()["session_id"] == "sess-1"
    assert postgrest.update_calls == []


def test_chat_requires_auth():
    response = client.post("/chat", json={"message": "hello"})

    assert response.status_code == 401


def test_chat_returns_502_on_run_failure():
    postgrest = FakePostgrestClient()
    powabase = FakePowabaseClient(lines=['data: {"event": "error", "message": "boom"}'])
    app.dependency_overrides[get_current_user] = lambda: {"id": "user-1"}
    app.dependency_overrides[get_postgrest_client] = lambda: postgrest
    app.dependency_overrides[get_powabase_client] = lambda: powabase

    response = client.post(
        "/chat", json={"message": "hello"}, headers={"Authorization": "Bearer test-token"}
    )

    assert response.status_code == 502


def test_list_sessions_returns_rows_for_own_chatbot():
    postgrest = FakePostgrestClient()
    app.dependency_overrides[get_current_user] = lambda: {"id": "user-1"}
    app.dependency_overrides[get_postgrest_client] = lambda: postgrest
    app.dependency_overrides[get_powabase_client] = lambda: FakePowabaseClient()

    response = client.get("/chat/sessions", headers={"Authorization": "Bearer test-token"})

    assert response.status_code == 200
    assert response.json() == [
        {"id": "sess-1", "title": None, "created_at": "2026-01-01T00:00:00Z"}
    ]


def test_list_session_messages_returns_rows():
    postgrest = FakePostgrestClient()
    app.dependency_overrides[get_current_user] = lambda: {"id": "user-1"}
    app.dependency_overrides[get_postgrest_client] = lambda: postgrest

    response = client.get(
        "/chat/sessions/sess-1/messages", headers={"Authorization": "Bearer test-token"}
    )

    assert response.status_code == 200
    assert response.json() == [
        {"id": "m1", "role": "user", "content": "hi", "created_at": "2026-01-01T00:00:00Z"}
    ]
