import pytest

from app.services.chat_service import ChatRunFailedError, ChatService


class FakePowabaseClient:
    def __init__(self, lines):
        self._lines = lines
        self.last_call = None

    async def stream_agent_run(self, agent_id, message, session_id=None, temperature=None):
        self.last_call = {
            "agent_id": agent_id,
            "message": message,
            "session_id": session_id,
            "temperature": temperature,
        }
        for line in self._lines:
            yield line


async def test_get_answer_returns_content_from_complete_event():
    client = FakePowabaseClient(
        lines=[
            'data: {"event": "start", "session_id": "s1"}',
            'data: {"event": "complete", "status": "completed", "content": "hi there"}',
        ]
    )
    service = ChatService(client=client, agent_id="agent-1")

    result = await service.get_answer("hello")

    assert result.answer == "hi there"
    assert result.sources == []
    assert result.powabase_session_id == "s1"


async def test_get_answer_passes_query_session_and_temperature_through():
    client = FakePowabaseClient(
        lines=['data: {"event": "complete", "status": "completed", "content": ""}']
    )
    service = ChatService(client=client, agent_id="agent-1")

    await service.get_answer("hello", session_id="s1", temperature=0.2)

    assert client.last_call == {
        "agent_id": "agent-1",
        "message": "hello",
        "session_id": "s1",
        "temperature": 0.2,
    }


async def test_get_answer_raises_on_error_event():
    client = FakePowabaseClient(lines=['data: {"event": "error", "message": "boom"}'])
    service = ChatService(client=client, agent_id="agent-1")

    with pytest.raises(ChatRunFailedError, match="boom"):
        await service.get_answer("hello")


async def test_get_answer_raises_when_run_status_is_failed():
    client = FakePowabaseClient(
        lines=['data: {"event": "complete", "status": "failed", "error": "model error"}']
    )
    service = ChatService(client=client, agent_id="agent-1")

    with pytest.raises(ChatRunFailedError, match="model error"):
        await service.get_answer("hello")
