import json
from typing import Any, AsyncIterator, Optional

import httpx


class AgentNotFoundError(Exception):
    def __init__(self, agent_id: str):
        self.agent_id = agent_id
        super().__init__(f"Powabase agent {agent_id} not found")


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

    async def create_knowledge_base(self, name: str) -> dict:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{self.base_url}/api/knowledge-bases",
                headers=self.headers,
                json={
                    "name": name,
                    "indexing_config": {
                        "strategy": "chunk_embed",
                        "chunk_size": 1000,
                        "chunk_overlap": 200,
                    },
                    "retrieval_config": {"method": "hybrid", "top_k": 4},
                },
            )
        resp.raise_for_status()
        return resp.json()

    async def create_agent(self, name: str, system_prompt: str) -> dict:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{self.base_url}/api/agents",
                headers=self.headers,
                json={
                    "name": name,
                    "model": "claude-haiku-4-5",
                    "system_prompt": system_prompt,
                },
            )
        resp.raise_for_status()
        return resp.json()

    async def add_knowledge_base_to_agent(self, agent_id: str, kb_id: str) -> dict:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{self.base_url}/api/agents/{agent_id}/knowledge-bases",
                headers=self.headers,
                json={"knowledge_base_id": kb_id},
            )
        resp.raise_for_status()
        return resp.json()

    async def get_user(self, access_token: str) -> dict:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(
                f"{self.base_url}/auth/v1/user",
                headers={**self.headers, "Authorization": f"Bearer {access_token}"},
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
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404:
                raise AgentNotFoundError(agent_id) from exc
            error_payload = json.dumps(
                {"event": "error", "message": f"Powabase request failed: {exc}"}
            )
            yield f"data: {error_payload}"
        except httpx.HTTPError as exc:
            error_payload = json.dumps(
                {"event": "error", "message": f"Powabase request failed: {exc}"}
            )
            yield f"data: {error_payload}"
