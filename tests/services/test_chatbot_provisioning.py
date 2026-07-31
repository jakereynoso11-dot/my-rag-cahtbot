from app.services.chatbot_provisioning import (
    SYSTEM_PROMPT,
    Chatbot,
    get_or_create_chatbot,
    recreate_agent_for_chatbot,
)


class FakePostgrestClient:
    def __init__(self, existing=None, chatbot_documents=None):
        self.existing = existing
        self.insert_calls = []
        self.update_calls = []
        self.chatbot_documents = chatbot_documents or []

    async def select_one(self, table, filters, columns, *, access_token):
        return self.existing

    async def select(self, table, columns, *, filters=None, order=None, access_token):
        if table == "chatbot_documents":
            return self.chatbot_documents
        raise AssertionError(f"unexpected select on {table}")

    async def insert(self, table, values, *, access_token):
        self.insert_calls.append((table, values, access_token))
        return {"id": "chatbot-new", **values}

    async def update(self, table, filters, values, *, access_token):
        self.update_calls.append((table, filters, values, access_token))
        return [values]


class FakePowabaseClient:
    def __init__(self):
        self.create_agent_calls = []
        self.link_agent_calls = []

    async def create_agent(self, name, system_prompt):
        self.create_agent_calls.append((name, system_prompt))
        return {"id": "agent-new"}

    async def add_knowledge_base_to_agent(self, agent_id, kb_id):
        self.link_agent_calls.append((agent_id, kb_id))
        return {"id": "link-1"}


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


async def test_recreate_agent_relinks_existing_document_knowledge_bases():
    chatbot = Chatbot(id="chatbot-1", agent_id="agent-deleted")
    postgrest = FakePostgrestClient(
        chatbot_documents=[
            {"documents": {"powabase_knowledge_base_id": "kb-1"}},
            {"documents": {"powabase_knowledge_base_id": "kb-2"}},
            {"documents": {"powabase_knowledge_base_id": None}},
        ]
    )
    powabase = FakePowabaseClient()

    result = await recreate_agent_for_chatbot(chatbot, "user-1", "token", postgrest, powabase)

    assert result.id == "chatbot-1"
    assert result.agent_id == "agent-new"
    assert powabase.create_agent_calls == [("user-user-1-agent", SYSTEM_PROMPT)]
    assert set(powabase.link_agent_calls) == {("agent-new", "kb-1"), ("agent-new", "kb-2")}
    assert postgrest.update_calls == [
        ("chatbots", {"id": "chatbot-1"}, {"powabase_agent_id": "agent-new"}, "token")
    ]


async def test_recreate_agent_with_no_documents_skips_relinking():
    chatbot = Chatbot(id="chatbot-1", agent_id="agent-deleted")
    postgrest = FakePostgrestClient(chatbot_documents=[])
    powabase = FakePowabaseClient()

    result = await recreate_agent_for_chatbot(chatbot, "user-1", "token", postgrest, powabase)

    assert result.agent_id == "agent-new"
    assert powabase.link_agent_calls == []
