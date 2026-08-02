import json

import httpx
import respx

from app.clients.postgrest_client import PostgrestClient

BASE_URL = "https://example.p.powabase.ai"
API_KEY = "service-role-key"
TOKEN = "user-jwt-token"


def make_client() -> PostgrestClient:
    return PostgrestClient(base_url=BASE_URL, api_key=API_KEY)


@respx.mock
async def test_rpc_posts_payload_and_headers():
    route = respx.post(f"{BASE_URL}/rest/v1/rpc/register_or_get_document").mock(
        return_value=httpx.Response(200, json={"id": "doc-1"})
    )
    client = make_client()

    result = await client.rpc(
        "register_or_get_document", {"p_content_sha256": "abc"}, access_token=TOKEN
    )

    assert result == {"id": "doc-1"}
    request = route.calls.last.request
    assert request.headers["apikey"] == API_KEY
    assert request.headers["Authorization"] == f"Bearer {TOKEN}"
    assert json.loads(request.content) == {"p_content_sha256": "abc"}


@respx.mock
async def test_select_applies_filters_and_order():
    route = respx.get(f"{BASE_URL}/rest/v1/documents").mock(
        return_value=httpx.Response(200, json=[{"id": "doc-1"}])
    )
    client = make_client()

    result = await client.select(
        "documents",
        "id,original_filename",
        filters={"user_id": "u1"},
        order="created_at.desc",
        access_token=TOKEN,
    )

    assert result == [{"id": "doc-1"}]
    request = route.calls.last.request
    assert request.url.params["select"] == "id,original_filename"
    assert request.url.params["user_id"] == "eq.u1"
    assert request.url.params["order"] == "created_at.desc"


@respx.mock
async def test_select_one_returns_first_row_or_none():
    respx.get(f"{BASE_URL}/rest/v1/chatbots").mock(
        return_value=httpx.Response(200, json=[{"powabase_agent_id": "agent-1"}])
    )
    client = make_client()

    result = await client.select_one(
        "chatbots", {"owner_id": "u1"}, "powabase_agent_id", access_token=TOKEN
    )

    assert result == {"powabase_agent_id": "agent-1"}


@respx.mock
async def test_select_one_returns_none_when_empty():
    respx.get(f"{BASE_URL}/rest/v1/chatbots").mock(return_value=httpx.Response(200, json=[]))
    client = make_client()

    result = await client.select_one(
        "chatbots", {"owner_id": "u1"}, "powabase_agent_id", access_token=TOKEN
    )

    assert result is None


@respx.mock
async def test_insert_returns_created_row():
    route = respx.post(f"{BASE_URL}/rest/v1/chat_sessions").mock(
        return_value=httpx.Response(201, json=[{"id": "sess-1", "user_id": "u1"}])
    )
    client = make_client()

    result = await client.insert("chat_sessions", {"user_id": "u1"}, access_token=TOKEN)

    assert result == {"id": "sess-1", "user_id": "u1"}
    assert route.calls.last.request.headers["Prefer"] == "return=representation"


@respx.mock
async def test_update_applies_filters_and_returns_rows():
    route = respx.patch(f"{BASE_URL}/rest/v1/documents").mock(
        return_value=httpx.Response(200, json=[{"id": "doc-1", "index_status": "indexed"}])
    )
    client = make_client()

    result = await client.update(
        "documents", {"id": "doc-1"}, {"index_status": "indexed"}, access_token=TOKEN
    )

    assert result == [{"id": "doc-1", "index_status": "indexed"}]
    request = route.calls.last.request
    assert request.url.params["id"] == "eq.doc-1"
    assert json.loads(request.content) == {"index_status": "indexed"}


@respx.mock
async def test_delete_applies_filters_and_returns_rows():
    route = respx.delete(f"{BASE_URL}/rest/v1/chatbots").mock(
        return_value=httpx.Response(200, json=[{"id": "cb-1"}])
    )
    client = make_client()

    result = await client.delete("chatbots", {"id": "cb-1"}, access_token=TOKEN)

    assert result == [{"id": "cb-1"}]
    request = route.calls.last.request
    assert request.url.params["id"] == "eq.cb-1"
    assert request.headers["Prefer"] == "return=representation"
