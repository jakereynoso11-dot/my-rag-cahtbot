import pytest

from app.services.document_ingestion import (
    get_chatbot_agent_id,
    ingest_document_for_chatbot,
)
from app.services.ingest_service import ExtractionNotUsableError

USER_JWT = "user-jwt-token"
SERVICE_ROLE_KEY = "service-role-key"


class FakePostgrestClient:
    def __init__(self):
        self.rpc_calls = []
        self.select_calls = []
        self.update_calls = []
        self.register_or_get_document_result = None
        self.attach_document_to_chatbot_result = None
        self.select_one_result = None

    async def rpc(self, function_name, payload, *, access_token):
        self.rpc_calls.append((function_name, payload, access_token))
        if function_name == "register_or_get_document":
            return self.register_or_get_document_result
        if function_name == "attach_document_to_chatbot":
            return self.attach_document_to_chatbot_result
        raise AssertionError(f"unexpected rpc call: {function_name}")

    async def select_one(self, table, filters, columns, *, access_token):
        self.select_calls.append((table, filters, columns, access_token))
        return self.select_one_result

    async def update(self, table, filters, values, *, access_token):
        self.update_calls.append((table, filters, values, access_token))
        return [values]


class FakePowabaseClient:
    def __init__(self):
        self.create_kb_calls = []
        self.link_agent_calls = []
        self.create_kb_result = {"id": "kb-new"}
        self.upload_source_result = {"id": "src-1"}
        self.source_statuses = ["extracted"]
        self.add_source_result = {"id": "idx-1"}
        self.index_statuses = ["indexed"]
        self._source_call = 0
        self._index_call = 0

    async def create_knowledge_base(self, name):
        self.create_kb_calls.append(name)
        return self.create_kb_result

    async def upload_source(self, filename, content):
        return self.upload_source_result

    async def get_source(self, source_id):
        status = self.source_statuses[min(self._source_call, len(self.source_statuses) - 1)]
        self._source_call += 1
        return {"id": source_id, "extraction_status": status}

    async def add_source_to_kb(self, kb_id, source_id):
        return self.add_source_result

    async def list_kb_sources(self, kb_id):
        status = self.index_statuses[min(self._index_call, len(self.index_statuses) - 1)]
        self._index_call += 1
        return {"items": [{"id": "idx-1", "index_status": status}]}

    async def add_knowledge_base_to_agent(self, agent_id, kb_id):
        self.link_agent_calls.append((agent_id, kb_id))
        return {"id": "link-1"}


async def test_get_chatbot_agent_id_returns_agent_id():
    postgrest = FakePostgrestClient()
    postgrest.select_one_result = {"id": "cb-1", "powabase_agent_id": "agent-1"}

    result = await get_chatbot_agent_id("cb-1", USER_JWT, postgrest)

    assert result == "agent-1"
    assert postgrest.select_calls == [
        ("chatbots", {"id": "cb-1"}, "id,powabase_agent_id", USER_JWT)
    ]


async def test_get_chatbot_agent_id_returns_none_when_not_found():
    postgrest = FakePostgrestClient()
    postgrest.select_one_result = None

    result = await get_chatbot_agent_id("cb-missing", USER_JWT, postgrest)

    assert result is None


async def test_ingest_new_document_creates_kb_and_indexes():
    postgrest = FakePostgrestClient()
    postgrest.register_or_get_document_result = [
        {
            "id": "doc-1",
            "is_new": True,
            "index_status": "pending",
            "powabase_source_id": None,
            "powabase_knowledge_base_id": None,
        }
    ]
    postgrest.attach_document_to_chatbot_result = {"id": "cd-1"}
    powabase = FakePowabaseClient()

    result = await ingest_document_for_chatbot(
        content=b"fake bytes",
        filename="doc.pdf",
        mime_type="application/pdf",
        chatbot_id="cb-1",
        agent_id="agent-1",
        access_token=USER_JWT,
        service_role_key=SERVICE_ROLE_KEY,
        postgrest=postgrest,
        powabase=powabase,
    )

    assert result.document_id == "doc-1"
    assert result.is_new is True
    assert result.index_status == "indexed"
    assert result.chatbot_document_id == "cd-1"

    assert len(powabase.create_kb_calls) == 1
    assert powabase.create_kb_calls[0].startswith("doc-")
    assert powabase.link_agent_calls == [("agent-1", "kb-new")]

    update_table, update_filters, update_values, update_token = postgrest.update_calls[0]
    assert update_table == "documents"
    assert update_filters == {"id": "doc-1"}
    assert update_values == {
        "powabase_source_id": "src-1",
        "powabase_knowledge_base_id": "kb-new",
        "index_status": "indexed",
    }
    assert update_token == SERVICE_ROLE_KEY

    register_call = postgrest.rpc_calls[0]
    assert register_call[0] == "register_or_get_document"
    assert register_call[2] == USER_JWT

    attach_call = postgrest.rpc_calls[1]
    assert attach_call[0] == "attach_document_to_chatbot"
    assert attach_call[1] == {
        "p_document_id": "doc-1",
        "p_chatbot_id": "cb-1",
        "p_display_name": "doc.pdf",
    }
    assert attach_call[2] == USER_JWT


async def test_ingest_existing_indexed_document_skips_reingest():
    postgrest = FakePostgrestClient()
    postgrest.register_or_get_document_result = [
        {
            "id": "doc-1",
            "is_new": False,
            "index_status": "indexed",
            "powabase_source_id": "src-existing",
            "powabase_knowledge_base_id": "kb-existing",
        }
    ]
    postgrest.attach_document_to_chatbot_result = {"id": "cd-2"}
    powabase = FakePowabaseClient()

    result = await ingest_document_for_chatbot(
        content=b"fake bytes",
        filename="doc.pdf",
        mime_type="application/pdf",
        chatbot_id="cb-2",
        agent_id="agent-2",
        access_token=USER_JWT,
        service_role_key=SERVICE_ROLE_KEY,
        postgrest=postgrest,
        powabase=powabase,
    )

    assert result.document_id == "doc-1"
    assert result.is_new is False
    assert result.index_status == "indexed"
    assert result.chatbot_document_id == "cd-2"

    assert powabase.create_kb_calls == []
    assert postgrest.update_calls == []
    assert powabase.link_agent_calls == [("agent-2", "kb-existing")]


async def test_ingest_raises_and_records_extraction_not_usable():
    postgrest = FakePostgrestClient()
    postgrest.register_or_get_document_result = [
        {
            "id": "doc-1",
            "is_new": True,
            "index_status": "pending",
            "powabase_source_id": None,
            "powabase_knowledge_base_id": None,
        }
    ]
    powabase = FakePowabaseClient()
    powabase.source_statuses = ["attention_required"]

    with pytest.raises(ExtractionNotUsableError):
        await ingest_document_for_chatbot(
            content=b"fake bytes",
            filename="doc.pdf",
            mime_type="application/pdf",
            chatbot_id="cb-1",
            agent_id="agent-1",
            access_token=USER_JWT,
            service_role_key=SERVICE_ROLE_KEY,
            postgrest=postgrest,
            powabase=powabase,
        )

    update_table, update_filters, update_values, update_token = postgrest.update_calls[0]
    assert update_table == "documents"
    assert update_filters == {"id": "doc-1"}
    assert update_values["index_status"] == "failed"
    assert update_values["powabase_source_id"] == "src-1"
    assert update_token == SERVICE_ROLE_KEY

    # Extraction failed before attach/link ever happen.
    assert not any(call[0] == "attach_document_to_chatbot" for call in postgrest.rpc_calls)
    assert powabase.link_agent_calls == []
