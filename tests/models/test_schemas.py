import pytest
from pydantic import ValidationError

from app.models.schemas import ChatRequest, ChatResponse, DocumentResponse


def test_chat_request_requires_message():
    with pytest.raises(ValidationError):
        ChatRequest()


def test_chat_request_defaults_session_and_temperature_to_none():
    req = ChatRequest(message="hello")

    assert req.session_id is None
    assert req.temperature is None


def test_chat_request_rejects_out_of_range_temperature():
    with pytest.raises(ValidationError):
        ChatRequest(message="hello", temperature=5.0)


def test_chat_response_defaults_sources_to_empty_list():
    resp = ChatResponse(answer="hi", session_id="sess-1")

    assert resp.sources == []


def test_document_response_shape():
    resp = DocumentResponse(
        document_id="doc-1", is_new=True, index_status="indexed", chatbot_document_id="cd-1"
    )

    assert resp.document_id == "doc-1"
    assert resp.is_new is True
    assert resp.index_status == "indexed"
    assert resp.chatbot_document_id == "cd-1"
