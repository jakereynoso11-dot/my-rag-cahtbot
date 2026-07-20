from fastapi import APIRouter, HTTPException

from app.core.config import settings
from app.models.schemas import ChatRequest, ChatResponse, SourceChunk

from app.clients.openai_client import get_openai_client
from app.clients.supabase_client import get_supabase_client
from app.clients.embeddings import get_embeddings

from app.services.retrieval_service import RetrievalService
from app.services.chat_service import ChatService

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("", response_model=ChatResponse)
def chat(req: ChatRequest):
    try:
        supabase = get_supabase_client()
        embeddings = get_embeddings()
        retrieval = RetrievalService(supabase=supabase, embeddings=embeddings)

        retrieved_docs = retrieval.similarity_search(
            query=req.query,
            k=min(req.k, settings.max_k),
            filter=req.filter,
            match_threshold=req.match_threshold,
        )

        openai_client = get_openai_client()
        chat_service = ChatService(openai_client=openai_client)

        model = req.model or settings.openai_model
        max_output_tokens = req.max_output_tokens or settings.default_max_output_tokens
        temperature = req.temperature if req.temperature is not None else settings.default_temperature

        answer = chat_service.answer(
            query=req.query,
            retrieved_docs=retrieved_docs,
            model=model,
            max_output_tokens=max_output_tokens,
            temperature=temperature,
        )

        sources = [
            SourceChunk(
                content_preview=(d.page_content or "")[:500],
                metadata=d.metadata or {},
            )
            for d in retrieved_docs
        ]

        return ChatResponse(answer=answer, sources=sources)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Chat failed: {e}")