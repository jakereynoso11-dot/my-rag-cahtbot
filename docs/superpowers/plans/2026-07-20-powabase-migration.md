# Powabase Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the LangChain + Supabase + direct-OpenAI stack in `app/` with Powabase's Sources/Knowledge-Base RAG pipeline and Agent chat, keeping FastAPI as a thin, trusted proxy.

**Architecture:** FastAPI holds the Powabase Service Role key server-side. `/ingest/file` uploads to Powabase Sources, polls extraction, adds the source to one fixed Knowledge Base, and polls indexing. `/chat` streams `/api/agents/{id}/run/stream` SSE straight through to the client (the Agent, linked to that KB, handles retrieval and generation itself). A one-time standalone script provisions the KB and Agent.

**Tech Stack:** FastAPI, `httpx` (async, replaces `supabase`/`openai`/LangChain), `pytest` + `pytest-asyncio` + `respx` for tests.

## Global Constraints

- Every Powabase `/api/*` call needs both `apikey` and `Authorization: Bearer` headers with the Service Role (Secret) key — this key never leaves the server.
- KB uses indexing strategy `chunk_embed` and retrieval method `hybrid` (Powabase's recommended default for general documents).
- `409 duplicate_source` on source upload is a success path (reuse the returned duplicate source), not an error.
- Extraction terminal states are `extracted`, `attention_required`, `failed`, `cancelled`; only `extracted` is usable for indexing — `attention_required`/`failed` surface as a client error, not a silent retry.
- Polling (extraction and indexing) is bounded by a timeout; exceeding it surfaces as a `504`.
- Powabase's per-run body has no `max_output_tokens`-equivalent field — it is not ported.
- Chat is SSE-streamed straight through with no event reshaping; a mid-stream (or pre-stream) Powabase error is forwarded as a `data: {"event": "error", ...}` line, not raised as an HTTP exception once streaming has begun.
- KB/Agent IDs and chunking/`top_k` defaults are fixed, provisioned once by a standalone script — not created or configured per-request by the running app.

---

### Task 1: Test tooling and project hygiene

**Files:**
- Modify: `requirements.txt`
- Create: `pytest.ini`
- Create: `conftest.py` (repo root)
- Create: `.gitignore`

**Interfaces:**
- Produces: a working `pytest` command that collects zero tests without error, and `app.*` modules importable from any test file placed under `tests/`.

- [ ] **Step 1: Add test dependencies to `requirements.txt`**

Add these lines (keep existing lines untouched for now — later tasks will remove the Supabase/OpenAI/LangChain ones):

```
pytest
pytest-asyncio
respx
httpx
```

- [ ] **Step 2: Install dependencies**

Run: `pip install -r requirements.txt`
Expected: installs `pytest`, `pytest-asyncio`, `respx`, `httpx` (and the existing packages) with no errors.

- [ ] **Step 3: Create `pytest.ini`**

```ini
[pytest]
asyncio_mode = auto
```

- [ ] **Step 4: Create an empty root `conftest.py`**

```python
```

(An empty file is sufficient — its presence makes pytest add the repo root to `sys.path`, so test files can `import app.xxx`.)

- [ ] **Step 5: Create `.gitignore`**

There is currently no `.gitignore`, and `.env` (which holds secrets) shows up as an untracked file in `git status`. Add one:

```gitignore
.venv/
__pycache__/
*.pyc
.env
tmp/
deploy.zip
```

- [ ] **Step 6: Verify pytest runs cleanly**

Run: `pytest`
Expected: `no tests ran` (exit code 0 or 5), no import errors.

- [ ] **Step 7: Commit**

```bash
git add requirements.txt pytest.ini conftest.py .gitignore
git commit -m "Add pytest/respx test tooling and a .gitignore"
```

---

### Task 2: Rewrite config settings and the health route

**Files:**
- Modify: `app/core/config.py`
- Modify: `app/api/routes/health.py`
- Modify: `.env`
- Create: `tests/core/test_config.py`

**Interfaces:**
- Produces: `Settings` fields `powabase_base_url: str`, `powabase_api_key: str`, `powabase_kb_id: str`, `powabase_agent_id: str` — every later task reads these from `app.core.config.settings`.

- [ ] **Step 1: Write the failing test**

Create `tests/core/test_config.py`:

```python
import importlib
import os

import pytest


def _reload_settings(monkeypatch, **env):
    for key in [
        "powabase_base_url", "powabase_api_key", "powabase_kb_id", "powabase_agent_id",
    ]:
        monkeypatch.delenv(key.upper(), raising=False)
    for key, value in env.items():
        monkeypatch.setenv(key.upper(), value)
    monkeypatch.setenv("PYDANTIC_SETTINGS_ENV_FILE", "")

    import app.core.config as config_module
    importlib.reload(config_module)
    return config_module


def test_settings_load_powabase_fields(monkeypatch, tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text(
        "POWABASE_BASE_URL=https://example.p.powabase.ai\n"
        "POWABASE_API_KEY=secret-key\n"
        "POWABASE_KB_ID=kb-123\n"
        "POWABASE_AGENT_ID=agent-456\n"
    )
    monkeypatch.chdir(tmp_path)

    import app.core.config as config_module
    importlib.reload(config_module)

    assert config_module.settings.powabase_base_url == "https://example.p.powabase.ai"
    assert config_module.settings.powabase_api_key == "secret-key"
    assert config_module.settings.powabase_kb_id == "kb-123"
    assert config_module.settings.powabase_agent_id == "agent-456"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/core/test_config.py -v`
Expected: FAIL — `app.core.config` still requires `openai_api_key`/`supabase_url`/`supabase_key` and has no `powabase_*` fields, so `Settings()` raises a `pydantic.ValidationError` on import (module-level `settings = Settings()`), or the new fields don't exist.

- [ ] **Step 3: Rewrite `app/core/config.py`**

```python
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # Powabase
    powabase_base_url: str
    powabase_api_key: str
    powabase_kb_id: str
    powabase_agent_id: str


settings = Settings()
```

- [ ] **Step 4: Update `.env`**

Read the current `.env`, remove the `OPENAI_API_KEY`, `SUPABASE_URL`, `SUPABASE_KEY` lines, and add:

```
POWABASE_BASE_URL=
POWABASE_API_KEY=
POWABASE_KB_ID=
POWABASE_AGENT_ID=
```

Leave the values blank for now — they get filled in during Task 9 (the setup script) and from the Studio Connect modal. The app will not start until they're filled in; that's expected until then.

- [ ] **Step 5: Rewrite `app/api/routes/health.py`**

```python
from fastapi import APIRouter
from app.core.config import settings

router = APIRouter(tags=["health"])


@router.get("/health")
def health():
    return {
        "status": "ok",
        "powabase_base_url": settings.powabase_base_url,
        "knowledge_base_id": settings.powabase_kb_id,
        "agent_id": settings.powabase_agent_id,
    }
```

- [ ] **Step 6: Run test to verify it passes**

Run: `pytest tests/core/test_config.py -v`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add app/core/config.py app/api/routes/health.py .env tests/core/test_config.py
git commit -m "Replace Supabase/OpenAI settings with Powabase config"
```

---

### Task 3: `PowabaseClient` — the authenticated HTTP boundary

**Files:**
- Create: `app/clients/powabase_client.py`
- Delete: `app/clients/supabase_client.py`
- Delete: `app/clients/openai_client.py`
- Delete: `app/clients/embeddings.py`
- Create: `tests/clients/test_powabase_client.py`

**Interfaces:**
- Consumes: nothing from other app modules (plain `httpx`).
- Produces: `PowabaseClient(base_url: str, api_key: str)` with:
  - `async def upload_source(self, filename: str, content: bytes) -> dict` — returns the source dict (`id`, `extraction_status`, ...) whether the upload was new (`201`) or a duplicate (`409`, unwraps `["duplicate"]`).
  - `async def get_source(self, source_id: str) -> dict`
  - `async def add_source_to_kb(self, kb_id: str, source_id: str) -> dict` — returns the indexed-source dict (`id` is the `indexed_source_id`).
  - `async def list_kb_sources(self, kb_id: str) -> dict` — returns `{"items": [...], "total": ..., ...}`.
  - `async def stream_agent_run(self, agent_id: str, message: str, session_id: str | None = None, temperature: float | None = None) -> AsyncIterator[str]` — yields raw `data: {...}` lines (no trailing blank line), buffering partial network chunks and dropping `:`-prefixed keepalive comments and blank lines. On an `httpx.HTTPError` (before or during the stream), yields one `data: {"event": "error", "message": "..."}` line instead of raising.

- [ ] **Step 1: Write the failing tests**

Create `tests/clients/test_powabase_client.py`:

```python
import json

import httpx
import pytest
import respx

from app.clients.powabase_client import PowabaseClient

BASE_URL = "https://example.p.powabase.ai"
API_KEY = "test-key"


def make_client() -> PowabaseClient:
    return PowabaseClient(base_url=BASE_URL, api_key=API_KEY)


@respx.mock
async def test_upload_source_success():
    route = respx.post(f"{BASE_URL}/api/sources/upload").mock(
        return_value=httpx.Response(201, json={"id": "src-1", "extraction_status": "pending"})
    )
    client = make_client()

    result = await client.upload_source("doc.pdf", b"%PDF-1.4 fake")

    assert result == {"id": "src-1", "extraction_status": "pending"}
    request = route.calls.last.request
    assert request.headers["apikey"] == API_KEY
    assert request.headers["Authorization"] == f"Bearer {API_KEY}"


@respx.mock
async def test_upload_source_duplicate_reuses_existing():
    respx.post(f"{BASE_URL}/api/sources/upload").mock(
        return_value=httpx.Response(
            409, json={"error": "duplicate_source", "duplicate": {"id": "src-existing", "extraction_status": "extracted"}}
        )
    )
    client = make_client()

    result = await client.upload_source("doc.pdf", b"%PDF-1.4 fake")

    assert result == {"id": "src-existing", "extraction_status": "extracted"}


@respx.mock
async def test_get_source():
    respx.get(f"{BASE_URL}/api/sources/src-1").mock(
        return_value=httpx.Response(200, json={"id": "src-1", "extraction_status": "extracted"})
    )
    client = make_client()

    result = await client.get_source("src-1")

    assert result["extraction_status"] == "extracted"


@respx.mock
async def test_add_source_to_kb():
    respx.post(f"{BASE_URL}/api/knowledge-bases/kb-1/sources").mock(
        return_value=httpx.Response(201, json={"id": "idx-1", "index_status": "pending"})
    )
    client = make_client()

    result = await client.add_source_to_kb("kb-1", "src-1")

    assert result == {"id": "idx-1", "index_status": "pending"}


@respx.mock
async def test_list_kb_sources():
    respx.get(f"{BASE_URL}/api/knowledge-bases/kb-1/sources").mock(
        return_value=httpx.Response(200, json={"items": [{"id": "idx-1", "index_status": "indexed"}], "total": 1})
    )
    client = make_client()

    result = await client.list_kb_sources("kb-1")

    assert result["items"][0]["index_status"] == "indexed"


class _ChunkedStream(httpx.AsyncByteStream):
    def __init__(self, chunks):
        self._chunks = chunks

    async def __aiter__(self):
        for chunk in self._chunks:
            yield chunk

    async def aclose(self) -> None:
        pass


@respx.mock
async def test_stream_agent_run_reassembles_lines_split_across_chunks():
    respx.post(f"{BASE_URL}/api/agents/agent-1/run/stream").mock(
        return_value=httpx.Response(
            200,
            stream=_ChunkedStream(
                [
                    b'data: {"event": "start", "session_id": "s1"}\n',
                    b"\n: keepalive\n\ndata: {\"eve",
                    b'nt": "complete", "content": "hi"}\n\n',
                ]
            ),
        )
    )
    client = make_client()

    lines = [line async for line in client.stream_agent_run("agent-1", message="hello")]

    assert lines == [
        'data: {"event": "start", "session_id": "s1"}',
        'data: {"event": "complete", "content": "hi"}',
    ]


@respx.mock
async def test_stream_agent_run_yields_error_event_on_http_error():
    respx.post(f"{BASE_URL}/api/agents/agent-1/run/stream").mock(
        return_value=httpx.Response(503, json={"error": "billing service unreachable"})
    )
    client = make_client()

    lines = [line async for line in client.stream_agent_run("agent-1", message="hello")]

    assert len(lines) == 1
    payload = json.loads(lines[0][len("data: "):])
    assert payload["event"] == "error"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/clients/test_powabase_client.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.clients.powabase_client'`

- [ ] **Step 3: Delete the old client files**

```bash
rm app/clients/supabase_client.py app/clients/openai_client.py app/clients/embeddings.py
```

- [ ] **Step 4: Create `app/clients/powabase_client.py`**

```python
import json
from typing import Any, AsyncIterator, Optional

import httpx


class PowabaseClient:
    def __init__(self, base_url: str, api_key: str):
        self.base_url = base_url.rstrip("/")
        self.headers = {
            "apikey": api_key,
            "Authorization": f"Bearer {api_key}",
        }

    async def upload_source(self, filename: str, content: bytes) -> dict:
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                f"{self.base_url}/api/sources/upload",
                headers=self.headers,
                files={"file": (filename, content)},
            )
        if resp.status_code == 409:
            return resp.json()["duplicate"]
        resp.raise_for_status()
        return resp.json()

    async def get_source(self, source_id: str) -> dict:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(
                f"{self.base_url}/api/sources/{source_id}", headers=self.headers
            )
        resp.raise_for_status()
        return resp.json()

    async def add_source_to_kb(self, kb_id: str, source_id: str) -> dict:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{self.base_url}/api/knowledge-bases/{kb_id}/sources",
                headers=self.headers,
                json={"source_id": source_id},
            )
        resp.raise_for_status()
        return resp.json()

    async def list_kb_sources(self, kb_id: str) -> dict:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(
                f"{self.base_url}/api/knowledge-bases/{kb_id}/sources",
                headers=self.headers,
            )
        resp.raise_for_status()
        return resp.json()

    async def stream_agent_run(
        self,
        agent_id: str,
        message: str,
        session_id: Optional[str] = None,
        temperature: Optional[float] = None,
    ) -> AsyncIterator[str]:
        payload: dict[str, Any] = {"message": message}
        if session_id:
            payload["session_id"] = session_id
        if temperature is not None:
            payload["temperature"] = temperature

        try:
            async with httpx.AsyncClient(timeout=None) as client:
                async with client.stream(
                    "POST",
                    f"{self.base_url}/api/agents/{agent_id}/run/stream",
                    headers=self.headers,
                    json=payload,
                ) as resp:
                    resp.raise_for_status()
                    buffer = ""
                    async for chunk in resp.aiter_text():
                        buffer += chunk
                        lines = buffer.split("\n")
                        buffer = lines.pop()
                        for line in lines:
                            if not line or line.startswith(":"):
                                continue
                            yield line
        except httpx.HTTPError as exc:
            error_payload = json.dumps(
                {"event": "error", "message": f"Powabase request failed: {exc}"}
            )
            yield f"data: {error_payload}"
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/clients/test_powabase_client.py -v`
Expected: PASS (7 tests)

- [ ] **Step 6: Commit**

```bash
git add app/clients tests/clients
git commit -m "Replace Supabase/OpenAI clients with an async Powabase HTTP client"
```

---

### Task 4: Rewrite `IngestService` for Sources + Knowledge Base

**Files:**
- Modify: `app/services/ingest_service.py` (full rewrite)
- Create: `tests/services/test_ingest_service.py`

**Interfaces:**
- Consumes: `PowabaseClient` (Task 3) — `upload_source`, `get_source`, `add_source_to_kb`, `list_kb_sources`.
- Produces: `IngestService(client: PowabaseClient, kb_id: str, poll_interval: float = 2.0, poll_timeout: float = 120.0)` with `async def ingest_pdf(self, filename: str, content: bytes) -> IngestResult`, where `IngestResult` is a dataclass with `source_id: str`, `indexed_source_id: str`, `status: str`. Raises `ExtractionNotUsableError(source_id, status)` or `PollTimeoutError(stage, resource_id)` on failure — both consumed by Task 7 (the ingest route) to pick HTTP status codes.

- [ ] **Step 1: Write the failing tests**

Create `tests/services/test_ingest_service.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/services/test_ingest_service.py -v`
Expected: FAIL — `app.services.ingest_service` still imports LangChain/Supabase and has no `IngestService.ingest_pdf`/`ExtractionNotUsableError`/`PollTimeoutError`.

- [ ] **Step 3: Rewrite `app/services/ingest_service.py`**

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/services/test_ingest_service.py -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Commit**

```bash
git add app/services/ingest_service.py tests/services/test_ingest_service.py
git commit -m "Rewrite IngestService to use Powabase Sources and Knowledge Bases"
```

---

### Task 5: Rewrite `ChatService` for Agent streaming, remove `RetrievalService`

**Files:**
- Modify: `app/services/chat_service.py` (full rewrite)
- Delete: `app/services/retrieval_service.py`
- Create: `tests/services/test_chat_service.py`

**Interfaces:**
- Consumes: `PowabaseClient.stream_agent_run` (Task 3).
- Produces: `ChatService(client: PowabaseClient, agent_id: str)` with `async def stream_answer(self, query: str, session_id: str | None = None, temperature: float | None = None) -> AsyncIterator[str]`, yielding fully-framed SSE chunks (each ending in `\n\n`) ready to hand to `StreamingResponse`.

- [ ] **Step 1: Write the failing tests**

Create `tests/services/test_chat_service.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/services/test_chat_service.py -v`
Expected: FAIL — `app.services.chat_service` still has the old OpenAI-based `ChatService` with a different constructor/method signature.

- [ ] **Step 3: Delete `app/services/retrieval_service.py`**

```bash
rm app/services/retrieval_service.py
```

(Its job — similarity search — now happens inside the Agent's own `knowledge_search` tool during `/run/stream`; the app no longer calls KB search directly.)

- [ ] **Step 4: Rewrite `app/services/chat_service.py`**

```python
from typing import AsyncIterator, Optional

from app.clients.powabase_client import PowabaseClient


class ChatService:
    def __init__(self, client: PowabaseClient, agent_id: str):
        self.client = client
        self.agent_id = agent_id

    async def stream_answer(
        self,
        query: str,
        session_id: Optional[str] = None,
        temperature: Optional[float] = None,
    ) -> AsyncIterator[str]:
        async for line in self.client.stream_agent_run(
            self.agent_id,
            message=query,
            session_id=session_id,
            temperature=temperature,
        ):
            yield f"{line}\n\n"
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/services/test_chat_service.py -v`
Expected: PASS (3 tests)

- [ ] **Step 6: Commit**

```bash
git add app/services/chat_service.py tests/services/test_chat_service.py
git rm app/services/retrieval_service.py
git commit -m "Rewrite ChatService to stream Powabase Agent runs; drop RetrievalService"
```

---

### Task 6: API dependencies and request/response schemas

**Files:**
- Create: `app/api/deps.py`
- Modify: `app/models/schemas.py`
- Create: `tests/api/test_deps.py`
- Create: `tests/models/test_schemas.py`

**Interfaces:**
- Consumes: `PowabaseClient` (Task 3), `IngestService` (Task 4), `ChatService` (Task 5), `app.core.config.settings` (Task 2).
- Produces: FastAPI dependency providers `get_powabase_client`, `get_ingest_service`, `get_chat_service` (Task 7/8 routes depend on these — and tests override them via `app.dependency_overrides`). Schemas: `IngestResponse(source_id: str, indexed_source_id: str, status: str)`, `ChatRequest(query: str, session_id: str | None = None, temperature: float | None = None)`.

- [ ] **Step 1: Write the failing tests**

Create `tests/api/test_deps.py`:

```python
from app.api.deps import get_chat_service, get_ingest_service, get_powabase_client
from app.clients.powabase_client import PowabaseClient
from app.services.chat_service import ChatService
from app.services.ingest_service import IngestService


def test_get_powabase_client_uses_settings(monkeypatch):
    import app.core.config as config_module

    monkeypatch.setattr(config_module.settings, "powabase_base_url", "https://x.p.powabase.ai")
    monkeypatch.setattr(config_module.settings, "powabase_api_key", "key-123")

    client = get_powabase_client()

    assert isinstance(client, PowabaseClient)
    assert client.base_url == "https://x.p.powabase.ai"
    assert client.headers["apikey"] == "key-123"


def test_get_ingest_service_wires_kb_id(monkeypatch):
    import app.core.config as config_module

    monkeypatch.setattr(config_module.settings, "powabase_kb_id", "kb-123")
    client = PowabaseClient(base_url="https://x.p.powabase.ai", api_key="key")

    service = get_ingest_service(client=client)

    assert isinstance(service, IngestService)
    assert service.kb_id == "kb-123"


def test_get_chat_service_wires_agent_id(monkeypatch):
    import app.core.config as config_module

    monkeypatch.setattr(config_module.settings, "powabase_agent_id", "agent-123")
    client = PowabaseClient(base_url="https://x.p.powabase.ai", api_key="key")

    service = get_chat_service(client=client)

    assert isinstance(service, ChatService)
    assert service.agent_id == "agent-123"
```

Create `tests/models/test_schemas.py`:

```python
import pytest
from pydantic import ValidationError

from app.models.schemas import ChatRequest, IngestResponse


def test_chat_request_requires_query():
    with pytest.raises(ValidationError):
        ChatRequest()


def test_chat_request_defaults_session_and_temperature_to_none():
    req = ChatRequest(query="hello")

    assert req.session_id is None
    assert req.temperature is None


def test_chat_request_rejects_out_of_range_temperature():
    with pytest.raises(ValidationError):
        ChatRequest(query="hello", temperature=5.0)


def test_ingest_response_shape():
    resp = IngestResponse(source_id="src-1", indexed_source_id="idx-1", status="indexed")

    assert resp.source_id == "src-1"
    assert resp.indexed_source_id == "idx-1"
    assert resp.status == "indexed"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/api/test_deps.py tests/models/test_schemas.py -v`
Expected: FAIL — `app.api.deps` doesn't exist yet; `app.models.schemas` still has the old `ChatRequest`/`IngestResponse`/`SourceChunk`/`ChatResponse` fields.

- [ ] **Step 3: Create `app/api/deps.py`**

Note the `client` parameters use `Depends(get_powabase_client)` as their default, not a plain `None` — a plain default would make FastAPI try to resolve `client` as a request parameter (it can't serialize a `PowabaseClient`) whenever `get_ingest_service`/`get_chat_service` are wired into a route via `Depends(...)`. `Depends(...)` tells FastAPI to resolve it as a sub-dependency instead. Calling these functions directly in a test (passing `client=` explicitly, as below) overrides that default normally, since `Depends(...)` is just an ordinary default value from Python's point of view.

```python
from fastapi import Depends

from app.clients.powabase_client import PowabaseClient
from app.core.config import settings
from app.services.chat_service import ChatService
from app.services.ingest_service import IngestService


def get_powabase_client() -> PowabaseClient:
    return PowabaseClient(settings.powabase_base_url, settings.powabase_api_key)


def get_ingest_service(
    client: PowabaseClient = Depends(get_powabase_client),
) -> IngestService:
    return IngestService(client=client, kb_id=settings.powabase_kb_id)


def get_chat_service(
    client: PowabaseClient = Depends(get_powabase_client),
) -> ChatService:
    return ChatService(client=client, agent_id=settings.powabase_agent_id)
```

- [ ] **Step 4: Rewrite `app/models/schemas.py`**

```python
from typing import Optional

from pydantic import BaseModel, Field


class IngestResponse(BaseModel):
    source_id: str
    indexed_source_id: str
    status: str


class ChatRequest(BaseModel):
    query: str = Field(..., min_length=1)
    session_id: Optional[str] = None
    temperature: Optional[float] = Field(None, ge=0.0, le=2.0)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/api/test_deps.py tests/models/test_schemas.py -v`
Expected: PASS (7 tests)

- [ ] **Step 6: Commit**

```bash
git add app/api/deps.py app/models/schemas.py tests/api/test_deps.py tests/models/test_schemas.py
git commit -m "Add Powabase API dependency providers and simplified request/response schemas"
```

---

### Task 7: Rewrite the ingest route

**Files:**
- Modify: `app/api/routes/ingest.py` (full rewrite)
- Create: `tests/api/test_ingest_route.py`

**Interfaces:**
- Consumes: `get_ingest_service` (Task 6), `IngestService.ingest_pdf` / `ExtractionNotUsableError` / `PollTimeoutError` (Task 4), `IngestResponse` (Task 6).
- Produces: `POST /ingest/file` returning `IngestResponse` on success, `422` on `ExtractionNotUsableError`, `504` on `PollTimeoutError`, `502` on any other `httpx.HTTPStatusError`.

- [ ] **Step 1: Write the failing tests**

Create `tests/api/test_ingest_route.py`:

```python
import httpx
import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_ingest_service
from app.main import app
from app.services.ingest_service import (
    ExtractionNotUsableError,
    IngestResult,
    PollTimeoutError,
)

client = TestClient(app)


class FakeIngestService:
    def __init__(self, result=None, error=None):
        self._result = result
        self._error = error

    async def ingest_pdf(self, filename, content):
        if self._error:
            raise self._error
        return self._result


def override(service):
    app.dependency_overrides[get_ingest_service] = lambda: service
    yield
    app.dependency_overrides.pop(get_ingest_service, None)


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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/api/test_ingest_route.py -v`
Expected: FAIL — the route still uses `save_upload_to_tmp`/`ingest_pdf_path` and the old `IngestResponse` shape; `app.main` may also fail to import cleanly depending on task order (that's expected until this task finishes).

- [ ] **Step 3: Rewrite `app/api/routes/ingest.py`**

```python
import httpx
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from app.api.deps import get_ingest_service
from app.models.schemas import IngestResponse
from app.services.ingest_service import (
    ExtractionNotUsableError,
    IngestService,
    PollTimeoutError,
)

router = APIRouter(prefix="/ingest", tags=["ingest"])


@router.post("/file", response_model=IngestResponse)
async def ingest_file(
    file: UploadFile = File(...),
    ingest_service: IngestService = Depends(get_ingest_service),
):
    try:
        content = await file.read()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Could not read uploaded file: {e}")

    try:
        result = await ingest_service.ingest_pdf(file.filename, content)
    except ExtractionNotUsableError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except PollTimeoutError as e:
        raise HTTPException(status_code=504, detail=str(e))
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=502, detail=f"Powabase request failed: {e}")

    return IngestResponse(
        source_id=result.source_id,
        indexed_source_id=result.indexed_source_id,
        status=result.status,
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/api/test_ingest_route.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add app/api/routes/ingest.py tests/api/test_ingest_route.py
git commit -m "Rewrite /ingest/file to upload and index through Powabase"
```

---

### Task 8: Rewrite the chat route (SSE streaming)

**Files:**
- Modify: `app/api/routes/chat.py` (full rewrite)
- Create: `tests/api/test_chat_route.py`

**Interfaces:**
- Consumes: `get_chat_service` (Task 6), `ChatService.stream_answer` (Task 5), `ChatRequest` (Task 6).
- Produces: `POST /chat` returning a `text/event-stream` `StreamingResponse` that forwards `ChatService.stream_answer`'s chunks verbatim.

- [ ] **Step 1: Write the failing tests**

Create `tests/api/test_chat_route.py`:

```python
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

    response = client.post("/chat", json={"query": "hello"})

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert response.text == (
        'data: {"event": "start", "session_id": "s1"}\n\n'
        'data: {"event": "complete", "content": "hi"}\n\n'
    )


def test_chat_passes_session_id_and_temperature_through():
    service = FakeChatService(chunks=[])
    app.dependency_overrides[get_chat_service] = lambda: service

    client.post("/chat", json={"query": "hello", "session_id": "s1", "temperature": 0.2})

    assert service.last_call == {"query": "hello", "session_id": "s1", "temperature": 0.2}


def test_chat_rejects_empty_query():
    response = client.post("/chat", json={"query": ""})

    assert response.status_code == 422
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/api/test_chat_route.py -v`
Expected: FAIL — the route still uses the old synchronous `RetrievalService`/`ChatService`/`ChatResponse` and returns a single JSON body, not a stream.

- [ ] **Step 3: Rewrite `app/api/routes/chat.py`**

```python
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from app.api.deps import get_chat_service
from app.models.schemas import ChatRequest
from app.services.chat_service import ChatService

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("")
async def chat(
    req: ChatRequest,
    chat_service: ChatService = Depends(get_chat_service),
):
    return StreamingResponse(
        chat_service.stream_answer(
            query=req.query,
            session_id=req.session_id,
            temperature=req.temperature,
        ),
        media_type="text/event-stream",
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/api/test_chat_route.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Run the full test suite**

Run: `pytest -v`
Expected: PASS — every test from Tasks 1-8 passes together, confirming `app.main` now imports and wires cleanly end to end.

- [ ] **Step 6: Commit**

```bash
git add app/api/routes/chat.py tests/api/test_chat_route.py
git commit -m "Rewrite /chat to stream Powabase Agent runs over SSE"
```

---

### Task 9: One-time Powabase provisioning script

**Files:**
- Create: `scripts/__init__.py`
- Create: `scripts/setup_powabase.py`
- Create: `tests/scripts/test_setup_powabase.py`

**Interfaces:**
- Produces: `create_kb_and_agent(base_url: str, api_key: str) -> tuple[str, str]` (returns `(kb_id, agent_id)`), and a `main()` CLI entrypoint reading `POWABASE_BASE_URL`/`POWABASE_API_KEY` from the environment and printing the resulting IDs. Not imported by the running app — this is a standalone, manually-run script.

- [ ] **Step 1: Write the failing test**

Create `tests/scripts/test_setup_powabase.py`:

```python
import httpx
import respx

from scripts.setup_powabase import create_kb_and_agent

BASE_URL = "https://example.p.powabase.ai"
API_KEY = "test-key"


@respx.mock
def test_create_kb_and_agent_creates_and_links_in_order():
    kb_route = respx.post(f"{BASE_URL}/api/knowledge-bases").mock(
        return_value=httpx.Response(201, json={"id": "kb-123"})
    )
    agent_route = respx.post(f"{BASE_URL}/api/agents").mock(
        return_value=httpx.Response(201, json={"id": "agent-456"})
    )
    link_route = respx.post(f"{BASE_URL}/api/agents/agent-456/knowledge-bases").mock(
        return_value=httpx.Response(201, json={"id": "link-1"})
    )

    kb_id, agent_id = create_kb_and_agent(BASE_URL, API_KEY)

    assert kb_id == "kb-123"
    assert agent_id == "agent-456"

    kb_body = kb_route.calls.last.request
    assert kb_body.headers["apikey"] == API_KEY
    import json
    kb_payload = json.loads(kb_body.content)
    assert kb_payload["indexing_config"]["strategy"] == "chunk_embed"
    assert kb_payload["retrieval_config"]["method"] == "hybrid"

    link_payload = json.loads(link_route.calls.last.request.content)
    assert link_payload == {"knowledge_base_id": "kb-123"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/scripts/test_setup_powabase.py -v`
Expected: FAIL — `scripts.setup_powabase` doesn't exist.

- [ ] **Step 3: Create `scripts/__init__.py`**

```python
```

- [ ] **Step 4: Create `scripts/setup_powabase.py`**

```python
import os
import sys

import httpx

SYSTEM_PROMPT = (
    "You are a helpful assistant. Use the knowledge base to answer the user's "
    "question. If the retrieved context is insufficient to answer, say so "
    "rather than guessing."
)


def create_kb_and_agent(base_url: str, api_key: str) -> tuple[str, str]:
    headers = {"apikey": api_key, "Authorization": f"Bearer {api_key}"}

    with httpx.Client(timeout=30.0) as client:
        kb_resp = client.post(
            f"{base_url}/api/knowledge-bases",
            headers=headers,
            json={
                "name": "rag-chatbot-kb",
                "indexing_config": {
                    "strategy": "chunk_embed",
                    "chunk_size": 1000,
                    "chunk_overlap": 200,
                },
                "retrieval_config": {"method": "hybrid", "top_k": 4},
            },
        )
        kb_resp.raise_for_status()
        kb_id = kb_resp.json()["id"]

        agent_resp = client.post(
            f"{base_url}/api/agents",
            headers=headers,
            json={
                "name": "rag-chatbot-agent",
                "model": "gpt-4o-mini",
                "system_prompt": SYSTEM_PROMPT,
                "settings": {"temperature": 0.4},
            },
        )
        agent_resp.raise_for_status()
        agent_id = agent_resp.json()["id"]

        link_resp = client.post(
            f"{base_url}/api/agents/{agent_id}/knowledge-bases",
            headers=headers,
            json={"knowledge_base_id": kb_id},
        )
        link_resp.raise_for_status()

    return kb_id, agent_id


def main() -> None:
    base_url = os.environ.get("POWABASE_BASE_URL")
    api_key = os.environ.get("POWABASE_API_KEY")
    if not base_url or not api_key:
        print(
            "Set POWABASE_BASE_URL and POWABASE_API_KEY environment variables first.",
            file=sys.stderr,
        )
        sys.exit(1)

    kb_id, agent_id = create_kb_and_agent(base_url, api_key)

    print(f"Created Knowledge Base: {kb_id}")
    print(f"Created Agent: {agent_id}")
    print()
    print("Add these to your .env:")
    print(f"POWABASE_KB_ID={kb_id}")
    print(f"POWABASE_AGENT_ID={agent_id}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/scripts/test_setup_powabase.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add scripts tests/scripts
git commit -m "Add one-time Powabase KB/Agent provisioning script"
```

---

### Task 10: Drop legacy dependencies and run the full suite

**Files:**
- Modify: `requirements.txt`

**Interfaces:**
- Produces: a `requirements.txt` containing only what the rewritten app actually imports.

- [ ] **Step 1: Remove unused packages from `requirements.txt`**

By this point nothing in `app/` or `scripts/` imports `supabase`, `openai`, `langchain-openai`, `langchain-community`, `langchain-text-splitters`, or `pypdf` — confirm with:

Run: `grep -rEn "langchain|supabase|^import openai|from openai" app scripts`
Expected: no output.

Then edit `requirements.txt` to:

```
fastapi
uvicorn
python-dotenv
pydantic
pydantic-settings
python-multipart
httpx
pytest
pytest-asyncio
respx
```

- [ ] **Step 2: Reinstall from the trimmed file in a scratch check**

Run: `pip install -r requirements.txt`
Expected: no errors (packages already installed from Task 1; this just confirms the file is self-consistent).

- [ ] **Step 3: Run the full test suite one final time**

Run: `pytest -v`
Expected: all tests from Tasks 2-9 PASS.

- [ ] **Step 4: Commit**

```bash
git add requirements.txt
git commit -m "Drop LangChain/Supabase/OpenAI dependencies"
```

---

## After this plan lands

The app is fully rewritten and unit-tested against mocks, but it cannot actually serve a request until the Studio-only steps from the design spec are done by hand:

1. Create a Powabase project; get the **Project URL** and **Service Role (Secret) key** from the Studio's Connect modal.
2. Configure a BYOK provider key (e.g. OpenAI) under **Settings → LLM Provider Keys**, unless AI-on-us is active.
3. Run `POWABASE_BASE_URL=... POWABASE_API_KEY=... python scripts/setup_powabase.py` (Task 9) and paste the printed `POWABASE_KB_ID`/`POWABASE_AGENT_ID` into `.env` alongside the base URL and API key.
4. Manual smoke test: start the app (`uvicorn app.main:app --reload`), `POST /ingest/file` a sample PDF, then `POST /chat` a question about it and confirm a streamed answer arrives.
