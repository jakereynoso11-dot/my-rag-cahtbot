import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.deps import get_current_user, get_postgrest_client, get_powabase_client
from app.api.routes.chat import router as chat_router
from app.clients.powabase_client import AgentNotFoundError

app = FastAPI()
app.include_router(chat_router)
client = TestClient(app)

_DEFAULT_CHATBOT_ROW = object()


class FakePostgrestClient:
    def __init__(
        self,
        chatbot_row=_DEFAULT_CHATBOT_ROW,
        existing_session=None,
        delete_result=None,
        specialist_rows=None,
    ):
        self.chatbot_row = (
            {"id": "chatbot-1", "powabase_agent_id": "agent-1"}
            if chatbot_row is _DEFAULT_CHATBOT_ROW
            else chatbot_row
        )
        self.existing_session = existing_session
        self.inserted_rows = []
        self.update_calls = []
        self.delete_calls = []
        self._next_session_id = "sess-new"
        self._delete_result = (
            [{"id": "sess-1"}] if delete_result is None else delete_result
        )
        self.specialist_rows = specialist_rows or []

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

    async def delete(self, table, filters, *, access_token):
        self.delete_calls.append((table, filters))
        return self._delete_result

    async def select(self, table, columns, *, filters=None, order=None, access_token):
        if table == "chat_sessions":
            return [{"id": "sess-1", "title": None, "created_at": "2026-01-01T00:00:00Z"}]
        if table == "messages":
            return [
                {"id": "m1", "role": "user", "content": "hi", "created_at": "2026-01-01T00:00:00Z"}
            ]
        if table == "chatbot_documents":
            return [{"documents": {"powabase_knowledge_base_id": "kb-1"}}]
        if table == "chatbot_specialists":
            return self.specialist_rows
        raise AssertionError(f"unexpected select on {table}")


class FakePowabaseClient:
    def __init__(
        self,
        lines=None,
        not_found_for_agent_id=None,
        lines_after_recovery=None,
        routing_reply=None,
        specialist_answers=None,
    ):
        self._lines = lines or []
        self._not_found_for_agent_id = not_found_for_agent_id
        self._lines_after_recovery = lines_after_recovery or []
        self.link_agent_calls = []
        self._routing_reply = routing_reply
        self._specialist_answers = specialist_answers or {}
        self.run_calls = []

    async def create_agent(self, name, system_prompt):
        return {"id": "agent-recovered"}

    async def add_knowledge_base_to_agent(self, agent_id, kb_id):
        self.link_agent_calls.append((agent_id, kb_id))
        return {"id": "link-1"}

    async def stream_agent_run(self, agent_id, message, session_id=None, temperature=None):
        self.run_calls.append((agent_id, message, session_id))
        if agent_id == self._not_found_for_agent_id:
            raise AgentNotFoundError(agent_id)

        if "routing classifier" in message:
            reply = self._routing_reply if self._routing_reply is not None else "NONE"
            yield f'data: {{"event": "complete", "status": "completed", "content": "{reply}"}}'
            return

        if agent_id in self._specialist_answers:
            content = self._specialist_answers[agent_id]
            yield f'data: {{"event": "complete", "status": "completed", "content": "{content}"}}'
            return

        lines = self._lines_after_recovery if agent_id == "agent-recovered" else self._lines
        for line in lines:
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
        "/chat",
        json={"chatbot_id": "chatbot-1", "message": "hello"},
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "answer": "hi there",
        "sources": [],
        "session_id": "sess-new",
        "specialist_name": None,
    }

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
        json={"chatbot_id": "chatbot-1", "message": "follow up", "session_id": "sess-1"},
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 200
    assert response.json()["session_id"] == "sess-1"
    assert postgrest.update_calls == []


def test_chat_requires_auth():
    response = client.post("/chat", json={"chatbot_id": "chatbot-1", "message": "hello"})

    assert response.status_code == 401


