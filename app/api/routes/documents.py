from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import get_bearer_token, get_current_user, get_postgrest_client
from app.clients.postgrest_client import PostgrestClient
from app.services.chatbot_management import ChatbotNotFoundError, get_owned_chatbot

router = APIRouter(prefix="/documents", tags=["documents"])


@router.get("")
async def list_documents(
    chatbot_id: str,
    access_token: str = Depends(get_bearer_token),
    user: dict = Depends(get_current_user),
    postgrest: PostgrestClient = Depends(get_postgrest_client),
):
    try:
        chatbot = await get_owned_chatbot(chatbot_id, access_token, postgrest)
    except ChatbotNotFoundError:
        raise HTTPException(status_code=404, detail="Chatbot not found")

    return await postgrest.select(
        "chatbot_documents",
        "id,display_name,created_at,documents(index_status,original_filename)",
        filters={"chatbot_id": chatbot.id},
        order="created_at.desc",
        access_token=access_token,
    )
