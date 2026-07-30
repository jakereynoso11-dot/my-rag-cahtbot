from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import get_chat_service
from app.models.schemas import ChatRequest, ChatResponse
from app.services.chat_service import ChatRunFailedError, ChatService

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("", response_model=ChatResponse)
async def chat(
    req: ChatRequest,
    chat_service: ChatService = Depends(get_chat_service),
):
    try:
        result = await chat_service.get_answer(
            query=req.message,
            session_id=req.session_id,
            temperature=req.temperature,
        )
    except ChatRunFailedError as e:
        raise HTTPException(status_code=502, detail=f"Powabase run failed: {e.message}")

    return ChatResponse(answer=result.answer, sources=result.sources)
