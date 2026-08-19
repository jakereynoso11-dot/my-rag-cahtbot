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
        self.update_calls = []
        self.delete_calls = []
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

    async def select_one(self, table, filters, columns, *, access_token):
        if table == "chatbots":
            return self.chatbot_row
        if table == "chatbot_specialists":
            return self.specialist_row
        raise AssertionError(f"unexpected select_one on {table}")

    async def rpc(self, function_name, payload, *, access_token):
        return self.rpc_results[function_name]

    async def update(self, table, filters, values, *, access_token):
        self.update_calls.append((table, filters, values))
        if self.specialist_row is None:
            return []
        self.specialist_row = {**self.specialist_row, **values}
        return [self.specialist_row]

    async def select(self, table, columns, *, filters=None, order=None, access_token):
        if table == "chatbot_specialists":
            return self.list_rows
        if table == "chatbot_documents":
            return self.kb_rows
        if table == "specialist_documents":
            return self.list_rows
        raise AssertionError(f"unexpected select on {table}")

    async def insert(self, table, values, *, access_token):
        self.insert_calls.append((table, values))
        if table == "chatbot_specialists":
            self.specialist_row = {
                "id": "specialist-new",
                "created_at": "2026-01-01T00:00:00Z",
                **values,
            }
            return self.specialist_row
        return {"id": "specialist-doc-1", **values}

    async def delete(self, table, filters, *, access_token):
        self.delete_calls.append((table, filters))
        return self.delete_result


class FakePowabaseClient:
    def __init__(self):
        self.create_agent_calls = []
        self.delete_agent_calls = []
        self.link_agent_calls = []
        self.update_agent_calls = []

    async def create_agent(self, name, system_prompt):
        self.create_agent_calls.append((name, system_prompt))
        return {"id": "specialist-agent-new"}

    async def add_knowledge_base_to_agent(self, agent_id, kb_id):
        self.link_agent_calls.append((agent_id, kb_id))
        return {"id": "link-1"}

    async def delete_agent(self, agent_id):
        self.delete_agent_calls.append(agent_id)

    async def update_agent(self, agent_id, *, name=None, system_prompt=None):
        self.update_agent_calls.append((agent_id, name, system_prompt))
        return {"id": agent_id}

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


def test_update_specialist_renames_and_updates_specialty():
    postgrest = FakePostgrestClient(
        specialist_row={
            "id": "spec-1",
            "name": "Billing Agent",
            "specialty": "billing",
            "created_at": "2026-01-01T00:00:00Z",
            "powabase_agent_id": "specialist-agent-1",
        }
    )
    powabase = FakePowabaseClient()
    override(postgrest=postgrest, powabase=powabase)

    response = client.patch(
        "/chatbots/chatbot-1/specialists/spec-1",
        json={"name": "New Name", "specialty": "invoicing"},
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 200
    assert response.json()["name"] == "New Name"
    assert response.json()["specialty"] == "invoicing"
    assert powabase.update_agent_calls == []


def test_update_specialist_updates_instructions():
    postgrest = FakePostgrestClient(
        specialist_row={
            "id": "spec-1",
            "name": "Billing Agent",
            "specialty": "billing",
            "created_at": "2026-01-01T00:00:00Z",
            "powabase_agent_id": "specialist-agent-1",
        }
    )
    powabase = FakePowabaseClient()
    override(postgrest=postgrest, powabase=powabase)

    response = client.patch(
        "/chatbots/chatbot-1/specialists/spec-1",
        json={"system_prompt": "Always mention the refund window."},
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 200
    assert len(powabase.update_agent_calls) == 1
    assert "refund window" in powabase.update_agent_calls[0][2]


def test_update_specialist_returns_404_when_missing():
    postgrest = FakePostgrestClient(specialist_row=None)
    powabase = FakePowabaseClient()
    override(postgrest=postgrest, powabase=powabase)

    response = client.patch(
        "/chatbots/chatbot-1/specialists/spec-missing",
        json={"name": "New Name"},
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 404


def test_update_specialist_returns_404_when_chatbot_not_owned():
    postgrest = FakePostgrestClient(chatbot_row=None)
    powabase = FakePowabaseClient()
    override(postgrest=postgrest, powabase=powabase)

    response = client.patch(
        "/chatbots/not-mine/specialists/spec-1",
        json={"name": "New Name"},
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


def test_upload_specialist_document_links_only_that_specialist():
    postgrest = FakePostgrestClient(
        specialist_row={"id": "spec-1", "powabase_agent_id": "agent-billing"}
    )
    powabase = FakePowabaseClient()
    override(postgrest=postgrest, powabase=powabase)

    response = client.post(
        "/chatbots/chatbot-1/specialists/spec-1/documents",
        files={"file": ("invoice-policy.pdf", b"%PDF-1.4 fake", "application/pdf")},
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "document_id": "doc-1",
        "is_new": True,
        "index_status": "indexed",
        "specialist_document_id": "specialist-doc-1",
    }
    assert powabase.link_agent_calls == [("agent-billing", "kb-new")]


def test_upload_specialist_document_returns_404_when_specialist_missing():
    postgrest = FakePostgrestClient(specialist_row=None)
    powabase = FakePowabaseClient()
    override(postgrest=postgrest, powabase=powabase)

    response = client.post(
        "/chatbots/chatbot-1/specialists/spec-missing/documents",
        files={"file": ("invoice-policy.pdf", b"%PDF-1.4 fake", "application/pdf")},
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 404


def test_upload_specialist_document_returns_404_when_chatbot_not_owned():
    postgrest = FakePostgrestClient(chatbot_row=None)
    powabase = FakePowabaseClient()
    override(postgrest=postgrest, powabase=powabase)

    response = client.post(
        "/chatbots/not-mine/specialists/spec-1/documents",
        files={"file": ("invoice-policy.pdf", b"%PDF-1.4 fake", "application/pdf")},
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 404


def test_list_specialist_documents_returns_rows():
    postgrest = FakePostgrestClient(
        list_rows=[
            {
                "id": "sd-1",
                "display_name": "invoice-policy.pdf",
                "created_at": "2026-01-01T00:00:00Z",
                "documents": {"index_status": "indexed", "original_filename": "invoice-policy.pdf"},
            }
        ]
    )
    override(postgrest=postgrest)

    response = client.get(
        "/chatbots/chatbot-1/specialists/spec-1/documents",
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 200
    assert response.json()[0]["display_name"] == "invoice-policy.pdf"


def test_specialists_require_auth():
    response = client.get("/chatbots/chatbot-1/specialists")

    assert response.status_code == 401
