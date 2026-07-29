import httpx
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from app.api.deps import get_bearer_token, get_postgrest_client, get_powabase_client
from app.clients.postgrest_client import PostgrestClient
from app.clients.powabase_client import PowabaseClient
from app.core.config import settings
from app.models.schemas import ChatbotDocumentIngestResponse
from app.services.document_ingestion import get_chatbot_agent_id, ingest_document_for_chatbot
from app.services.ingest_service import ExtractionNotUsableError, PollTimeoutError

router = APIRouter(prefix="/ingest", tags=["ingest"])


@router.post("/file", response_model=ChatbotDocumentIngestResponse)
async def ingest_file(
    chatbot_id: str = Form(...),
    file: UploadFile = File(...),
    access_token: str = Depends(get_bearer_token),
    postgrest: PostgrestClient = Depends(get_postgrest_client),
    powabase: PowabaseClient = Depends(get_powabase_client),
):
    try:
        content = await file.read()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Could not read uploaded file: {e}")

    agent_id = await get_chatbot_agent_id(chatbot_id, access_token, postgrest)
    if not agent_id:
        raise HTTPException(status_code=404, detail=f"Chatbot not found: {chatbot_id}")

    try:
        result = await ingest_document_for_chatbot(
            content=content,
            filename=file.filename,
            mime_type=file.content_type,
            chatbot_id=chatbot_id,
            agent_id=agent_id,
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
            raise HTTPException(status_code=e.response.status_code, detail=f"Powabase request failed: {e}")
        else:
            raise HTTPException(status_code=502, detail=f"Powabase request failed: {e}")
    except httpx.HTTPError as e:
        raise HTTPException(status_code=502, detail=f"Powabase unreachable: {e}")

    return ChatbotDocumentIngestResponse(
        document_id=result.document_id,
        is_new=result.is_new,
        index_status=result.index_status,
        chatbot_document_id=result.chatbot_document_id,
    )
