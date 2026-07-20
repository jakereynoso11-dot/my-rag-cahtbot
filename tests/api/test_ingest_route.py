import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.deps import get_ingest_service
from app.api.routes.ingest import router as ingest_router
from app.services.ingest_service import (
    ExtractionNotUsableError,
    IngestResult,
    PollTimeoutError,
)

app = FastAPI()
app.include_router(ingest_router)
client = TestClient(app)


class FakeIngestService:
    def __init__(self, result=None, error=None):
        self._result = result
        self._error = error

    async def ingest_pdf(self, filename, content):
        if self._error:
            raise self._error
        return self._result


@pytest.fixture(autouse=True)
def clear_overrides():
    yield
    app.dependency_overrides.pop(get_ingest_service, None)


def test_ingest_file_success():
    service = FakeIngestService(
        result=IngestResult(source_id="src-1", indexed_source_id="idx-1", status="indexed")
    )
    app.dependency_overrides[get_ingest_service] = lambda: service

    response = client.post(
        "/ingest/file", files={"file": ("doc.pdf", b"%PDF-1.4 fake", "application/pdf")}
    )

    assert response.status_code == 200
    assert response.json() == {"source_id": "src-1", "indexed_source_id": "idx-1", "status": "indexed"}


def test_ingest_file_extraction_not_usable_returns_422():
    service = FakeIngestService(error=ExtractionNotUsableError("src-1", "attention_required"))
    app.dependency_overrides[get_ingest_service] = lambda: service

    response = client.post(
        "/ingest/file", files={"file": ("doc.pdf", b"%PDF-1.4 fake", "application/pdf")}
    )

    assert response.status_code == 422


def test_ingest_file_poll_timeout_returns_504():
    service = FakeIngestService(error=PollTimeoutError("indexing", "idx-1"))
    app.dependency_overrides[get_ingest_service] = lambda: service

    response = client.post(
        "/ingest/file", files={"file": ("doc.pdf", b"%PDF-1.4 fake", "application/pdf")}
    )

    assert response.status_code == 504


def test_ingest_file_upstream_http_error_returns_502():
    service = FakeIngestService(
        error=httpx.HTTPStatusError(
            "boom", request=httpx.Request("POST", "https://x/api/sources/upload"),
            response=httpx.Response(500, request=httpx.Request("POST", "https://x")),
        )
    )
    app.dependency_overrides[get_ingest_service] = lambda: service

    response = client.post(
        "/ingest/file", files={"file": ("doc.pdf", b"%PDF-1.4 fake", "application/pdf")}
    )

    assert response.status_code == 502
