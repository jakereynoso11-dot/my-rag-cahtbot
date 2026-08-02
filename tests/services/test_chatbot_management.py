import httpx
import pytest

from app.services.chatbot_management import (
    ChatbotNotFoundError,
    create_chatbot,
    delete_chatbot,
    get_owned_chatbot,
    list_chatbots,
    rename_chatbot,
)
from app.services.chatbot_provisioning import SYSTEM_PROMPT

TOKEN = "user-jwt-token"


class FakePostgrestClient:
    def __init__(self, chatbot_row=None, list_rows=None):
        self.chatbot_row = chatbot_row
        self.list_rows = list_rows or []
        self.select_calls = []
        self.insert_calls = []
        self.update_calls = []
        self.delete_calls = []

    async def select(self, table, columns, *, filters=None, order=None, access_token):
        self.select_calls.append((table, columns, filters, order, access_token))
        return self.list_rows

    async def select_one(self, table, filters, columns, *, access_token):
        return self.chatbot_row

    async def insert(self, table, values, *, access_token):
        self.insert_calls.append((table, values, access_token))
        return {"id": "chatbot-new", **values}

    async def update(self, table, filters, values, *, access_token):
        self.update_calls.append((table, filters, values, access_token))
        if self.chatbot_row is None:
            return []
        return [{**self.chatbot_row, **values}]

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


async def test_list_chatbots_scopes_to_owner():
    postgrest = FakePostgrestClient(
        list_rows=[{"id": "cb-1", "name": "Tax Docs Helper", "created_at": "2026-01-01T00:00:00Z"}]
    )

    result = await list_chatbots("user-1", TOKEN, postgrest)

    assert result == [
        {"id": "cb-1", "name": "Tax Docs Helper", "created_at": "2026-01-01T00:00:00Z"}
    ]
    table, columns, filters, order, access_token = postgrest.select_calls[0]
    assert table == "chatbots"
    assert filters == {"owner_id": "user-1"}
    assert access_token == TOKEN


async def test_create_chatbot_uses_custom_system_prompt():
    postgrest = FakePostgrestClient()
    powabase = FakePowabaseClient()

    result = await create_chatbot(
        "user-1", "Tax Docs Helper", "You're a tax assistant.", TOKEN, postgrest, powabase
    )

    assert result.id == "chatbot-new"
    assert result.agent_id == "agent-new"
    assert powabase.create_agent_calls == [("Tax Docs Helper", "You're a tax assistant.")]
    assert postgrest.insert_calls == [
        (
            "chatbots",
            {"owner_id": "user-1", "name": "Tax Docs Helper", "powabase_agent_id": "agent-new"},
            TOKEN,
        )
    ]


async def test_create_chatbot_falls_back_to_default_system_prompt():
    postgrest = FakePostgrestClient()
    powabase = FakePowabaseClient()

    await create_chatbot("user-1", "Recipe Box", None, TOKEN, postgrest, powabase)

    assert powabase.create_agent_calls == [("Recipe Box", SYSTEM_PROMPT)]


async def test_get_owned_chatbot_returns_chatbot():
    postgrest = FakePostgrestClient(chatbot_row={"id": "cb-1", "powabase_agent_id": "agent-1"})

    result = await get_owned_chatbot("cb-1", TOKEN, postgrest)

    assert result.id == "cb-1"
    assert result.agent_id == "agent-1"


async def test_get_owned_chatbot_raises_when_missing_or_not_owned():
    postgrest = FakePostgrestClient(chatbot_row=None)

    with pytest.raises(ChatbotNotFoundError):
        await get_owned_chatbot("cb-missing", TOKEN, postgrest)


async def test_rename_chatbot_updates_name():
    postgrest = FakePostgrestClient(chatbot_row={"id": "cb-1", "name": "old"})

    result = await rename_chatbot("cb-1", "new name", TOKEN, postgrest)

    assert result["name"] == "new name"
    assert postgrest.update_calls == [
        ("chatbots", {"id": "cb-1"}, {"name": "new name"}, TOKEN)
    ]


async def test_rename_chatbot_raises_when_missing_or_not_owned():
    postgrest = FakePostgrestClient(chatbot_row=None)

    with pytest.raises(ChatbotNotFoundError):
        await rename_chatbot("cb-missing", "new name", TOKEN, postgrest)


async def test_delete_chatbot_removes_row_and_agent():
    postgrest = FakePostgrestClient(chatbot_row={"id": "cb-1", "powabase_agent_id": "agent-1"})
    powabase = FakePowabaseClient()

    await delete_chatbot("cb-1", TOKEN, postgrest, powabase)

    assert postgrest.delete_calls == [("chatbots", {"id": "cb-1"}, TOKEN)]
    assert powabase.delete_agent_calls == ["agent-1"]


async def test_delete_chatbot_raises_when_missing_or_not_owned():
    postgrest = FakePostgrestClient(chatbot_row=None)
    powabase = FakePowabaseClient()

    with pytest.raises(ChatbotNotFoundError):
        await delete_chatbot("cb-missing", TOKEN, postgrest, powabase)

    assert postgrest.delete_calls == []
    assert powabase.delete_agent_calls == []


async def test_delete_chatbot_succeeds_even_if_agent_deletion_fails():
    postgrest = FakePostgrestClient(chatbot_row={"id": "cb-1", "powabase_agent_id": "agent-1"})

    class FailingPowabaseClient(FakePowabaseClient):
        async def delete_agent(self, agent_id):
            raise httpx.HTTPStatusError(
                "boom",
                request=httpx.Request("DELETE", "https://x/api/agents/agent-1"),
                response=httpx.Response(404, request=httpx.Request("DELETE", "https://x")),
            )

    await delete_chatbot("cb-1", TOKEN, postgrest, FailingPowabaseClient())

    assert postgrest.delete_calls == [("chatbots", {"id": "cb-1"}, TOKEN)]
