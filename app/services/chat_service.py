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
    powabase_session_id: Optional[str] = None


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
        powabase_session_id = session_id

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

            if event == "start" and payload.get("session_id"):
                powabase_session_id = payload["session_id"]

            if event == "complete":
                if payload.get("status") == "failed":
                    raise ChatRunFailedError(payload.get("error") or "Powabase run failed")
                content = payload.get("content", "")

        return ChatAnswer(answer=content, powabase_session_id=powabase_session_id)
