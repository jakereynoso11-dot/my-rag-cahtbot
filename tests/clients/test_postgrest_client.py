import json

import httpx
import respx

from app.clients.postgrest_client import PostgrestClient

BASE_URL = "https://example.p.powabase.ai"
API_KEY = "service-role-key"
USER_JWT = "user-jwt-token"


def make_client() -> PostgrestClient:
    return PostgrestClient(base_url=BASE_URL, api_key=API_KEY)


@respx.mock
async def test_rpc_sends_two_headers_and_returns_json():
    route = respx.post(f"{BASE_URL}/rest/v1/rpc/register_or_get_document").mock(
        return_value=httpx.Response(200, json=[{"id": "doc-1", "is_new": True}])
    )
    client = make_client()

    result = await client.rpc(
        "register_or_get_document",
        {"p_content_sha256": "abc"},
        access_token=USER_JWT,
    )

    assert result == [{"id": "doc-1", "is_new": True}]
    request = route.calls.last.request
    assert request.headers["apikey"] == API_KEY
    assert request.headers["Authorization"] == f"Bearer {USER_JWT}"
    assert json.loads(request.content) == {"p_content_sha256": "abc"}


@respx.mock
async def test_select_one_returns_first_row():
    route = respx.get(f"{BASE_URL}/rest/v1/chatbots").mock(
        return_value=httpx.Response(200, json=[{"id": "cb-1", "powabase_agent_id": "agent-1"}])
    )
    client = make_client()

    result = await client.select_one(
        "chatbots", {"id": "cb-1"}, "id,powabase_agent_id", access_token=USER_JWT
    )

    assert result == {"id": "cb-1", "powabase_agent_id": "agent-1"}
    request = route.calls.last.request
    assert request.url.params["id"] == "eq.cb-1"
    assert request.url.params["select"] == "id,powabase_agent_id"
    assert request.headers["Authorization"] == f"Bearer {USER_JWT}"


@respx.mock
async def test_select_one_returns_none_when_no_rows():
    respx.get(f"{BASE_URL}/rest/v1/chatbots").mock(return_value=httpx.Response(200, json=[]))
    client = make_client()

    result = await client.select_one(
        "chatbots", {"id": "missing"}, "id,powabase_agent_id", access_token=USER_JWT
    )

    assert result is None


@respx.mock
async def test_update_sends_filters_and_prefer_header():
    route = respx.patch(f"{BASE_URL}/rest/v1/documents").mock(
        return_value=httpx.Response(200, json=[{"id": "doc-1", "index_status": "indexed"}])
    )
    client = make_client()

    result = await client.update(
        "documents",
        {"id": "doc-1"},
        {"index_status": "indexed"},
        access_token=API_KEY,
    )

    assert result == [{"id": "doc-1", "index_status": "indexed"}]
    request = route.calls.last.request
    assert request.url.params["id"] == "eq.doc-1"
    assert request.headers["Prefer"] == "return=representation"
    assert json.loads(request.content) == {"index_status": "indexed"}
