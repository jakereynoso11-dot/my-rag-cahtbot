from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.deps import get_current_user, get_postgrest_client, get_powabase_client
from app.api.routes.specialists import router as specialists_router

app = FastAPI()
app.include_router(specialists_router)
client = TestClient(app)

_DEFAULT_CHATBOT_ROW = object()


class FakePostgrestClient:
    def __init__(
        self,
        chatbot_row=_DEFAULT_CHATBOT_ROW,
        list_rows=None,
        specialist_row=None,
        kb_rows=None,
        delete_result=None,
    ):
        self.chatbot_row = (
            {"id": "chatbot-1", "powabase_agent_id": "agent-1"}
            if chatbot_row is _DEFAULT_CHATBOT_ROW
            else chatbot_row
        )
        self.list_rows = list_rows or []
        self.specialist_row = specialist_row
        self.kb_rows = kb_rows or []
        self.delete_result = delete_result if delete_result is not None else (
            [self.specialist_row] if self.specialist_row else []
        )
        self.insert_calls = []
        self.delete_calls = []

    async def select_one(self, table, filters, columns, *, access_token):
        if table == "chatbots":
            return self.chatbot_row
        if table == "chatbot_specialists":
            return self.specialist_row
        raise AssertionError(f"unexpected select_one on {table}")

    async def select(self, table, columns, *, filters=None, order=None, access_token):
        if table == "chatbot_specialists":
            return self.list_rows
        if table == "chatbot_documents":
            return self.kb_rows
        raise AssertionError(f"unexpected select on {table}")

    async def insert(self, table, values, *, access_token):
        self.insert_calls.append((table, values))
        self.specialist_row = {
            "id": "specialist-new",
            "created_at": "2026-01-01T00:00:00Z",
            **values,
        }
        return self.specialist_row

    async def delete(self, table, filters, *, access_token):
        self.delete_calls.append((table, filters))
        return self.delete_result


class FakePowabaseClient:
    def __init__(self):
        self.create_agent_calls = []
        self.delete_agent_calls = []

    async def create_agent(self, name, system_prompt):
        self.create_agent_calls.append((name, system_prompt))
        return {"id": "specialist-agent-new"}

    async def add_knowledge_base_to_agent(self, agent_id, kb_id):
        return {"id": "link-1"}

    async def delete_agent(self, agent_id):
        self.delete_agent_calls.append(agent_id)


def override(postgrest=None, powabase=None):
    app.dependency_overrides[get_current_user] = lambda: {"id": "user-1"}
    if postgrest is not None:
        app.dependency_overrides[get_postgrest_client] = lambda: postgrest
    if powabase is not None:
        app.dependency_overrides[get_powabase_client] = lambda: powabase


def teardown_function():
    app.dependency_overrides.clear()


def test_list_specialists_returns_rows_for_owned_chatbot():
    postgrest = FakePostgrestClient(
        list_rows=[
            {
                "id": "spec-1",
                "name": "Billing Agent",
                "specialty": "billing",
                "created_at": "2026-01-01T00:00:00Z",
            }
        ]
    )
    override(postgrest=postgrest)

    response = client.get(
        "/chatbots/chatbot-1/specialists", headers={"Authorization": "Bearer test-token"}
    )

    assert response.status_code == 200
    assert response.json()[0]["name"] == "Billing Agent"


def test_list_specialists_returns_404_when_chatbot_not_owned():
    postgrest = FakePostgrestClient(chatbot_row=None)
    override(postgrest=postgrest)

    response = client.get(
        "/chatbots/not-mine/specialists", headers={"Authorization": "Bearer test-token"}
    )

    assert response.status_code == 404


def test_create_specialist_returns_new_row():
    postgrest = FakePostgrestClient()
    powabase = FakePowabaseClient()
    override(postgrest=postgrest, powabase=powabase)

    response = client.post(
        "/chatbots/chatbot-1/specialists",
        json={"name": "Billing Agent", "specialty": "billing questions"},
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 200
    assert response.json()["name"] == "Billing Agent"
    assert response.json()["specialty"] == "billing questions"
    assert powabase.create_agent_calls[0][0] == "Billing Agent"
    assert postgrest.insert_calls[0][1]["chatbot_id"] == "chatbot-1"


def test_create_specialist_returns_404_when_chatbot_not_owned():
    postgrest = FakePostgrestClient(chatbot_row=None)
    powabase = FakePowabaseClient()
    override(postgrest=postgrest, powabase=powabase)

    response = client.post(
        "/chatbots/not-mine/specialists",
        json={"name": "Billing Agent", "specialty": "billing questions"},
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 404


def test_delete_specialist_succeeds():
    postgrest = FakePostgrestClient(
        specialist_row={"id": "spec-1", "powabase_agent_id": "specialist-agent-1"}
    )
    powabase = FakePowabaseClient()
    override(postgrest=postgrest, powabase=powabase)

    response = client.delete(
        "/chatbots/chatbot-1/specialists/spec-1",
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 204
    assert powabase.delete_agent_calls == ["specialist-agent-1"]


def test_delete_specialist_returns_404_when_missing():
    postgrest = FakePostgrestClient(specialist_row=None, delete_result=[])
    powabase = FakePowabaseClient()
    override(postgrest=postgrest, powabase=powabase)

    response = client.delete(
        "/chatbots/chatbot-1/specialists/spec-missing",
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 404


def test_specialists_require_auth():
    response = client.get("/chatbots/chatbot-1/specialists")

    assert response.status_code == 401
