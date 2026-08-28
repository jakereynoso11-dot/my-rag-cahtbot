import httpx
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.deps import get_postgrest_client, get_powabase_client
from app.api.routes.public_chat import router as public_chat_router
from app.core.config import settings

app = FastAPI()
app.include_router(public_chat_router)
client = TestClient(app)

SHARE_TOKEN = "share-token-1"
CHATBOT_ROW = {
    "id": "chatbot-1",
    "name": "Support Bot",
    "purpose": "Answer FAQs",
    "powabase_agent_id": "agent-1",
}


def _postgrest_400():
    return httpx.HTTPStatusError(
        "bad request",
        request=httpx.Request("GET", "https://x/rest/v1/chatbots"),
        response=httpx.Response(400, request=httpx.Request("GET", "https://x")),
    )


class FakePostgrestClient:
    def __init__(
        self,
        chatbot_row=CHATBOT_ROW,
        existing_sessions=None,
        raise_400_for_session_id=None,
        raise_400_for_share_token=None,
    ):
        self.chatbot_row = chatbot_row
        self.existing_sessions = existing_sessions or {}
        self.raise_400_for_session_id = raise_400_for_session_id
        self.raise_400_for_share_token = raise_400_for_share_token
        self.inserted_rows = []
        self.update_calls = []
        self.select_one_calls = []

    async def select_one(self, table, filters, columns, *, access_token):
        self.select_one_calls.append((table, filters, access_token))
        if table == "chatbots":
            if filters.get("share_token") == self.raise_400_for_share_token:
                raise _postgrest_400()
            if self.chatbot_row and filters.get("share_token") == SHARE_TOKEN:
                return self.chatbot_row
            return None
        if table == "chat_sessions":
            if filters.get("id") == self.raise_400_for_session_id:
                raise _postgrest_400()
            return self.existing_sessions.get(filters.get("id"))
        raise AssertionError(f"unexpected select_one on {table}")

    async def insert(self, table, values, *, access_token):
        self.inserted_rows.append((table, values, access_token))
        if table == "chat_sessions":
            return {"id": "sess-new", "chatbot_id": values["chatbot_id"]}
        return {**values, "id": "row-1"}

    async def update(self, table, filters, values, *, access_token):
        self.update_calls.append((table, filters, values, access_token))
        return [values]

    async def select(self, table, columns, *, filters=None, order=None, access_token):
        if table == "chatbot_specialists":
            return []
        if table == "messages":
            return [
                {"id": "m1", "role": "user", "content": "hi", "created_at": "2026-01-01T00:00:00Z"}
            ]
        raise AssertionError(f"unexpected select on {table}")


class FakePowabaseClient:
    def __init__(self, lines=None):
        self._lines = lines or [
            'data: {"event": "start", "session_id": "powabase-sess-1"}',
            'data: {"event": "complete", "status": "completed", "content": "hi there"}',
        ]

    async def stream_agent_run(
        self, agent_id, message, session_id=None, temperature=None, runtime_knowledge_bases=None
    ):
        for line in self._lines:
            yield line


def teardown_function():
    app.dependency_overrides.clear()


def test_get_public_chatbot_returns_name_and_purpose():
    app.dependency_overrides[get_postgrest_client] = lambda: FakePostgrestClient()

    response = client.get(f"/public/chatbots/{SHARE_TOKEN}")

    assert response.status_code == 200
    assert response.json() == {"name": "Support Bot", "purpose": "Answer FAQs"}


def test_get_public_chatbot_returns_404_for_unknown_token():
    app.dependency_overrides[get_postgrest_client] = lambda: FakePostgrestClient(chatbot_row=None)

    response = client.get("/public/chatbots/bad-token")

    assert response.status_code == 404


def test_get_public_chatbot_returns_404_not_500_for_malformed_token():
    """share_token is a uuid column -- Postgrest 400s on a non-uuid value
    instead of returning no rows. This unauthenticated route is reachable
    by anyone (bad links, bots probing paths), so it must 404, not 500."""
    app.dependency_overrides[get_postgrest_client] = lambda: FakePostgrestClient(
        raise_400_for_share_token="not-a-uuid"
    )

    response = client.get("/public/chatbots/not-a-uuid")

    assert response.status_code == 404


def test_public_chat_treats_malformed_session_id_as_no_session():
    postgrest = FakePostgrestClient(raise_400_for_session_id="not-a-uuid")
    app.dependency_overrides[get_postgrest_client] = lambda: postgrest
    app.dependency_overrides[get_powabase_client] = lambda: FakePowabaseClient()

    response = client.post(
        f"/public/chatbots/{SHARE_TOKEN}/chat",
        json={"message": "hi", "session_id": "not-a-uuid"},
    )

    assert response.status_code == 200
    assert response.json()["session_id"] == "sess-new"


def test_list_public_session_messages_returns_404_not_500_for_malformed_session_id():
    postgrest = FakePostgrestClient(raise_400_for_session_id="not-a-uuid")
    app.dependency_overrides[get_postgrest_client] = lambda: postgrest

    response = client.get(f"/public/chatbots/{SHARE_TOKEN}/chat/sessions/not-a-uuid/messages")

    assert response.status_code == 404


