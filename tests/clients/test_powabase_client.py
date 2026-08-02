import json

import httpx
import pytest
import respx

from app.clients.powabase_client import AgentNotFoundError, PowabaseClient

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


@respx.mock
async def test_create_knowledge_base():
    route = respx.post(f"{BASE_URL}/api/knowledge-bases").mock(
        return_value=httpx.Response(201, json={"id": "kb-new"})
    )
    client = make_client()

    result = await client.create_knowledge_base("user-1-kb")

    assert result == {"id": "kb-new"}
    payload = json.loads(route.calls.last.request.content)
    assert payload["name"] == "user-1-kb"
    assert payload["indexing_config"]["strategy"] == "chunk_embed"
    assert payload["retrieval_config"]["method"] == "hybrid"


@respx.mock
async def test_create_agent():
    route = respx.post(f"{BASE_URL}/api/agents").mock(
        return_value=httpx.Response(201, json={"id": "agent-new"})
    )
    client = make_client()

    result = await client.create_agent("user-1-agent", "system prompt")

    assert result == {"id": "agent-new"}
    payload = json.loads(route.calls.last.request.content)
    assert payload == {
        "name": "user-1-agent",
        "model": "claude-haiku-4-5",
        "system_prompt": "system prompt",
    }


@respx.mock
async def test_delete_agent():
    route = respx.delete(f"{BASE_URL}/api/agents/agent-1").mock(
        return_value=httpx.Response(204)
    )
    client = make_client()

    await client.delete_agent("agent-1")

    request = route.calls.last.request
    assert request.headers["apikey"] == API_KEY


@respx.mock
async def test_add_knowledge_base_to_agent():
    route = respx.post(f"{BASE_URL}/api/agents/agent-1/knowledge-bases").mock(
        return_value=httpx.Response(201, json={"id": "link-1"})
    )
    client = make_client()

    result = await client.add_knowledge_base_to_agent("agent-1", "kb-1")

    assert result == {"id": "link-1"}
    payload = json.loads(route.calls.last.request.content)
    assert payload == {"knowledge_base_id": "kb-1"}


@respx.mock
async def test_get_user():
    route = respx.get(f"{BASE_URL}/auth/v1/user").mock(
        return_value=httpx.Response(200, json={"id": "user-1", "email": "a@example.com"})
    )
    client = make_client()

    result = await client.get_user("user-jwt-token")

    assert result == {"id": "user-1", "email": "a@example.com"}
    request = route.calls.last.request
    assert request.headers["apikey"] == API_KEY
    assert request.headers["Authorization"] == "Bearer user-jwt-token"


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


@respx.mock
async def test_stream_agent_run_raises_agent_not_found_on_404():
    respx.post(f"{BASE_URL}/api/agents/agent-1/run/stream").mock(
        return_value=httpx.Response(404, json={"error": "not_found"})
    )
    client = make_client()

    with pytest.raises(AgentNotFoundError) as exc_info:
        async for _ in client.stream_agent_run("agent-1", message="hello"):
            pass

    assert exc_info.value.agent_id == "agent-1"
