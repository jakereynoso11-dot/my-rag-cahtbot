from typing import Optional

import httpx

from app.clients.postgrest_client import PostgrestClient
from app.clients.powabase_client import PowabaseClient
from app.services.chatbot_provisioning import SYSTEM_PROMPT, Chatbot

__all__ = [
    "ChatbotNotFoundError",
    "list_chatbots",
    "create_chatbot",
    "get_owned_chatbot",
    "get_chatbot_by_share_token",
    "update_chatbot",
    "delete_chatbot",
]


class ChatbotNotFoundError(Exception):
    def __init__(self, chatbot_id: str):
        self.chatbot_id = chatbot_id
        super().__init__(f"Chatbot {chatbot_id} not found")


async def list_chatbots(
    user_id: str, access_token: str, postgrest: PostgrestClient
) -> list:
    return await postgrest.select(
        "chatbots",
        "id,name,purpose,created_at,share_token",
        filters={"owner_id": user_id},
        order="created_at.desc",
        access_token=access_token,
    )


async def create_chatbot(
    user_id: str,
    name: str,
    purpose: Optional[str],
    system_prompt: Optional[str],
    access_token: str,
    postgrest: PostgrestClient,
    powabase: PowabaseClient,
) -> Chatbot:
    agent = await powabase.create_agent(name, system_prompt or SYSTEM_PROMPT)

    row = await postgrest.insert(
        "chatbots",
        {
            "owner_id": user_id,
            "name": name,
            "purpose": purpose,
            "powabase_agent_id": agent["id"],
        },
        access_token=access_token,
    )

    return Chatbot(id=row["id"], agent_id=row["powabase_agent_id"])


async def get_owned_chatbot(
    chatbot_id: str, access_token: str, postgrest: PostgrestClient
) -> Chatbot:
    row = await postgrest.select_one(
        "chatbots",
        {"id": chatbot_id},
        "id,powabase_agent_id",
        access_token=access_token,
    )
    if not row:
        raise ChatbotNotFoundError(chatbot_id)
    return Chatbot(id=row["id"], agent_id=row["powabase_agent_id"])


async def get_chatbot_by_share_token(
    share_token: str, access_token: str, postgrest: PostgrestClient
) -> Chatbot:
    """Looks up a chatbot by its public share link token instead of its id
    and an owning user -- used by the unauthenticated public chat routes,
    where the caller passes the Powabase service role key as access_token
    since there's no visitor JWT to scope a request by."""
    row = await postgrest.select_one(
        "chatbots",
        {"share_token": share_token},
        "id,powabase_agent_id",
        access_token=access_token,
    )
    if not row:
        raise ChatbotNotFoundError(share_token)
    return Chatbot(id=row["id"], agent_id=row["powabase_agent_id"])


async def update_chatbot(
    chatbot_id: str,
    *,
    name: Optional[str] = None,
    purpose: Optional[str] = None,
    system_prompt: Optional[str] = None,
    access_token: str,
    postgrest: PostgrestClient,
    powabase: PowabaseClient,
) -> dict:
    chatbot = await get_owned_chatbot(chatbot_id, access_token, postgrest)

    if system_prompt is not None:
        await powabase.update_agent(chatbot.agent_id, system_prompt=system_prompt)

    values = {}
    if name is not None:
        values["name"] = name
    if purpose is not None:
        values["purpose"] = purpose

    if values:
        rows = await postgrest.update(
            "chatbots", {"id": chatbot_id}, values, access_token=access_token
        )
        if not rows:
            raise ChatbotNotFoundError(chatbot_id)
        return rows[0]

    return await postgrest.select_one(
        "chatbots",
        {"id": chatbot_id},
        "id,name,purpose,created_at,share_token",
        access_token=access_token,
    )


async def delete_chatbot(
    chatbot_id: str,
    access_token: str,
    postgrest: PostgrestClient,
    powabase: PowabaseClient,
) -> None:
    chatbot = await get_owned_chatbot(chatbot_id, access_token, postgrest)

    await postgrest.delete("chatbots", {"id": chatbot_id}, access_token=access_token)

    # Best-effort: the chatbot row (source of truth for ownership) is already
    # gone, so a failure here just leaves an unused agent behind on Powabase
    # rather than a dangling reference the app would ever hit again.
    try:
        await powabase.delete_agent(chatbot.agent_id)
    except httpx.HTTPError:
        pass
