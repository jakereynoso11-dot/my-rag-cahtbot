from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import (
    get_bearer_token,
    get_current_user,
    get_postgrest_client,
    get_powabase_client,
)
from app.clients.postgrest_client import PostgrestClient
from app.clients.powabase_client import PowabaseClient
from app.models.schemas import SpecialistCreate, SpecialistResponse
from app.services.chatbot_management import ChatbotNotFoundError, get_owned_chatbot
from app.services.specialist_management import (
    SpecialistNotFoundError,
    create_specialist,
    delete_specialist,
    list_specialists,
)

router = APIRouter(prefix="/chatbots/{chatbot_id}/specialists", tags=["specialists"])


@router.get("", response_model=list[SpecialistResponse])
async def list_chatbot_specialists(
    chatbot_id: str,
    access_token: str = Depends(get_bearer_token),
    user: dict = Depends(get_current_user),
    postgrest: PostgrestClient = Depends(get_postgrest_client),
):
    try:
        await get_owned_chatbot(chatbot_id, access_token, postgrest)
    except ChatbotNotFoundError:
        raise HTTPException(status_code=404, detail="Chatbot not found")

    return await list_specialists(chatbot_id, access_token, postgrest)


@router.post("", response_model=SpecialistResponse)
async def create_chatbot_specialist(
    chatbot_id: str,
    req: SpecialistCreate,
    access_token: str = Depends(get_bearer_token),
    user: dict = Depends(get_current_user),
    postgrest: PostgrestClient = Depends(get_postgrest_client),
    powabase: PowabaseClient = Depends(get_powabase_client),
):
    try:
        await get_owned_chatbot(chatbot_id, access_token, postgrest)
    except ChatbotNotFoundError:
        raise HTTPException(status_code=404, detail="Chatbot not found")

    specialist = await create_specialist(
        chatbot_id,
        req.name,
        req.specialty,
        req.system_prompt,
        access_token,
        postgrest,
        powabase,
    )
    return await postgrest.select_one(
        "chatbot_specialists",
        {"id": specialist.id},
        "id,name,specialty,created_at",
        access_token=access_token,
    )


@router.delete("/{specialist_id}", status_code=204)
async def delete_chatbot_specialist(
    chatbot_id: str,
    specialist_id: str,
    access_token: str = Depends(get_bearer_token),
    user: dict = Depends(get_current_user),
    postgrest: PostgrestClient = Depends(get_postgrest_client),
    powabase: PowabaseClient = Depends(get_powabase_client),
):
    try:
        await get_owned_chatbot(chatbot_id, access_token, postgrest)
    except ChatbotNotFoundError:
        raise HTTPException(status_code=404, detail="Chatbot not found")

    try:
        await delete_specialist(
            specialist_id, chatbot_id, access_token, postgrest, powabase
        )
    except SpecialistNotFoundError:
        raise HTTPException(status_code=404, detail="Specialist not found")
