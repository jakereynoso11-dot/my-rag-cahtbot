import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_chat_service
from app.main import app

client = TestClient(app)


class FakeChatService:
    def __init__(self, chunks):
        self._chunks = chunks
        self.last_call = None

    async def stream_answer(self, query, session_id=None, temperature=None):
        self.last_call = {"query": query, "session_id": session_id, "temperature": temperature}
        for chunk in self._chunks:
            yield chunk


@pytest.fixture(autouse=True)
def clear_overrides():
    yield
    app.dependency_overrides.pop(get_chat_service, None)


def test_chat_streams_sse_chunks_through():
    service = FakeChatService(
        chunks=[
            'data: {"event": "start", "session_id": "s1"}\n\n',
            'data: {"event": "complete", "content": "hi"}\n\n',
        ]
    )
    app.dependency_overrides[get_chat_service] = lambda: service

    response = client.post("/chat", json={"message": "hello"})

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert response.text == (
        'data: {"event": "start", "session_id": "s1"}\n\n'
        'data: {"event": "complete", "content": "hi"}\n\n'
    )


def test_chat_passes_session_id_and_temperature_through():
    service = FakeChatService(chunks=[])
    app.dependency_overrides[get_chat_service] = lambda: service

    client.post("/chat", json={"message": "hello", "session_id": "s1", "temperature": 0.2})

    assert service.last_call == {"query": "hello", "session_id": "s1", "temperature": 0.2}


def test_chat_rejects_empty_query():
    response = client.post("/chat", json={"message": ""})

    assert response.status_code == 422
