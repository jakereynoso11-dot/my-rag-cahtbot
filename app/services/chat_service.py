import json
from dataclasses import dataclass, field
from typing import Optional

from app.clients.powabase_client import PowabaseClient


class ChatRunFailedError(Exception):
    def __init__(self, message: str):
        self.message = message
        super().__init__(message)


@dataclass
class ChatAnswer:
    answer: str
    sources: list = field(default_factory=list)


class ChatService:
    def __init__(self, client: PowabaseClient, agent_id: str):
        self.client = client
        self.agent_id = agent_id

    async def get_answer(
        self,
        query: str,
        session_id: Optional[str] = None,
        temperature: Optional[float] = None,
    ) -> ChatAnswer:
        content = ""

        async for line in self.client.stream_agent_run(
            self.agent_id,
            message=query,
            session_id=session_id,
            temperature=temperature,
        ):
            if not line.startswith("data: "):
                continue
            payload = json.loads(line[len("data: "):])
            event = payload.get("event")

            if event == "error":
                raise ChatRunFailedError(payload.get("message") or "Powabase run failed")

            if event == "complete":
                if payload.get("status") == "failed":
                    raise ChatRunFailedError(payload.get("error") or "Powabase run failed")
                content = payload.get("content", "")

        return ChatAnswer(answer=content)
