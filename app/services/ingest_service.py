import asyncio
from dataclasses import dataclass
from typing import Optional

from app.clients.powabase_client import PowabaseClient

EXTRACTION_TERMINAL = {"extracted", "attention_required", "failed", "cancelled"}
EXTRACTION_USABLE = {"extracted"}
INDEX_TERMINAL = {"indexed", "failed", "cancelled"}


class ExtractionNotUsableError(Exception):
    def __init__(self, source_id: str, status: str):
        self.source_id = source_id
        self.status = status
        super().__init__(
            f"Source {source_id} extraction ended in unusable status: {status}"
        )


class PollTimeoutError(Exception):
    def __init__(self, stage: str, resource_id: str):
        self.stage = stage
        self.resource_id = resource_id
        super().__init__(f"Timed out waiting for {stage} on {resource_id}")


@dataclass
class IngestResult:
    source_id: str
    indexed_source_id: str
    status: str


class IngestService:
    def __init__(
        self,
        client: PowabaseClient,
        kb_id: str,
        poll_interval: float = 2.0,
        poll_timeout: float = 120.0,
    ):
        self.client = client
        self.kb_id = kb_id
        self.poll_interval = poll_interval
        self.poll_timeout = poll_timeout

    async def _wait_for_extraction(self, source_id: str) -> str:
        elapsed = 0.0
        while True:
            source = await self.client.get_source(source_id)
            status = source["extraction_status"]
            if status in EXTRACTION_TERMINAL:
                return status
            if elapsed >= self.poll_timeout:
                raise PollTimeoutError("extraction", source_id)
            await asyncio.sleep(self.poll_interval)
            elapsed += self.poll_interval

    async def _wait_for_indexing(self, indexed_source_id: str) -> str:
        elapsed = 0.0
        while True:
            listing = await self.client.list_kb_sources(self.kb_id)
            match = next(
                (item for item in listing["items"] if item["id"] == indexed_source_id),
                None,
            )
            status = match["index_status"] if match else None
            if status in INDEX_TERMINAL:
                return status
            if elapsed >= self.poll_timeout:
                raise PollTimeoutError("indexing", indexed_source_id)
            await asyncio.sleep(self.poll_interval)
            elapsed += self.poll_interval

    async def ingest_pdf(self, filename: str, content: bytes) -> IngestResult:
        uploaded = await self.client.upload_source(filename, content)
        source_id = uploaded["id"]

        extraction_status = await self._wait_for_extraction(source_id)
        if extraction_status not in EXTRACTION_USABLE:
            raise ExtractionNotUsableError(source_id, extraction_status)

        added = await self.client.add_source_to_kb(self.kb_id, source_id)
        indexed_source_id = added["id"]

        index_status = await self._wait_for_indexing(indexed_source_id)

        return IngestResult(
            source_id=source_id,
            indexed_source_id=indexed_source_id,
            status=index_status,
        )
