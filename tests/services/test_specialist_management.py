import httpx
import pytest

from app.services.specialist_management import (
    SpecialistNotFoundError,
    create_specialist,
    delete_specialist,
    get_owned_specialist,
    list_specialists,
)

TOKEN = "user-jwt-token"


class FakePostgrestClient:
    def __init__(self, specialist_row=None, list_rows=None, kb_rows=None):
        self.specialist_row = specialist_row
        self.list_rows = list_rows or []
        self.kb_rows = kb_rows or []
        self.select_calls = []
        self.insert_calls = []
        self.delete_calls = []

    async def select(self, table, columns, *, filters=None, order=None, access_token):
        self.select_calls.append((table, columns, filters, order))
        if table == "chatbot_specialists":
            return self.list_rows
        if table == "chatbot_documents":
            return self.kb_rows
        raise AssertionError(f"unexpected select on {table}")

    async def select_one(self, table, filters, columns, *, access_token):
        return self.specialist_row

    async def insert(self, table, values, *, access_token):
        self.insert_calls.append((table, values))
        return {"id": "specialist-new", **values}

    async def delete(self, table, filters, *, access_token):
        self.delete_calls.append((table, filters))
        if self.specialist_row is None:
            return []
        return [self.specialist_row]


class FakePowabaseClient:
    def __init__(self):
        self.create_agent_calls = []
        self.link_calls = []
        self.delete_agent_calls = []

    async def create_agent(self, name, system_prompt):
        self.create_agent_calls.append((name, system_prompt))
        return {"id": "specialist-agent-new"}

    async def add_knowledge_base_to_agent(self, agent_id, kb_id):
        self.link_calls.append((agent_id, kb_id))
        return {"id": "link-1"}

    async def delete_agent(self, agent_id):
        self.delete_agent_calls.append(agent_id)


async def test_list_specialists_scopes_to_chatbot():
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

    result = await list_specialists("cb-1", TOKEN, postgrest)

    assert result[0]["name"] == "Billing Agent"
    table, columns, filters, order = postgrest.select_calls[0]
    assert table == "chatbot_specialists"
    assert filters == {"chatbot_id": "cb-1"}


async def test_create_specialist_shares_existing_documents():
    postgrest = FakePostgrestClient(
        kb_rows=[
            {"documents": {"powabase_knowledge_base_id": "kb-1"}},
            {"documents": {"powabase_knowledge_base_id": "kb-2"}},
        ]
    )
    powabase = FakePowabaseClient()

    result = await create_specialist(
        "cb-1", "Billing Agent", "billing questions", None, TOKEN, postgrest, powabase
    )

    assert result.id == "specialist-new"
    assert result.agent_id == "specialist-agent-new"
    assert powabase.create_agent_calls[0][0] == "Billing Agent"
    assert "billing questions" in powabase.create_agent_calls[0][1]
    assert sorted(powabase.link_calls) == [
        ("specialist-agent-new", "kb-1"),
        ("specialist-agent-new", "kb-2"),
    ]
    assert postgrest.insert_calls == [
        (
            "chatbot_specialists",
            {
                "chatbot_id": "cb-1",
                "name": "Billing Agent",
                "specialty": "billing questions",
                "powabase_agent_id": "specialist-agent-new",
            },
        )
    ]


async def test_create_specialist_includes_custom_instructions_in_prompt():
    postgrest = FakePostgrestClient()
    powabase = FakePowabaseClient()

    await create_specialist(
        "cb-1",
        "Billing Agent",
        "billing questions",
        "Always mention our refund policy.",
        TOKEN,
        postgrest,
        powabase,
    )

    prompt = powabase.create_agent_calls[0][1]
    assert "billing questions" in prompt
    assert "Always mention our refund policy." in prompt


async def test_delete_specialist_removes_row_and_agent():
    postgrest = FakePostgrestClient(
        specialist_row={"id": "spec-1", "powabase_agent_id": "specialist-agent-1"}
    )
    powabase = FakePowabaseClient()

    await delete_specialist("spec-1", "cb-1", TOKEN, postgrest, powabase)

    assert postgrest.delete_calls == [("chatbot_specialists", {"id": "spec-1"})]
    assert powabase.delete_agent_calls == ["specialist-agent-1"]


async def test_delete_specialist_raises_when_missing_or_not_owned():
    postgrest = FakePostgrestClient(specialist_row=None)
    powabase = FakePowabaseClient()

    with pytest.raises(SpecialistNotFoundError):
        await delete_specialist("spec-missing", "cb-1", TOKEN, postgrest, powabase)

    assert postgrest.delete_calls == []


async def test_get_owned_specialist_returns_row():
    postgrest = FakePostgrestClient(
        specialist_row={
            "id": "spec-1",
            "name": "Billing Agent",
            "powabase_agent_id": "specialist-agent-1",
        }
    )

    result = await get_owned_specialist("cb-1", "spec-1", TOKEN, postgrest)

    assert result["powabase_agent_id"] == "specialist-agent-1"


async def test_get_owned_specialist_raises_when_missing_or_not_owned():
    postgrest = FakePostgrestClient(specialist_row=None)

    with pytest.raises(SpecialistNotFoundError):
        await get_owned_specialist("cb-1", "spec-missing", TOKEN, postgrest)


async def test_delete_specialist_succeeds_even_if_agent_deletion_fails():
    postgrest = FakePostgrestClient(
        specialist_row={"id": "spec-1", "powabase_agent_id": "specialist-agent-1"}
    )

    class FailingPowabaseClient(FakePowabaseClient):
        async def delete_agent(self, agent_id):
            raise httpx.HTTPStatusError(
                "boom",
                request=httpx.Request("DELETE", "https://x/api/agents/specialist-agent-1"),
                response=httpx.Response(404, request=httpx.Request("DELETE", "https://x")),
            )

    await delete_specialist("spec-1", "cb-1", TOKEN, postgrest, FailingPowabaseClient())

    assert postgrest.delete_calls == [("chatbot_specialists", {"id": "spec-1"})]
