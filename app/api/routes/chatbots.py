from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import (
    get_bearer_token,
    get_current_user,
    get_postgrest_client,
    get_powabase_client,
)
from app.clients.postgrest_client import PostgrestClient
from app.clients.powabase_client import PowabaseClient
from app.models.schemas import ChatbotCreate, ChatbotRename, ChatbotResponse
from app.services.chatbot_management import (
    ChatbotNotFoundError,
    create_chatbot,
    delete_chatbot,
    list_chatbots,
    rename_chatbot,
)

router = APIRouter(prefix="/chatbots", tags=["chatbots"])


@router.get("", response_model=list[ChatbotResponse])
async def list_my_chatbots(
    access_token: str = Depends(get_bearer_token),
    user: dict = Depends(get_current_user),
    postgrest: PostgrestClient = Depends(get_postgrest_client),
):
    return await list_chatbots(user["id"], access_token, postgrest)


@router.post("", response_model=ChatbotResponse)
async def create_my_chatbot(
    req: ChatbotCreate,
    access_token: str = Depends(get_bearer_token),
    user: dict = Depends(get_current_user),
    postgrest: PostgrestClient = Depends(get_postgrest_client),
    powabase: PowabaseClient = Depends(get_powabase_client),
):
    chatbot = await create_chatbot(
        user["id"], req.name, req.system_prompt, access_token, postgrest, powabase
    )
    return await postgrest.select_one(
        "chatbots", {"id": chatbot.id}, "id,name,created_at", access_token=access_token
    )


@router.patch("/{chatbot_id}", response_model=ChatbotResponse)
async def rename_my_chatbot(
    chatbot_id: str,
    req: ChatbotRename,
    access_token: str = Depends(get_bearer_token),
    user: dict = Depends(get_current_user),
    postgrest: PostgrestClient = Depends(get_postgrest_client),
):
    try:
        return await rename_chatbot(chatbot_id, req.name, access_token, postgrest)
    except ChatbotNotFoundError:
        raise HTTPException(status_code=404, detail="Chatbot not found")


@router.delete("/{chatbot_id}", status_code=204)
async def delete_my_chatbot(
    chatbot_id: str,
    access_token: str = Depends(get_bearer_token),
    user: dict = Depends(get_current_user),
    postgrest: PostgrestClient = Depends(get_postgrest_client),
    powabase: PowabaseClient = Depends(get_powabase_client),
):
    try:
        await delete_chatbot(chatbot_id, access_token, postgrest, powabase)
    except ChatbotNotFoundError:
        raise HTTPException(status_code=404, detail="Chatbot not found")
