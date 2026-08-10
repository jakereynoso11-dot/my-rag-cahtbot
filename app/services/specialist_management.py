from dataclasses import dataclass
from typing import Optional

import httpx

from app.clients.postgrest_client import PostgrestClient
from app.clients.powabase_client import PowabaseClient

__all__ = [
    "SpecialistNotFoundError",
    "Specialist",
    "list_specialists",
    "create_specialist",
    "delete_specialist",
    "build_specialist_system_prompt",
]


class SpecialistNotFoundError(Exception):
    def __init__(self, specialist_id: str):
        self.specialist_id = specialist_id
        super().__init__(f"Specialist {specialist_id} not found")


@dataclass
class Specialist:
    id: str
    name: str
    specialty: str
    agent_id: str


def build_specialist_system_prompt(specialty: str, custom_instructions: Optional[str]) -> str:
    base = (
        f"You are a specialist assistant focused on {specialty}. "
        "Use the knowledge base to answer the user's question. If the "
        "retrieved context is insufficient to answer, say so rather than "
        "guessing. Stay within your area of expertise; if a question falls "
        "clearly outside it, say that it's outside what you handle."
    )
    if custom_instructions:
        return f"{base}\n\n{custom_instructions}"
    return base


async def list_specialists(
    chatbot_id: str, access_token: str, postgrest: PostgrestClient
) -> list:
    return await postgrest.select(
        "chatbot_specialists",
        "id,name,specialty,created_at",
        filters={"chatbot_id": chatbot_id},
        order="created_at.asc",
        access_token=access_token,
    )


async def _existing_knowledge_base_ids(
    chatbot_id: str, access_token: str, postgrest: PostgrestClient
) -> set:
    linked_docs = await postgrest.select(
        "chatbot_documents",
        "documents(powabase_knowledge_base_id)",
        filters={"chatbot_id": chatbot_id},
        access_token=access_token,
    )
    return {
        row["documents"]["powabase_knowledge_base_id"]
        for row in linked_docs
        if row.get("documents") and row["documents"].get("powabase_knowledge_base_id")
    }


async def create_specialist(
    chatbot_id: str,
    name: str,
    specialty: str,
    system_prompt: Optional[str],
    access_token: str,
    postgrest: PostgrestClient,
    powabase: PowabaseClient,
) -> Specialist:
    """Provision a specialist agent and share the parent chatbot's already
    uploaded documents with it, so it starts out an "expert" on whatever
    the chatbot already knows."""
    agent = await powabase.create_agent(
        name, build_specialist_system_prompt(specialty, system_prompt)
    )
    agent_id = agent["id"]

    for kb_id in await _existing_knowledge_base_ids(chatbot_id, access_token, postgrest):
        await powabase.add_knowledge_base_to_agent(agent_id, kb_id)

    row = await postgrest.insert(
        "chatbot_specialists",
        {
            "chatbot_id": chatbot_id,
            "name": name,
            "specialty": specialty,
            "powabase_agent_id": agent_id,
        },
        access_token=access_token,
    )

    return Specialist(id=row["id"], name=name, specialty=specialty, agent_id=agent_id)


async def delete_specialist(
    specialist_id: str,
    chatbot_id: str,
    access_token: str,
    postgrest: PostgrestClient,
    powabase: PowabaseClient,
) -> None:
    row = await postgrest.select_one(
        "chatbot_specialists",
        {"id": specialist_id, "chatbot_id": chatbot_id},
        "id,powabase_agent_id",
        access_token=access_token,
    )
    if not row:
        raise SpecialistNotFoundError(specialist_id)

    await postgrest.delete(
        "chatbot_specialists", {"id": specialist_id}, access_token=access_token
    )

    try:
        await powabase.delete_agent(row["powabase_agent_id"])
    except httpx.HTTPError:
        pass
