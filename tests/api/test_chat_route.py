import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_chat_service
from app.main import app
from app.services.chat_service import ChatAnswer, ChatRunFailedError

client = TestClient(app)


class FakeChatService:
    def __init__(self, answer=None, error=None):
        self._answer = answer
        self._error = error
        self.last_call = None

    async def get_answer(self, query, session_id=None, temperature=None):
        self.last_call = {"query": query, "session_id": session_id, "temperature": temperature}
        if self._error:
            raise self._error
        return self._answer


@pytest.fixture(autouse=True)
def clear_overrides():
    yield
    app.dependency_overrides.pop(get_chat_service, None)


def test_chat_returns_answer_json():
    service = FakeChatService(answer=ChatAnswer(answer="hi there", sources=[]))
    app.dependency_overrides[get_chat_service] = lambda: service

    response = client.post("/chat", json={"message": "hello"})

    assert response.status_code == 200
    assert response.json() == {"answer": "hi there", "sources": []}


def test_chat_passes_session_id_and_temperature_through():
    service = FakeChatService(answer=ChatAnswer(answer="", sources=[]))
    app.dependency_overrides[get_chat_service] = lambda: service

    client.post("/chat", json={"message": "hello", "session_id": "s1", "temperature": 0.2})

    assert service.last_call == {"query": "hello", "session_id": "s1", "temperature": 0.2}


def test_chat_rejects_empty_message():
    response = client.post("/chat", json={"message": ""})

    assert response.status_code == 422


def test_chat_returns_502_when_run_fails():
    service = FakeChatService(error=ChatRunFailedError("model error"))
    app.dependency_overrides[get_chat_service] = lambda: service

    response = client.post("/chat", json={"message": "hello"})

    assert response.status_code == 502
