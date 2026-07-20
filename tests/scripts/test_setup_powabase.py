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
