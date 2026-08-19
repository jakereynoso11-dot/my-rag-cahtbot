import httpx
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from app.api.deps import (
    get_bearer_token,
    get_current_user,
    get_postgrest_client,
    get_powabase_client,
)
from app.clients.postgrest_client import PostgrestClient
from app.clients.powabase_client import PowabaseClient
from app.core.config import settings
from app.models.schemas import SpecialistCreate, SpecialistDocumentResponse, SpecialistResponse
from app.services.chatbot_management import ChatbotNotFoundError, get_owned_chatbot
from app.services.document_ingestion import (
    SpecialistNotFoundError as SpecialistDocumentNotFoundError,
)
from app.services.document_ingestion import ingest_document_for_specialist
from app.services.ingest_service import ExtractionNotUsableError, PollTimeoutError
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


@router.post("/{specialist_id}/documents", response_model=SpecialistDocumentResponse)
async def upload_specialist_document(
    chatbot_id: str,
    specialist_id: str,
    file: UploadFile = File(...),
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
        content = await file.read()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Could not read uploaded file: {e}")

    try:
        result = await ingest_document_for_specialist(
            content=content,
            filename=file.filename,
            mime_type=file.content_type,
            specialist_id=specialist_id,
            access_token=access_token,
            service_role_key=settings.powabase_api_key,
            postgrest=postgrest,
            powabase=powabase,
        )
    except SpecialistDocumentNotFoundError:
        raise HTTPException(status_code=404, detail="Specialist not found")
    except ExtractionNotUsableError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except PollTimeoutError as e:
        raise HTTPException(status_code=504, detail=str(e))
    except httpx.HTTPStatusError as e:
        if e.response.status_code in (402, 503):
            raise HTTPException(
                status_code=e.response.status_code, detail=f"Powabase request failed: {e}"
            )
        raise HTTPException(status_code=502, detail=f"Powabase request failed: {e}")
    except httpx.HTTPError as e:
        raise HTTPException(status_code=502, detail=f"Powabase unreachable: {e}")

    return SpecialistDocumentResponse(
        document_id=result.document_id,
        is_new=result.is_new,
        index_status=result.index_status,
        specialist_document_id=result.specialist_document_id,
    )


@router.get("/{specialist_id}/documents")
async def list_specialist_documents(
    chatbot_id: str,
    specialist_id: str,
    access_token: str = Depends(get_bearer_token),
    user: dict = Depends(get_current_user),
    postgrest: PostgrestClient = Depends(get_postgrest_client),
):
    try:
        await get_owned_chatbot(chatbot_id, access_token, postgrest)
    except ChatbotNotFoundError:
        raise HTTPException(status_code=404, detail="Chatbot not found")

    return await postgrest.select(
        "specialist_documents",
        "id,display_name,created_at,documents(index_status,original_filename)",
        filters={"specialist_id": specialist_id},
        order="created_at.asc",
        access_token=access_token,
    )