def test_chat_returns_404_when_chatbot_not_owned():
    postgrest = FakePostgrestClient(chatbot_row=None)
    powabase = FakePowabaseClient()
    app.dependency_overrides[get_current_user] = lambda: {"id": "user-1"}
    app.dependency_overrides[get_postgrest_client] = lambda: postgrest
    app.dependency_overrides[get_powabase_client] = lambda: powabase

    response = client.post(
        "/chat",
        json={"chatbot_id": "not-mine", "message": "hello"},
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 404


def test_chat_returns_502_on_run_failure():
    postgrest = FakePostgrestClient()
    powabase = FakePowabaseClient(lines=['data: {"event": "error", "message": "boom"}'])
    app.dependency_overrides[get_current_user] = lambda: {"id": "user-1"}
    app.dependency_overrides[get_postgrest_client] = lambda: postgrest
    app.dependency_overrides[get_powabase_client] = lambda: powabase

    response = client.post(
        "/chat",
        json={"chatbot_id": "chatbot-1", "message": "hello"},
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 502


def test_chat_recovers_and_retries_when_stored_agent_was_deleted():
    postgrest = FakePostgrestClient()
    powabase = FakePowabaseClient(
        not_found_for_agent_id="agent-1",
        lines_after_recovery=[
            'data: {"event": "start", "session_id": "powabase-sess-2"}',
            'data: {"event": "complete", "status": "completed", "content": "back online"}',
        ],
    )
    app.dependency_overrides[get_current_user] = lambda: {"id": "user-1"}
    app.dependency_overrides[get_postgrest_client] = lambda: postgrest
    app.dependency_overrides[get_powabase_client] = lambda: powabase

    response = client.post(
        "/chat",
        json={"chatbot_id": "chatbot-1", "message": "hello"},
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 200
    assert response.json()["answer"] == "back online"
    assert powabase.link_agent_calls == [("agent-recovered", "kb-1")]
    assert (
        "chatbots",
        {"id": "chatbot-1"},
        {"powabase_agent_id": "agent-recovered"},
    ) in postgrest.update_calls


def test_chat_routes_to_the_only_specialist_without_a_classification_call():
    postgrest = FakePostgrestClient(
        specialist_rows=[
            {
                "id": "spec-1",
                "name": "Billing Agent",
                "specialty": "billing questions",
                "powabase_agent_id": "agent-billing",
            }
        ]
    )
    powabase = FakePowabaseClient(
        specialist_answers={"agent-billing": "your invoice is paid"}
    )
    app.dependency_overrides[get_current_user] = lambda: {"id": "user-1"}
    app.dependency_overrides[get_postgrest_client] = lambda: postgrest
    app.dependency_overrides[get_powabase_client] = lambda: powabase

    response = client.post(
        "/chat",
        json={"chatbot_id": "chatbot-1", "message": "what's my invoice status"},
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["answer"] == "your invoice is paid"
    assert body["specialist_name"] == "Billing Agent"
    # No routing classifier call needed when there's only one specialist.
    assert all("routing classifier" not in call[1] for call in powabase.run_calls)
    assert ("agent-billing", "what's my invoice status", None) in [
        (a, m, s) for a, m, s in powabase.run_calls
    ]


def test_chat_routes_to_matching_specialist_via_classification():
    postgrest = FakePostgrestClient(
        specialist_rows=[
            {
                "id": "spec-1",
                "name": "Billing Agent",
                "specialty": "billing questions",
                "powabase_agent_id": "agent-billing",
            },
            {
                "id": "spec-2",
                "name": "Tax Agent",
                "specialty": "tax questions",
                "powabase_agent_id": "agent-tax",
            },
        ]
    )
    powabase = FakePowabaseClient(
        routing_reply="Tax Agent",
        specialist_answers={"agent-tax": "here's your tax answer"},
    )
    app.dependency_overrides[get_current_user] = lambda: {"id": "user-1"}
    app.dependency_overrides[get_postgrest_client] = lambda: postgrest
    app.dependency_overrides[get_powabase_client] = lambda: powabase

    response = client.post(
        "/chat",
        json={"chatbot_id": "chatbot-1", "message": "how do I file a w2"},
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["answer"] == "here's your tax answer"
    assert body["specialist_name"] == "Tax Agent"


def test_chat_falls_back_to_parent_chatbot_when_no_specialist_matches():
    postgrest = FakePostgrestClient(
        specialist_rows=[
            {
                "id": "spec-1",
                "name": "Billing Agent",
                "specialty": "billing questions",
                "powabase_agent_id": "agent-billing",
            },
            {
                "id": "spec-2",
                "name": "Tax Agent",
                "specialty": "tax questions",
                "powabase_agent_id": "agent-tax",
            },
        ]
    )
    powabase = FakePowabaseClient(
        routing_reply="NONE",
        lines=[
            'data: {"event": "start", "session_id": "powabase-sess-1"}',
            'data: {"event": "complete", "status": "completed", "content": "general answer"}',
        ],
    )
    app.dependency_overrides[get_current_user] = lambda: {"id": "user-1"}
    app.dependency_overrides[get_postgrest_client] = lambda: postgrest
    app.dependency_overrides[get_powabase_client] = lambda: powabase

    response = client.post(
        "/chat",
        json={"chatbot_id": "chatbot-1", "message": "what's the weather"},
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["answer"] == "general answer"
    assert body["specialist_name"] is None


def test_list_sessions_returns_rows_for_given_chatbot():
    postgrest = FakePostgrestClient()
    app.dependency_overrides[get_current_user] = lambda: {"id": "user-1"}
    app.dependency_overrides[get_postgrest_client] = lambda: postgrest

    response = client.get(
        "/chat/sessions",
        params={"chatbot_id": "chatbot-1"},
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 200
    assert response.json() == [
        {"id": "sess-1", "title": None, "created_at": "2026-01-01T00:00:00Z"}
    ]


def test_list_sessions_requires_chatbot_id():
    postgrest = FakePostgrestClient()
    app.dependency_overrides[get_current_user] = lambda: {"id": "user-1"}
    app.dependency_overrides[get_postgrest_client] = lambda: postgrest

    response = client.get("/chat/sessions", headers={"Authorization": "Bearer test-token"})

    assert response.status_code == 422


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


def test_delete_session_succeeds():
    postgrest = FakePostgrestClient(delete_result=[{"id": "sess-1"}])
    app.dependency_overrides[get_current_user] = lambda: {"id": "user-1"}
    app.dependency_overrides[get_postgrest_client] = lambda: postgrest

    response = client.delete(
        "/chat/sessions/sess-1", headers={"Authorization": "Bearer test-token"}
    )

    assert response.status_code == 204
    assert postgrest.delete_calls == [("chat_sessions", {"id": "sess-1"})]


def test_delete_session_returns_404_when_not_owned_or_missing():
    postgrest = FakePostgrestClient(delete_result=[])
    app.dependency_overrides[get_current_user] = lambda: {"id": "user-1"}
    app.dependency_overrides[get_postgrest_client] = lambda: postgrest

    response = client.delete(
        "/chat/sessions/not-mine", headers={"Authorization": "Bearer test-token"}
    )

    assert response.status_code == 404


def test_delete_session_requires_auth():
    response = client.delete("/chat/sessions/sess-1")

    assert response.status_code == 401