def test_public_chat_starts_new_session_using_service_role_key():
    postgrest = FakePostgrestClient()
    app.dependency_overrides[get_postgrest_client] = lambda: postgrest
    app.dependency_overrides[get_powabase_client] = lambda: FakePowabaseClient()

    response = client.post(
        f"/public/chatbots/{SHARE_TOKEN}/chat", json={"message": "hello"}
    )

    assert response.status_code == 200
    body = response.json()
    assert body == {
        "answer": "hi there",
        "sources": [],
        "session_id": "sess-new",
        "specialist_name": None,
    }

    message_inserts = [row for table, row, _ in postgrest.inserted_rows if table == "messages"]
    assert message_inserts == [
        {"session_id": "sess-new", "role": "user", "content": "hello"},
        {"session_id": "sess-new", "role": "assistant", "content": "hi there"},
    ]
    # Every postgrest call in the public path uses the service role key, not
    # a visitor JWT -- there isn't one.
    assert all(token == settings.powabase_api_key for _, _, token in postgrest.inserted_rows)


def test_public_chat_reuses_session_belonging_to_same_chatbot():
    postgrest = FakePostgrestClient(
        existing_sessions={
            "sess-1": {
                "id": "sess-1",
                "chatbot_id": "chatbot-1",
                "powabase_session_id": "powabase-sess-1",
            }
        }
    )
    app.dependency_overrides[get_postgrest_client] = lambda: postgrest
    app.dependency_overrides[get_powabase_client] = lambda: FakePowabaseClient()

    response = client.post(
        f"/public/chatbots/{SHARE_TOKEN}/chat",
        json={"message": "follow up", "session_id": "sess-1"},
    )

    assert response.status_code == 200
    assert response.json()["session_id"] == "sess-1"


def test_public_chat_ignores_session_id_belonging_to_a_different_chatbot():
    postgrest = FakePostgrestClient(
        existing_sessions={
            "sess-other": {
                "id": "sess-other",
                "chatbot_id": "some-other-chatbot",
                "powabase_session_id": "powabase-sess-other",
            }
        }
    )
    app.dependency_overrides[get_postgrest_client] = lambda: postgrest
    app.dependency_overrides[get_powabase_client] = lambda: FakePowabaseClient()

    response = client.post(
        f"/public/chatbots/{SHARE_TOKEN}/chat",
        json={"message": "hi", "session_id": "sess-other"},
    )

    assert response.status_code == 200
    # A foreign session id is not reused -- a brand new session is minted instead.
    assert response.json()["session_id"] == "sess-new"


def test_public_chat_returns_404_for_unknown_share_token():
    app.dependency_overrides[get_postgrest_client] = lambda: FakePostgrestClient(chatbot_row=None)
    app.dependency_overrides[get_powabase_client] = lambda: FakePowabaseClient()

    response = client.post("/public/chatbots/bad-token/chat", json={"message": "hi"})

    assert response.status_code == 404


def test_list_public_session_messages_returns_rows():
    postgrest = FakePostgrestClient(
        existing_sessions={"sess-1": {"id": "sess-1", "chatbot_id": "chatbot-1"}}
    )
    app.dependency_overrides[get_postgrest_client] = lambda: postgrest

    response = client.get(f"/public/chatbots/{SHARE_TOKEN}/chat/sessions/sess-1/messages")

    assert response.status_code == 200
    assert response.json() == [
        {"id": "m1", "role": "user", "content": "hi", "created_at": "2026-01-01T00:00:00Z"}
    ]


def test_public_chat_marks_new_session_as_public_origin():
    postgrest = FakePostgrestClient()
    app.dependency_overrides[get_postgrest_client] = lambda: postgrest
    app.dependency_overrides[get_powabase_client] = lambda: FakePowabaseClient()

    client.post(f"/public/chatbots/{SHARE_TOKEN}/chat", json={"message": "hello"})

    session_inserts = [row for table, row, _ in postgrest.inserted_rows if table == "chat_sessions"]
    assert session_inserts == [{"chatbot_id": "chatbot-1", "origin": "public"}]


def test_public_chat_marks_session_unread_on_visitor_message_and_updates_preview():
    postgrest = FakePostgrestClient()
    app.dependency_overrides[get_postgrest_client] = lambda: postgrest
    app.dependency_overrides[get_powabase_client] = lambda: FakePowabaseClient()

    client.post(f"/public/chatbots/{SHARE_TOKEN}/chat", json={"message": "hello there"})

    activity_updates = [
        values
        for table, filters, values, _ in postgrest.update_calls
        if table == "chat_sessions" and "last_message_preview" in values
    ]
    assert len(activity_updates) == 2
    # The visitor's message marks the session unread for the admin inbox...
    assert activity_updates[0]["unread"] is True
    assert activity_updates[0]["last_message_preview"] == "hello there"
    # ...while the assistant's reply just refreshes the preview, since the
    # admin still hasn't reviewed the exchange.
    assert "unread" not in activity_updates[1]
    assert activity_updates[1]["last_message_preview"] == "hi there"


def test_list_public_session_messages_returns_404_for_foreign_session():
    postgrest = FakePostgrestClient(
        existing_sessions={"sess-other": {"id": "sess-other", "chatbot_id": "some-other-chatbot"}}
    )
    app.dependency_overrides[get_postgrest_client] = lambda: postgrest

    response = client.get(f"/public/chatbots/{SHARE_TOKEN}/chat/sessions/sess-other/messages")

    assert response.status_code == 404
