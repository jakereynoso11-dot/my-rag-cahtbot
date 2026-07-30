from dataclasses import dataclass

from app.clients.postgrest_client import PostgrestClient
from app.clients.powabase_client import PowabaseClient

SYSTEM_PROMPT = (
    "You are a helpful assistant. Use the knowledge base to answer the user's "
    "question. If the retrieved context is insufficient to answer, say so "
    "rather than guessing."
)


@dataclass
class Chatbot:
    id: str
    agent_id: str


async def get_or_create_chatbot(
    user_id: str,
    access_token: str,
    postgrest: PostgrestClient,
    powabase: PowabaseClient,
) -> Chatbot:
    row = await postgrest.select_one(
        "chatbots",
        {"owner_id": user_id},
        "id,powabase_agent_id",
        access_token=access_token,
    )
    if row:
        return Chatbot(id=row["id"], agent_id=row["powabase_agent_id"])

    agent = await powabase.create_agent(f"user-{user_id}-agent", SYSTEM_PROMPT)

    row = await postgrest.insert(
        "chatbots",
        {"owner_id": user_id, "name": "My Assistant", "powabase_agent_id": agent["id"]},
        access_token=access_token,
    )

    return Chatbot(id=row["id"], agent_id=row["powabase_agent_id"])
