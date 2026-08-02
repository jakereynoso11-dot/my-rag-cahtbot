import pytest
from pydantic import ValidationError

from app.models.schemas import (
    ChatbotCreate,
    ChatbotRename,
    ChatbotResponse,
    ChatRequest,
    ChatResponse,
    DocumentResponse,
)


def test_chat_request_requires_chatbot_id_and_message():
    with pytest.raises(ValidationError):
        ChatRequest()

    with pytest.raises(ValidationError):
        ChatRequest(chatbot_id="chatbot-1")

    with pytest.raises(ValidationError):
        ChatRequest(message="hello")


def test_chat_request_defaults_session_and_temperature_to_none():
    req = ChatRequest(chatbot_id="chatbot-1", message="hello")

    assert req.session_id is None
    assert req.temperature is None


def test_chat_request_rejects_out_of_range_temperature():
    with pytest.raises(ValidationError):
        ChatRequest(chatbot_id="chatbot-1", message="hello", temperature=5.0)


def test_chatbot_create_requires_name():
    with pytest.raises(ValidationError):
        ChatbotCreate()


def test_chatbot_create_defaults_system_prompt_to_none():
    req = ChatbotCreate(name="Tax Docs Helper")

    assert req.system_prompt is None


def test_chatbot_rename_requires_name():
    with pytest.raises(ValidationError):
        ChatbotRename()


def test_chatbot_response_shape():
    resp = ChatbotResponse(id="cb-1", name="Tax Docs Helper", created_at="2026-01-01T00:00:00Z")

    assert resp.id == "cb-1"
    assert resp.name == "Tax Docs Helper"
    assert resp.created_at == "2026-01-01T00:00:00Z"


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
