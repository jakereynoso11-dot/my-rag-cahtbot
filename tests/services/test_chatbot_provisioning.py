from app.services.chatbot_provisioning import get_or_create_chatbot


class FakePostgrestClient:
    def __init__(self, existing=None):
        self.existing = existing
        self.insert_calls = []

    async def select_one(self, table, filters, columns, *, access_token):
        return self.existing

    async def insert(self, table, values, *, access_token):
        self.insert_calls.append((table, values, access_token))
        return {"id": "chatbot-new", **values}


class FakePowabaseClient:
    def __init__(self):
        self.create_agent_calls = []

    async def create_agent(self, name, system_prompt):
        self.create_agent_calls.append((name, system_prompt))
        return {"id": "agent-new"}


async def test_returns_existing_chatbot_without_creating():
    postgrest = FakePostgrestClient(existing={"id": "chatbot-1", "powabase_agent_id": "agent-1"})
    powabase = FakePowabaseClient()

    result = await get_or_create_chatbot("user-1", "token", postgrest, powabase)

    assert result.id == "chatbot-1"
    assert result.agent_id == "agent-1"
    assert powabase.create_agent_calls == []


async def test_creates_chatbot_and_agent_when_none_exists():
    postgrest = FakePostgrestClient(existing=None)
    powabase = FakePowabaseClient()

    result = await get_or_create_chatbot("user-1", "token", postgrest, powabase)

    assert result.id == "chatbot-new"
    assert result.agent_id == "agent-new"
    assert postgrest.insert_calls == [
        (
            "chatbots",
            {"owner_id": "user-1", "name": "My Assistant", "powabase_agent_id": "agent-new"},
            "token",
        )
    ]
