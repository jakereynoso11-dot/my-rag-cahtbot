import httpx
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from app.api.deps import (
    get_bearer_token,
    get_current_user,
    get_postgrest_client,
    get_powabase_client,
)
from app.clients.postgrest_client import PostgrestClient
from app.clients.powabase_client import PowabaseClient
from app.core.config import settings
from app.models.schemas import DocumentResponse
from app.services.chatbot_management import ChatbotNotFoundError, get_owned_chatbot
from app.services.document_ingestion import ingest_document_for_chatbot
from app.services.ingest_service import ExtractionNotUsableError, PollTimeoutError

router = APIRouter(prefix="/ingest", tags=["ingest"])


@router.post("/file", response_model=DocumentResponse)
async def ingest_file(
    chatbot_id: str = Form(...),
    file: UploadFile = File(...),
    access_token: str = Depends(get_bearer_token),
    user: dict = Depends(get_current_user),
    postgrest: PostgrestClient = Depends(get_postgrest_client),
    powabase: PowabaseClient = Depends(get_powabase_client),
):
    try:
        content = await file.read()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Could not read uploaded file: {e}")

    try:
        chatbot = await get_owned_chatbot(chatbot_id, access_token, postgrest)
    except ChatbotNotFoundError:
        raise HTTPException(status_code=404, detail="Chatbot not found")

    try:
        result = await ingest_document_for_chatbot(
            content=content,
            filename=file.filename,
            mime_type=file.content_type,
            chatbot_id=chatbot.id,
            agent_id=chatbot.agent_id,
            access_token=access_token,
            service_role_key=settings.powabase_api_key,
            postgrest=postgrest,
            powabase=powabase,
        )
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

    return DocumentResponse(
        document_id=result.document_id,
        is_new=result.is_new,
        index_status=result.index_status,
        chatbot_document_id=result.chatbot_document_id,
    )
