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
