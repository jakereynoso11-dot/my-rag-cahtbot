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
