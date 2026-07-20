from app.services.chat_service import ChatService


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


async def test_stream_answer_frames_each_line_as_sse():
    client = FakePowabaseClient(
        lines=[
            'data: {"event": "start", "session_id": "s1"}',
            'data: {"event": "complete", "content": "hi"}',
        ]
    )
    service = ChatService(client=client, agent_id="agent-1")

    chunks = [chunk async for chunk in service.stream_answer("hello")]

    assert chunks == [
        'data: {"event": "start", "session_id": "s1"}\n\n',
        'data: {"event": "complete", "content": "hi"}\n\n',
    ]


async def test_stream_answer_passes_query_session_and_temperature_through():
    client = FakePowabaseClient(lines=[])
    service = ChatService(client=client, agent_id="agent-1")

    [_ async for _ in service.stream_answer("hello", session_id="s1", temperature=0.2)]

    assert client.last_call == {
        "agent_id": "agent-1",
        "message": "hello",
        "session_id": "s1",
        "temperature": 0.2,
    }


async def test_stream_answer_forwards_error_events():
    client = FakePowabaseClient(lines=['data: {"event": "error", "message": "boom"}'])
    service = ChatService(client=client, agent_id="agent-1")

    chunks = [chunk async for chunk in service.stream_answer("hello")]

    assert chunks == ['data: {"event": "error", "message": "boom"}\n\n']
