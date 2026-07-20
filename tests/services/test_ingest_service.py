import pytest

from app.services.ingest_service import (
    ExtractionNotUsableError,
    IngestService,
    PollTimeoutError,
)


class FakePowabaseClient:
    def __init__(self):
        self.upload_source_result = {"id": "src-1"}
        self.source_statuses = ["extracted"]
        self.add_source_result = {"id": "idx-1"}
        self.index_statuses = ["indexed"]
        self._source_call = 0
        self._index_call = 0

    async def upload_source(self, filename, content):
        return self.upload_source_result

    async def get_source(self, source_id):
        status = self.source_statuses[min(self._source_call, len(self.source_statuses) - 1)]
        self._source_call += 1
        return {"id": source_id, "extraction_status": status}

    async def add_source_to_kb(self, kb_id, source_id):
        return self.add_source_result

    async def list_kb_sources(self, kb_id):
        status = self.index_statuses[min(self._index_call, len(self.index_statuses) - 1)]
        self._index_call += 1
        return {"items": [{"id": "idx-1", "index_status": status}]}


async def test_ingest_pdf_happy_path():
    client = FakePowabaseClient()
    service = IngestService(client=client, kb_id="kb-1", poll_interval=0.01, poll_timeout=1.0)

    result = await service.ingest_pdf("doc.pdf", b"fake bytes")

    assert result.source_id == "src-1"
    assert result.indexed_source_id == "idx-1"
    assert result.status == "indexed"


async def test_ingest_pdf_polls_until_extracted():
    client = FakePowabaseClient()
    client.source_statuses = ["pending", "extracting", "extracted"]
    service = IngestService(client=client, kb_id="kb-1", poll_interval=0.01, poll_timeout=1.0)

    result = await service.ingest_pdf("doc.pdf", b"fake bytes")

    assert result.status == "indexed"


async def test_ingest_pdf_raises_when_extraction_needs_attention():
    client = FakePowabaseClient()
    client.source_statuses = ["attention_required"]
    service = IngestService(client=client, kb_id="kb-1", poll_interval=0.01, poll_timeout=1.0)

    with pytest.raises(ExtractionNotUsableError) as exc_info:
        await service.ingest_pdf("doc.pdf", b"fake bytes")

    assert exc_info.value.source_id == "src-1"
    assert exc_info.value.status == "attention_required"


async def test_ingest_pdf_raises_on_extraction_poll_timeout():
    client = FakePowabaseClient()
    client.source_statuses = ["pending"]  # never reaches a terminal state
    service = IngestService(client=client, kb_id="kb-1", poll_interval=0.01, poll_timeout=0.03)

    with pytest.raises(PollTimeoutError) as exc_info:
        await service.ingest_pdf("doc.pdf", b"fake bytes")

    assert exc_info.value.stage == "extraction"


async def test_ingest_pdf_raises_on_indexing_poll_timeout():
    client = FakePowabaseClient()
    client.index_statuses = ["pending"]  # never reaches a terminal state
    service = IngestService(client=client, kb_id="kb-1", poll_interval=0.01, poll_timeout=0.03)

    with pytest.raises(PollTimeoutError) as exc_info:
        await service.ingest_pdf("doc.pdf", b"fake bytes")

    assert exc_info.value.stage == "indexing"
