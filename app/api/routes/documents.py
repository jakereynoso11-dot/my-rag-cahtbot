from fastapi import APIRouter, Depends

from app.api.deps import (
    get_bearer_token,
    get_current_user,
    get_postgrest_client,
    get_powabase_client,
)
from app.clients.postgrest_client import PostgrestClient
from app.clients.powabase_client import PowabaseClient
from app.services.chatbot_provisioning import get_or_create_chatbot

router = APIRouter(prefix="/documents", tags=["documents"])


@router.get("")
async def list_documents(
    access_token: str = Depends(get_bearer_token),
    user: dict = Depends(get_current_user),
    postgrest: PostgrestClient = Depends(get_postgrest_client),
    powabase: PowabaseClient = Depends(get_powabase_client),
):
    chatbot = await get_or_create_chatbot(user["id"], access_token, postgrest, powabase)

    return await postgrest.select(
        "chatbot_documents",
        "id,display_name,created_at,documents(index_status,original_filename)",
        filters={"chatbot_id": chatbot.id},
        order="created_at.desc",
        access_token=access_token,
    )
