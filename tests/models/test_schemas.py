import pytest
from pydantic import ValidationError

from app.models.schemas import ChatRequest, IngestResponse


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


def test_ingest_response_shape():
    resp = IngestResponse(source_id="src-1", indexed_source_id="idx-1", status="indexed")

    assert resp.source_id == "src-1"
    assert resp.indexed_source_id == "idx-1"
    assert resp.status == "indexed"
